#!/usr/bin/env python3

import json
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import requests
from meteofrance_api import MeteoFranceClient
from tabulate import tabulate
import adresse


def extract_settings(text):
    class MeteoMarineSettings(HTMLParser):
        """
        Parser HTML pour extraire le JSON des settings.
        """

        settings = None
        data = None
        save = False

        def handle_starttag(self, tag, attrs):
            if tag == "script" and ("data-drupal-selector", "drupal-settings-json") in attrs:
                self.save = True
                self.data = []

        def handle_endtag(self, tag: str) -> None:
            if self.save and tag == "script":
                self.settings = json.loads("".join(self.data))
                self.data = None
                self.save = False

        def handle_data(self, data: str) -> None:
            if self.save:
                self.data.append(data)

    parser = MeteoMarineSettings()
    parser.feed(text)

    return parser.settings


def get_pois():
    """
    Retourne la liste des ports disponibles pour les prévisions marine de Météo France.
    """

    f = Path("pois.json")

    if f.is_file():
        return json.loads(f.read_bytes())

    r = requests.get("https://meteofrance.com/meteo-marine")
    if r.status_code != 200:
        raise requests.HTTPError(r)

    settings = extract_settings(r.text)
    if not settings:
        raise ValueError("settings-json")

    Path("settings.json").write_text(json.dumps(settings, indent=2))
    pois = settings["mf_map_layers_marine"]["pois"]["Port"]
    f.write_text(json.dumps(pois, indent=2))
    return parser.pois


class MeteoFranceMarine(MeteoFranceClient):
    def get_forecast_marine(self, latitude: float, longitude: float, language: str = "fr"):
        """
        http://webservice.meteofrance.com/forecast/marine?lat=47.115537&lon=-2.104171&id=&token=xxx
        """
        resp = self.session.request(
            "get",
            "forecast/marine",
            params={"lat": latitude, "lon": longitude, "id": ""},
        )

        return resp.json()

    def get_tide(self, citycode):
        """
        http://webservice.meteofrance.com/tide?id=4413152&token=xxx (code INSEE + 52)
        """
        resp = self.session.request("get", "tide", params={"id": citycode + "52"})

        return resp.json()


def fmt_time(time):
    return datetime.fromisoformat(time.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")


def show(harbor):

    if harbor:
        harbor2 = harbor.replace(" ", "").lower()
        for poi in get_pois():
            if poi["title"].replace(" ", "").lower() == harbor2:
                print(poi)
                break
        else:
            h = adresse.search(harbor)
            if not h:
                return
            print(h)
            poi = {"lat": h["lat"], "lng": h["lon"]}

        mfm = MeteoFranceMarine()
        r = mfm.get_forecast_marine(poi["lat"], poi["lng"])
        Path("r.json").write_text(json.dumps(r, ensure_ascii=False, indent=2))

    else:
        r = json.loads(Path("r.json").read_text())

    properties = r["properties"]

    headers = ["time", "wind_speed_kt", "beaufort_scale", "wind_direction", "sea_condition_description"]
    data = []
    arrows = ["⬇️", "↙️", "⬅️", "↖️", "⬆️", "↗️", "➡️", "↘️"]

    for i in properties["marine"]:
        row = []
        arrow = int(((i["wind_direction"] + 22.5) % 360) / 45)
        i["wind_direction"] = f"{arrows[arrow]}  {i['wind_direction']:3}°"

        i["time"] = fmt_time(i["time"])

        for header in headers:
            row.append(i[header])
        data.append(row)

    headers = ["time", "kt", "Bf", "wind", "sea"]

    print(f"{fmt_time(r['update_time'])} {properties['zone']}  {properties['name']}  {properties['insee']}")

    print(tabulate(data, headers, tablefmt="pretty"))


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Ephemeride")
    parser.add_argument("-s", "--extract-settings", help="extract_settings", action="store_true")
    parser.add_argument("harbor", help="Harbor", nargs="?")
    args = parser.parse_args()
    if args.extract_settings:
        import sys

        settings = extract_settings(sys.stdin.read())
        print(json.dumps(settings, indent=2, ensure_ascii=False))
    else:
        show(args.harbor)
