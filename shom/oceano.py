#!/usr/bin/env python3

"""
Service de vignettes océanogrammes

Le service permet de générer une page html, un widget en javascript, une image png
ou un fichier texte avec les informations de météo et de mer sur quatre jours.

Il utilise une ressource WFS qui contient la liste des spots.

Il est utilisable en tant que couche dans https://data.shom.fr

Les spots sont de trois types:
- avec marégraphe du réseau RONIM ●
- un endroit prédéfini △
- un endroit quelconque (latitude/longitude)

https://services.data.shom.fr/support/fr/tuto/oceanogramme
https://services.data.shom.fr/support/fr/services/oceanogramme
"""

import requests
from pathlib import Path
import webbrowser
from urllib.parse import urlencode, quote
import json
from fnmatch import fnmatch


class Spots:
    def __init__(self, exact=True):
        typename = "OCEANOGRAMME_SPOTS_BDD_WFS:spots_oceanogramme_positions_modeles"

        if exact:
            self._pattern_filter = self._key_filter = lambda text: text.lower()
        else:
            self._key_filter = lambda text: "".join(filter(str.isalpha, str(text).lower()))
            self._pattern_filter = lambda text: "".join(filter(lambda x: x.isalpha() or x in "*?", str(text).lower()))

        f = Path(typename.split(":")[1]).with_suffix(".json")

        if not f.is_file():
            url = "https://services.data.shom.fr/clevisu/wfs"
            query = {
                "service": "WFS",
                "srsName": "EPSG:3857",  # projection Web Mercator
                "version": "1.1.0",
                "request": "GetFeature",
                "outputFormat": "application/json",
                "typeName": typename,
            }
            headers = {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0;",
                "Origin": "https://data.shom.fr",
                "Referer": "https://data.shom.fr/",  # le serveur renvoie 403 si pas le bon referer
            }
            r = requests.get(url + "?" + urlencode(query), headers=headers)
            if r.status_code != 200:
                raise requests.HTTPError(r)
            data = r.json()
            f.write_bytes(r.content)
        else:
            data = json.load(f.open())

        self.raw_data = data

    def filter(self, pattern):
        """
        Retourne la liste des spots matchant le pattern (style filename).
        """
        pattern = self._pattern_filter(pattern)

        def gen():
            for feature in self.raw_data["features"]:
                p = feature["properties"]
                if fnmatch(self._key_filter(p["cst"]), pattern):
                    yield p
                elif fnmatch(self._key_filter(p["toponyme"]), pattern):
                    yield p

        return [i for i in gen()]


class Oceano:

    TEMPERATURE_AT_SURFACE = 1
    SALINITY_AT_SURFACE = 2
    WIND_WAVES = 4
    PRIMARY_SWELL = 8
    SECONDARY_SWELL = 16

    def __init__(self, parameters=None):
        self.parameters = []
        if isinstance(parameters, int):
            if parameters & Oceano.TEMPERATURE_AT_SURFACE:
                self.parameters.append("temperature_at_surface")
            if parameters & Oceano.SALINITY_AT_SURFACE:
                self.parameters.append("salinity_at_surface")
            if parameters & Oceano.WIND_WAVES:
                self.parameters.append("wind_waves")
            if parameters & Oceano.PRIMARY_SWELL:
                self.parameters.append("primary_swell")
            if parameters & Oceano.SECONDARY_SWELL:
                self.parameters.append("secondary_swell")

    def _url(self, render, spot=None, lat=None, lon=None):
        """
        Construit l'url de l'océanogramme, soit par spot prédéfini, soit par coordonnées.
        Le spot doit exister et correspond à la property 'cst' de la ressource WFS.
        """
        if render not in ["widget", "html", "image", "text"]:
            raise ValueError(render)

        url = f"https://services.data.shom.fr/oceano/render/{render}?duration=4&delta-date=0"

        if spot and not lat and not lon:
            url += f"&spot={spot}"
        elif not spot and lat and lon:
            url += f"&lat={lat}&lon={lon}"
        else:
            raise ValueError("spot or (lat,lon)")

        url += f"&lang=fr"
        if self.parameters:
            url += "&parameters=" + quote(",".join(self.parameters))

        return url

    def _request(self, render, spot=None, lat=None, lon=None):
        url = self._url(render, spot, lat, lon)
        r = requests.get(url)
        if r.status_code != 200:
            raise requests.HTTPError(r.status_code)
        return r.content

    def _save(self, render, suffix, spot=None, lat=None, lon=None, filename=None):
        r = self._request(render, spot, lat, lon)
        if not filename:
            if spot:
                filename = spot.lower()
            else:
                filename = f"{lat}_{lon}"
        filename = Path(filename).with_suffix(suffix)
        filename.write_bytes(r)
        return filename

    def image(self, spot=None, lat=None, lon=None, filename=None):
        return self._save("image", ".png", spot, lat, lon, filename)

    def text(self, spot=None, lat=None, lon=None, filename=None):
        return self._save("text", ".txt", spot, lat, lon, filename)

    def html(self, spot=None, lat=None, lon=None):
        return self._url("html", spot, lat, lon)

    def open(self, spot=None, lat=None, lon=None):
        webbrowser.open(self._url("html", spot, lat, lon))


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("-l", "--latlon", action="store_true", help="Utilise les coordonnées du spot")
    parser.add_argument("-a", "--all", action="store_true", help="Paramètres supplémentaires")
    parser.add_argument("-i", "--image", action="store_true")
    parser.add_argument("-t", "--text", action="store_true")
    parser.add_argument("spot", help="spot", nargs="?", default="Portsall")
    args = parser.parse_args()

    spots = Spots(exact=False)
    r = spots.filter(args.spot)
    if len(r) == 0:
        print(f"Spot non trouvé: {args.spot}")
    else:
        parameters = 31 if args.all else 0
        for spot in r:
            a = Oceano(parameters=parameters)
            if args.latlon:
                req = {"lat": spot["lat"], "lon": spot["lon"]}
            else:
                req = {"spot": spot["cst"]}

            if args.text:
                print(a.text(**req))
            elif args.image:
                print(a.image(**req))
            else:
                print(a.html(**req))
