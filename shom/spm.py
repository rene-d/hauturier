#!/usr/bin/env python3

"""
Service de Prédictions de Marées

https://services.data.shom.fr/support/fr/services/spm

Documentation API: https://services.data.shom.fr/spm/doc/#0-2
"""

import json
from datetime import datetime
from pathlib import Path

import defusedxml.ElementTree as ET
import requests

# SPM_KEY = "xxx"


class SPM:
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

    def hlt(self, harbor, date_ymd: datetime, correlation="1"):
        """hlt (Annuaire de marée)."""
        return self._request("hlt", harbor, date_ymd, correlation)

    def wl(self, harbor, date_ymd: datetime):
        """wl (Hauteur d'eau à un pas de temps donné)."""
        return self._request("wl", harbor, date_ymd)

    def _request(self, service, harbor, date_ymd: datetime, correlation="1"):
        """Effectue une requête au service SPM."""

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

        headers = {"Accept": "*/*"}

        if harbor not in self.data or date_ymd not in self.data[harbor]["hlt"]:

            print(f"download spm for harbor {harbor} date {date_ymd} correlation {correlation}")

            url = f"https://services.data.shom.fr/{SPM_KEY}/spm/hlt?harborName={harbor}&duration=7&date={date_ymd}&utc=standard&correlation={correlation}"
            hlt = requests.get(url, headers=headers).json()

            url = f"https://services.data.shom.fr/{SPM_KEY}/spm/wl?harborName={harbor}&duration=7&date={date_ymd}&utc=standard&nbWaterLevels=288"
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


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("harbor", help="harbor", nargs="?", default="BREST")
    args = parser.parse_args()

    a = SPM()
    h, d, m = a.hlt(args.harbor, datetime.now())
    print(h, d)
    for i in m:
        print("\t".join(i))
