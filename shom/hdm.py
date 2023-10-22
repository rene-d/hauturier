#!/usr/bin/env python3

"""
Service de Prédictions de Marées / HDM

Site: https://maree.shom.fr
Documentation approximative API: https://services.data.shom.fr/spm/doc/#0-2
PDF: https://services.data.shom.fr/static/help/Aide-en-ligne_DATA-SHOM-FR.pdf
"""

import json
import logging
import sqlite3
import typing as t
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlencode, urlsplit

import requests

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6.1 Safari/605.1.15"  # noqa


def _get_maree_config(key=None):
    """
    Affiche l'URL du service HDM trouvé dans la page web.
    Non documenté par le SHOM.
    """
    f = Path("data/shom_config.json")

    if f.exists():
        config = json.loads(f.read_text())
    else:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9",
            "User-Agent": USER_AGENT,
        }
        r = requests.get("https://maree.shom.fr", headers=headers)

        class HdmConfig(HTMLParser):
            """Extract the config structure."""

            config = {}

            def handle_starttag(self, tag, attrs):
                if tag == "meta":
                    if ("name", "shom-horaires-des-marees/config/environment") in attrs:
                        for name, value in attrs:
                            if name == "content":
                                self.config = json.loads(unquote(value))

        parser = HdmConfig()
        parser.feed(r.text)

        if len(parser.config) == 0:
            print("config non trouvée dans https://maree.shom.fr")
            exit(2)
        Path("data/shom_config.json").write_text(json.dumps(parser.config, indent=2))
        config = parser.config

    if key is not None:
        value = config.get(key)
        if value:
            return value
        print(f"{key} non trouvé dans la config")
        exit(2)

    return config


class WFS:
    """
    Web Feature Service
    """

    def __init__(self, config_key, access_key=None, name=None) -> None:
        name = name or access_key
        self.name = name
        f = Path("data") / name
        f = f.with_suffix(".json")

        if not f.is_file():
            url = _get_maree_config(config_key)

            headers = {
                "Accept": "application/json",  # , text/javascript, */*; q=0.01",
                "User-Agent": USER_AGENT,
                "Referer": "https://maree.shom.fr/",
            }

            r = requests.get(url, headers=headers)
            data = r.json()
            f.parent.mkdir(exist_ok=True, parents=True)
            f.write_bytes(r.content)

            print(f"téléchargé: {f}")
        else:
            data = json.load(f.open())

        self.features = {}
        self.items = {}
        for feature in data["features"]:
            if access_key:
                properties = feature["properties"]
                self.items[properties[access_key]] = properties
            else:
                self.items[feature["id"]] = feature

    # def __getitem__(self, key):
    #     return self.items.get(key)

    # def __iter__(self):
    #     return iter(self.items.items())

    # def keys(self):
    #     return self.items.keys()

    def get_feature(typename):
        """
        Interroge une featue du serveur [WFS](https://fr.wikipedia.org/wiki/Web_Feature_Service).
        """
        wfs_url = _get_maree_config("wfsHarborUrl")
        assert wfs_url is not None

        p = urlsplit(wfs_url)
        wfs_url = f"{p.scheme}://{p.netloc}{p.path}"

        query = {
            "service": "WFS",
            "version": "1.0.0",
            "srsName": "EPSG:3857",  # projection Web Mercator
            "request": "GetFeature",
            "typeName": typename,
            "outputFormat": "application/json",
        }

        url = f"{wfs_url}?{urlencode(query)}"
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "User-Agent": USER_AGENT,
            "Referer": "https://maree.shom.fr/",
        }

        print(url)
        r = requests.get(url, headers=headers)
        print(r)
        print(r.content)


class Harbors(WFS):
    def __init__(self):
        super().__init__("wfsHarborUrl", access_key="cst", name="liste_ports_spm_h2m")


class SPM:
    """
    Accès au service de prédictions de marées
    """

    def __init__(self) -> None:
        if Path("data/spm.json").is_file():
            self.data = json.load(Path("data/spm.json").open())
        else:
            self.data = {}
        self._harbors = None

        self.db = sqlite3.connect("data/spm.sqlite")
        self.db.executescript(
            """
create table if not exists hlt (
    cst text not null,      -- code du port en majuscule
    date_utc text not null, -- jour au format YYYY-MM-DDTHH:MM UTC
    tide text not null,     -- high/low
    height number,          -- hauteur de la marée
    coeff integer           -- uniquement pour les PM (tide=high)
);
create unique index if not exists idx_hlt on hlt (cst, date_utc);

create table if not exists nearest (
    cst text not null,      -- code du port en majuscule
    date text not null,     -- date de la requête
    utc number not null,    -- fuseau horaire de la date de la requête
    isBM boolean,           -- true si BM, false si PM
    diff number,            -- différence en heures avec la PM la plus proche
    coeff integer,          -- uniquement pour les PM
    closest text,           -- date de la PM la plus proche
    json text               -- contenu de la réponse
);
"""
            ""
        )

        self.sess = requests.Session()
        self.sess.headers["User-Agent"] = "Mozilla/5.0"
        self.sess.headers["Referer"] = "https://maree.shom.fr/"

        self.config = _get_maree_config()
        self.hdm_service_url = self.config["hdmServiceUrl"]

    @property
    def harbors(self):
        """
        Charge ou retourne la liste des ports.
        """
        if self._harbors:
            return self._harbors

        wfs = Harbors()
        self._harbors = wfs.items
        for k, v in self._harbors.items():
            assert k == v["cst"]
        return self._harbors

    def find_harbor(self, harbor):
        if harbor.upper() not in self.harbors:
            lean = "".join(filter(str.isalpha, harbor.lower()))
            for v in self.harbors.values():
                name = "".join(filter(str.isalpha, v["cst"].lower()))
                if name == lean:
                    harbor = v["cst"]
                    break
                name = "".join(filter(str.isalpha, v["toponyme"].split()[0].lower()))
                if name == lean:
                    harbor = v["cst"]
                    break
                name = "".join(filter(str.isalpha, v["cst"].split("_")[0].lower()))
                if name == lean:
                    harbor = v["cst"]
                    break
            else:
                raise ValueError(f"Port non trouvé {harbor}")
        else:
            harbor = harbor.upper()

        return harbor

    def hlt_utc(self, harbor, date_ymd: datetime, force_update=False, duration=366):
        """
        Effectue une requête au service HDM (non documenté par le SHOM).
        service: hlt (Annuaire de marée).

        harbor doit être features[].properties.cst de liste_ports_spm_h2m
        """

        assert isinstance(date_ymd, datetime)

        if not harbor:
            return None, []

        start_date = date_ymd.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        end_date = start_date + timedelta(days=1)

        start_date_ymd = start_date.strftime("%Y-%m-%d")

        harbor = self.find_harbor(harbor)

        rows = []
        if not force_update:
            for tide, date_utc, height, coeff in self.db.execute(
                "select tide,date_utc,height,coeff from hlt where cst=? and date_utc between ? and ?",
                (
                    harbor,
                    start_date.strftime("%Y-%m-%dT%H:%M:00Z"),
                    end_date.strftime("%Y-%m-%dT%H:%M:00Z"),
                ),
            ):
                date_local = datetime.fromisoformat(date_utc).astimezone()
                rows.append((date_local.strftime("%Y-%m-%d"), date_local.strftime("%H:%M %Z"), tide, height, coeff))

        if len(rows) == 0:
            # cf. shom-horaires-des-marees.js
            # this.modelFor("harbor").properties.coeff
            correlation = self.harbors[harbor]["coeff"]

            print(f"download spm for harbor {harbor} date {start_date_ymd} correlation {correlation}")

            hlt_endpoint = self.config["hltEndpoint"]  # /spm/hlt

            url = f"{self.hdm_service_url}{hlt_endpoint}?harborName={harbor}&duration={duration}&date={start_date_ymd}&utc=0&correlation={correlation}"  # noqa
            r = self.sess.get(url)
            if r.status_code != 200:
                print(r)
                print(r.content)
                r.raise_for_status()

            hlt = r.json()
            assert duration == len(hlt)

            self.db.execute("delete from hlt where cst=? and date_utc>=?", (harbor, start_date_ymd))

            rows = []

            for date, tides in hlt.items():
                for tide, hour, height, coeff in tides:
                    tide = tide.removeprefix("tide.")
                    if tide == "none":
                        if hour != "--:--" and hour != "---":
                            print("marée inconnue", tides)
                            exit()
                        continue
                    assert tide == "high" or tide == "low"

                    height = float(height) if height != "---" else None
                    coeff = int(coeff) if coeff != "---" else None

                    date_utc = f"{date}T{hour}:00Z"

                    self.db.execute(
                        "insert into hlt (cst,date_utc,tide,height,coeff) values (?,?,?,?,?)",
                        (harbor, date_utc, tide, height, coeff),
                    )

                    date_utc = datetime.fromisoformat(date_utc)

                    if start_date <= date_utc <= end_date:
                        date_local = date_utc.astimezone()
                        rows.append(
                            (date_local.strftime("%Y-%m-%d"), date_local.strftime("%H:%M %Z"), tide, height, coeff)
                        )

            self.db.commit()

        if not (3 <= len(rows) <= 5):
            print(rows)
            print(ValueError(f"nombre de marées incorrect pour {date_ymd}"))

        return harbor, rows

    def interpolation(self, harbor, date: datetime, isBM=False) -> t.Dict[str, str]:
        harbor = harbor.upper()
        date_utc = date.astimezone(timezone.utc)

        self.hlt_utc(harbor, date_utc)
        # print(date_utc)

        tide = "low" if isBM else "high"

        cur = self.db.execute(
            "select tide,date_utc,height,coeff from hlt where cst=? and date_utc<=? and tide=? order by date_utc desc limit 1",
            (harbor, date_utc.strftime("%Y-%m-%dT%H:%M:00Z"), tide),
        )
        rows_inf = cur.fetchone()
        # print(rows_inf)

        cur = self.db.execute(
            "select tide,date_utc,height,coeff from hlt where cst=? and date_utc>=? and tide=? order by date_utc asc limit 1",
            (harbor, date_utc.strftime("%Y-%m-%dT%H:%M:00Z"), tide),
        )
        rows_sup = cur.fetchone()
        # print(rows_sup)

        if rows_inf == rows_sup:
            return {"diff": 0.00, "coeff": rows_inf[3], "closestDateTime": rows_inf[1].rstrip("Z")}

        dz = datetime.fromisoformat(rows_sup[1]) - datetime.fromisoformat(rows_inf[1])
        d = date_utc - datetime.fromisoformat(rows_inf[1])

        diff = d.total_seconds() / dz.total_seconds() * 12
        if diff <= 6:
            if tide == "low":
                coeff = self.db.execute(
                    "select coeff from hlt where cst=? and date_utc<=? and tide='high' order by date_utc desc limit 1",
                    (harbor, rows_inf[1]),
                ).fetchone()[0]
            else:
                coeff = rows_inf[3]

            return {"diff": round(diff, 2), "coeff": coeff, "closestDateTime": rows_inf[1].rstrip("Z")}
        else:
            if tide == "low":
                coeff = self.db.execute(
                    "select coeff from hlt where cst=? and date_utc<=? and tide='high' order by date_utc desc limit 1",
                    (harbor, rows_sup[1]),
                ).fetchone()[0]
            else:
                coeff = rows_sup[3]
            return {"diff": round(diff - 12, 2), "coeff": coeff, "closestDateTime": rows_sup[1].rstrip("Z")}

    def nearest(self, harbor, date: datetime, isBM=False) -> t.Dict[str, str]:
        """
        Service non documenté de lecture de la marée la plus proche d'une PM (ou d'une BM).
        """
        spm_url = "https://services.data.shom.fr/spm/rzuf4y2dexc9dsth4k9c858r"

        harbor = harbor.upper()
        date_utc = date.astimezone(timezone.utc)

        d = date_utc.strftime("%Y-%m-%dT%H:%M:%S")

        row = self.db.execute(
            "select json from nearest where cst=? and date=? and utc=0 and isBM=?", (harbor, d, isBM)
        ).fetchone()
        if row is None:
            isBM_value = "true" if isBM else "false"
            url = f"{spm_url}/diffFromNearestPM?harborName={harbor}&utc=0&datetime={d}&isBM={isBM_value}"
            r = self.sess.get(
                url,
                headers={"Referer": "https://data.shom.fr/"},
            )
            r.raise_for_status()

            logging.debug(f"response: {r}")
            logging.debug(f"response: {r.text}")
            # logging.debug(f"response: {r.headers}")

            if r.headers["content-type"].split(";")[0].strip() == "application/json":
                values = r.json()
                closest = values["closestDateTime"]
                diff = values["diff"]
                coeff = values["coeff"]

                self.db.execute(
                    "insert into nearest (cst,date,utc,isBM,diff,coeff,closest,json) values (?,?,?,?,?,?,?,?)",
                    (harbor, d, 0, isBM, diff, coeff, closest, r.text),
                )
                self.db.commit()

            else:
                print(r.headers)
                print(r.text)
                raise ValueError(f"response: {r}")
        else:
            values = json.loads(row[0])

        values["coeff"] = int(values["coeff"])
        values["diff"] = float(values["diff"])
        return values


def main():
    from argparse import ArgumentParser

    parser = ArgumentParser()

    parser.add_argument("-v", "--verbose", action="store_true", help="Affiche les requêtes")
    parser.add_argument("-f", "--force", action="store_true", help="Force le téléchargement des données")
    parser.add_argument("-d", "--date", help="Date des horaires de marée")
    parser.add_argument(
        "--duree",
        metavar="JOURS",
        type=int,
        default=1,
        help="Durée en jours",
    )
    parser.add_argument("--nearest", action="store_true", help="requête diffFromNearestPM")
    parser.add_argument("--isBM", action="store_true", help="flag BM pour --nearest")

    parser.add_argument("harbor", help="Port de référence")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    a = SPM()

    try:
        if args.date:
            date = datetime.fromisoformat(args.date)
        else:
            date = datetime.now()

        if args.harbor.lower() == "bretagne":
            for k, v in a.harbors.items():
                lat, lon = v["lat"], v["lon"]
                if -7 <= lon <= -1.5 and 47.03 <= lat <= 50.33:
                    print(k, v["toponyme"], lat, lon)
                    a.hlt_utc(k, datetime.now(), args.force)

        elif args.nearest:
            print(a.nearest(args.harbor, date, args.isBM))
            print()
            print(a.interpolation(args.harbor, date, args.isBM))

        else:
            for day in range(args.duree):
                harbor, tides = a.hlt_utc(args.harbor, date + timedelta(days=day), args.force)
                print(harbor, tides)
                for i in tides:
                    print(" ⇨ " + "\t".join(map(str, i)))

    except Exception as e:
        print(e)
        raise e


if __name__ == "__main__":
    main()
