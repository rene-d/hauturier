#!/usr/bin/env python3

"""
Service de Prédictions de Marées / HDM

Documentation API: https://services.data.shom.fr/spm/doc/#0-2
"""

import configparser
import json
import random
import time
from datetime import datetime
from fnmatch import fnmatch
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlencode, urlsplit

import defusedxml.ElementTree as ET
import requests
import rapidfuzz


def get_hdm_urls():
    """
    Affiche l'URL du service HDM trouvé dans la page web.
    Non documenté par le SHOM.
    """
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Host": "maree.shom.fr",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6.1 Safari/605.1.15",
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
    # Path("config.json").write_text(json.dumps(parser.config, indent=2))
    wfs_url = parser.config.get("wfsHarborUrl")
    if wfs_url:
        p = urlsplit(wfs_url)
        wfs_url = f"{p.scheme}://{p.netloc}/{p.path}"
    return parser.config.get("hdmServiceUrl"), wfs_url


def _get_keys():
    rc = Path("data/.shomrc")
    ini = configparser.ConfigParser()

    if rc.is_file():
        ini.read(rc)
    if ini.has_section("hdm"):
        return ini["hdm"]["HDM_SERVICE_URL"], ini["hdm"]["WFS_URL"]

    HDM_SERVICE_URL, WFS_URL = get_hdm_urls()

    ini.add_section("hdm")
    ini.set("hdm", "HDM_SERVICE_URL", HDM_SERVICE_URL)
    ini.set("hdm", "WFS_URL", WFS_URL)

    rc.parent.mkdir(exist_ok=True, parents=True)
    with rc.open("w") as fp:
        ini.write(fp)

    return HDM_SERVICE_URL, WFS_URL


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

    @property
    def harbors(self):
        """Charge ou retourne la liste des ports."""

        if self._harbors:
            return self._harbors

        f = Path("data/harbors.xml")
        if not f.is_file():
            url = "https://services.data.shom.fr/spm/listHarbors"
            headers = {"Accept": "*/*"}
            r = requests.get(url, headers=headers)
            r = r.content
            f.parent.mkdir(exist_ok=True, parents=True)
            f.write_bytes(r)
        else:
            r = f.read_bytes()

        r = ET.fromstring(r)
        harbors = {}
        for i in r:
            harbors[i.attrib["cst"]] = i.attrib
        self._harbors = harbors
        return harbors

    def hlt(self, harbor, date_ymd: datetime):
        """hlt (Annuaire de marée)."""
        return self._request("hlt", harbor, date_ymd)

    def wl(self, harbor, date_ymd: datetime):
        """wl (Hauteur d'eau à un pas de temps donné)."""
        return self._request("wl", harbor, date_ymd)

    def _request(self, service, harbor, date_ymd: datetime):
        """Effectue une requête au service HDM (non documenté par le SHOM)."""

        if isinstance(date_ymd, datetime):
            date_ymd = date_ymd.strftime("%Y-%m-%d")

        if harbor not in self.harbors:
            lean = "".join(filter(str.isalpha, harbor.lower()))
            for v in self.harbors.values():
                name = "".join(filter(str.isalpha, v["name"].lower()))
                if name == lean:
                    harbor = v["cst"]
                    break
            else:
                raise ValueError(harbor)

        correlation = self.harbors[harbor]["isCoeffAvailable"]

        headers = {
            "Origin": "https://maree.shom.fr",
            "Accept": "*/*",
            "Host": "services.data.shom.fr",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6.1 Safari/605.1.15",
            "Referer": "https://maree.shom.fr/",
        }

        if harbor not in self.data or date_ymd not in self.data[harbor]["hlt"]:

            time.sleep(random.random() % 3)

            print(f"download spm for harbor {harbor} date {date_ymd} correlation {correlation}")

            # if correlation == "1":
            #     date_ym1 = date_ymd[:-2]+"01"
            #     url = f"{HDM_SERVICE_URL}/spm/coeff?harborName={harbor}&duration=365&date={date_ym1}&utc=1&correlation=1"
            #     coeff = requests.get(url, headers=headers).json()
            #     # retourne un tableau sur l'année avec les coefficients pm de chaque jour

            HDM_SERVICE_URL, _ = _get_keys()

            url = f"{HDM_SERVICE_URL}/spm/hlt?harborName={harbor}&duration=7&date={date_ymd}&utc=standard&correlation={correlation}"
            hlt = requests.get(url, headers=headers).json()

            url = f"{HDM_SERVICE_URL}/spm/wl?harborName={harbor}&duration=7&date={date_ymd}&utc=standard&nbWaterLevels=288"
            wl = requests.get(url, headers=headers).json()

            if not harbor in self.data:
                self.data[harbor] = {"hlt": {}, "wl": {}, "coeff": {}}

            for k, v in wl.items():
                self.data[harbor]["wl"][k] = v

            for k, v in hlt.items():
                self.data[harbor]["hlt"][k] = v

            Path("data/spm.json").parent.mkdir(exist_ok=True, parents=True)

            json.dump(self.data, Path("data/spm.json").open("w"), indent=2)

        return harbor, date_ymd, self.data[harbor][service][date_ymd]


class WFS:
    def __init__(self, typename, access_key=None, filename=None) -> None:

        if filename:
            f = Path(filename)
        else:
            f = Path("data") / typename.split(":")[1]
            f = f.with_suffix(".json")
        if not f.is_file():
            _, WFS_URL = _get_keys()

            url = f"{WFS_URL}?"
            query = {
                "service": "WFS",
                "version": "1.0.0",
                "srsName": "EPSG:3857",  # projection Web Mercator
                "request": "GetFeature",
                "typeName": typename,
                "outputFormat": "application/json",
            }
            headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Origin": "https://maree.shom.fr",
                "Host": "services.data.shom.fr",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6.1 Safari/605.1.15",
                "Referer": "https://maree.shom.fr/",
            }

            r = requests.get(url + urlencode(query), headers=headers)
            data = r.json()
            f.parent.mkdir(exist_ok=True, parents=True)
            f.write_bytes(r.content)
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

    def __getitem__(self, key):
        return self.items.get(key)

    def __iter__(self):
        return iter(self.items.items())

    def keys(
        self,
    ):
        return self.items.keys()

    def find(self, pattern):
        lean = lambda text: "".join(filter(str.isalpha, text.lower()))

        if "*" in pattern:
            pattern = "".join(filter(lambda c: str.isalpha(c) or c == "*", pattern.lower()))
            for k, v in self.items.items():
                if fnmatch(lean(k), pattern):
                    yield k, v
        else:
            best_d = 0.15
            best_kv = None
            for k, v in self.items.items():
                d = rapidfuzz.distance.JaroWinkler.distance(k, pattern, processor=lean)
                if d == 0:
                    yield k, v
                    return
                elif d <= best_d:
                    best_d = d
                    best_kv = (k, v)
            if best_kv:
                yield best_kv


class Harbors(WFS):
    def __init__(self, **args):
        super().__init__(typename="SPM_PORTS_WFS:liste_ports_spm_h2m", access_key="cst", **args)


class Zones(WFS):
    def __init__(self, **args):
        super().__init__(typename="H2M_ZONES_WFS:zones_h2m_20160126", access_key="zone_fr", **args)


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("-u", "--url", action="store_true", help="Print hdm service and WFS urls.")
    parser.add_argument("-H", "--harbors", action="store_true", help="Fetch the list of harbors.")
    parser.add_argument("-Z", "--zones", action="store_true", help="Fetch the list of zones.")
    parser.add_argument("harbor", help="harbor", nargs="?", default="")
    args = parser.parse_args()

    if args.harbors or args.zones:
        l = Harbors() if args.harbors else Zones()
        if args.harbor:
            r = list(l.find(args.harbor))
            if len(r) == 1:
                k, v = r[0]
                print(k)
                for k, v in v.items():
                    print(f"{k:>16} : {v}")
            else:
                for k, _ in r:
                    print(k)
    elif args.url:
        print(get_hdm_urls())
    else:
        a = SPM()
        try:
            h, d, m = a.hlt(args.harbor, datetime.now())
            print(h, d)
            for i in m:
                print("\t".join(i))
        except ValueError:
            print(f"Harbor {args.harbor} not found")
