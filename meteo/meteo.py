#!/usr/bin/env python3

import json
import logging
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import defusedxml.ElementTree as ET
import requests
from meteofrance_api.session import MeteoFranceSession
from tabulate import tabulate
import rapidfuzz

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


def get_settings(large=False):
    """
    Retourne les settings pour les prévisions marine de Météo France.
    """

    if large:
        f = Path("data/large.json")
        url = "https://meteofrance.com/meteo-marine/large"
    else:
        f = Path("data/meteo.json")
        url = "https://meteofrance.com/meteo-marine"

    if f.is_file():
        settings = json.loads(f.read_bytes())
    else:
        r = requests.get(url)
        if r.status_code != 200:
            raise requests.HTTPError(r)

        settings = extract_settings(r.text)
        if not settings:
            raise ValueError(f"settings {url}")

        f.write_text(json.dumps(settings, indent=2, ensure_ascii=False))

    return settings


class MeteoFranceMarine:
    def __init__(self):
        self.session = MeteoFranceSession()

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

    def get_bmr(self, domain, large=False):
        """
        Bulletin Marine Régulier
        """
        if large:
            params = {"domain": domain, "report_type": "marine", "report_subtype": "BMR_large_fr", "format": "xml"}
        else:
            params = {"domain": domain, "report_type": "marine", "report_subtype": "BMR_cote_fr", "format": "xml"}
        resp = self.session.request("get", "report", params=params)
        return resp.content

    def get_bms(self, domain, large=False):
        """
        Bulletin Marine Spécial
        """
        if large:
            params = {"domain": domain, "report_type": "marine", "report_subtype": "BMS_large_fr", "format": "json"}
        else:
            params = {"domain": domain, "report_type": "marine", "report_subtype": "BMS_cote_fr", "format": "xml"}
        resp = self.session.request("get", "report", params=params)
        return resp.content

    def get_warning(self, zone, large=False):
        zone = f"{int(zone):02d}"
        large = "LARGE" if large else "COTE"
        params = {"domain": f"BMS{large}-{zone}", "depth": 1, "warning_type": "BMS"}
        resp = self.session.request("get", "warning/timelaps", params=params)
        r = resp.json()
        bms = []
        for domain in r["subdomains_timelaps"]:
            for timelaps in domain["timelaps"]:
                for items in timelaps["timelaps_items"]:
                    if "end_time" in items:
                        bms.append((domain["domain_id"], items["begin_time"], items["end_time"]))
        return bms

    def zones(large=False):
        """
        Retourne les zones des bulletins météo
        """
        settings = get_settings(large)
        zones = settings["mf_map_layers_marine"]["subzones"]
        return iter(zones.values())

    def pois(type="Port"):
        """
        Retourne la liste des ports disponibles pour les prévisions marine de Météo France.
        """
        settings = get_settings()
        pois = settings["mf_map_layers_marine"]["pois"][type]
        return iter(pois)


def find_poi(harbor):
    if not harbor:
        return

    latlon = re.match(r"^(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)$", harbor)
    if latlon:
        return {"lat": latlon[1], "lng": latlon[2]}

    best_d = 1
    best_poi = None
    for poi in MeteoFranceMarine.pois():
        d = rapidfuzz.distance.JaroWinkler.distance(poi["title"], harbor, processor=str.lower)
        if d < best_d:
            best_d = d
            best_poi = poi
            if d == 0:
                break

    if best_d <= 0.1:
        print(f"POI {best_d} {best_poi}")
        return best_poi

    pos = adresse.search(harbor)
    if not pos:
        return

    # petite précaution
    d = rapidfuzz.distance.JaroWinkler.distance(pos["city"], harbor, processor=str.lower)
    if d > 0.1:
        print(f"{pos['city']} too far from {harbor} ({d:.3f})")
        # return

    print(f"ADRESSE: {pos}")
    return {"lat": pos["lat"], "lng": pos["lon"]}


def show_harbor(harbor, tablefmt):
    """
    Affiche les prévisions pour un port ou une position
    """

    if harbor:
        poi = find_poi(harbor)
        if not poi:
            print(f"{harbor} not found")
            return

        mfm = MeteoFranceMarine()
        marine_forecast = mfm.get_forecast_marine(poi["lat"], poi["lng"])
        Path("marine_forecast.json").write_text(json.dumps(marine_forecast, ensure_ascii=False, indent=2))

    elif Path("marine_forecast.json").is_file():
        marine_forecast = json.loads(Path("marine_forecast.json").read_text())
    else:
        print("No harbor")
        return

    properties = marine_forecast["properties"]

    fmt_time = lambda time: datetime.fromisoformat(time.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")

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

    print(
        f"{fmt_time(marine_forecast['update_time'])} {properties['zone']}  {properties['name']}  {properties['insee']}"
    )

    print(tabulate(data, headers, tablefmt=tablefmt))


def tabulate2(data, headers, **kwargs):
    n = len(data)
    data2 = [data[i] + data[i + (n + 1) // 2] for i in range(n // 2)]
    if n % 2 == 1:
        data2.append(data[n // 2 + 1])
    return tabulate(data2, headers + headers, **kwargs)


def list_pois(tablefmt):
    if tablefmt == "json":
        data = data = list(MeteoFranceMarine.pois())
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        data = list((poi["title"], poi["lat"], poi["lng"], poi["type"]) for poi in MeteoFranceMarine.pois())
        headers = ["nom port", "latitude", "longitude", "type"]
        print(tabulate(data, headers, tablefmt=tablefmt))


def list_zones(large, tablefmt):
    if tablefmt == "json":
        data = list(MeteoFranceMarine.zones(large))
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        data = list((z["title"], z["id"]) for z in MeteoFranceMarine.zones(large))
        headers = ["nom zone", "id"]
        if large:
            print(tabulate2(data, headers, tablefmt=tablefmt))
        else:
            print(tabulate(data, headers, tablefmt=tablefmt))


def show_bm(zone, special, large, tablefmt):
    if not zone:
        return

    ids = re.match(r"^(\d+)(?:\-(\d+))?", zone)
    if ids:
        ids = ids.groups()
    else:
        zone2 = re.sub("['/ ]", "", zone).lower()
        for z in MeteoFranceMarine.zones(large):
            ids, title = z["id"].split("-")[1:], re.sub("['/ ]", "", z["title"]).lower()
            if title == zone2:
                break
        else:
            ids = None
    if ids:
        if large and not special:
            ids = (ids[0], None)
        if not large and not ids[1]:
            raise ValueError(f"BMR/BMS côte: sous-zone manquante {zone}")
        domain = ("BMS" if special else "BMR") + ("LARGE" if large else "COTE") + f"-{int(ids[0]):02d}"
        if ids[1]:
            domain += f"-{int(ids[1]):02d}"
    else:
        raise ValueError(f"zone inconnue: {zone}")

    mfm = MeteoFranceMarine()
    if special:
        bm = mfm.get_bms(domain, large)
    else:
        bm = mfm.get_bmr(domain, large)

    if not bm:
        print("vide")
        return

    if special and large:
        bms = json.loads(bm)
        print(json.dumps(bms, indent=2, ensure_ascii=False))
        return

    r = ET.fromstring(bm)

    def p(node, indent=0):
        text = node.text
        if text:
            text = text.strip()

        if not text:
            text = "\n".join(f"{k}={v}" for k, v in node.items())
        else:
            if len(node.attrib) != 0:
                raise ValueError(str(node.attrib))

        text = (f"\n{'':<20}| ").join(text.split("\n"))

        tag = "  " * indent + node.tag
        print(f"{tag:<20}| {text}")

        for elem in node:
            p(elem, indent + 1)

    p(r)


def show_special(large):
    mfm = MeteoFranceMarine()
    if large:
        warnings = mfm.get_warning(1, True) + mfm.get_warning(2, True) + mfm.get_warning(3, True)
    else:
        warnings = mfm.get_warning(1, False) + mfm.get_warning(2, False)

    zone_titles = dict((z["id"], z["title"]) for z in MeteoFranceMarine.zones(large))

    headers = ["id", "name", "begin_time", "end_time"]
    data = []
    for w in warnings:
        begin_time = datetime.fromtimestamp(w[1]).strftime("%Y-%m-%d %H:%M")
        end_time = datetime.fromtimestamp(w[2]).strftime("%Y-%m-%d %H:%M")
        data.append((w[0], zone_titles[w[0]], begin_time, end_time))

    print(tabulate(data, headers, tablefmt=args.tablefmt))


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Ephemeride")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--settings", help="settings", action="store_true")
    parser.add_argument("-f", "--tablefmt", help="tablefmt ", default="fancy_outline")

    parser.add_argument("-l", "--list", help="liste les ports/zones", action="store_true")

    parser.add_argument("-b", "--bmr", help="bulletin météo régulier côte", action="store_true")
    parser.add_argument("-B", "--bmr-large", help="bulletin météo régulier large", action="store_true")

    parser.add_argument("-s", "--bms", help="bulletin météo spécial côte", action="store_true")
    parser.add_argument("-S", "--bms-large", help="bulletin météo spécial large", action="store_true")

    parser.add_argument("harbor", help="port ou zone", nargs="?")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s", level=logging.DEBUG, datefmt="%H:%M:%S")

    if args.settings:
        print(json.dumps(get_settings(), indent=2, ensure_ascii=False))
        exit()

    bm = args.bmr + args.bmr_large + args.bms + args.bms_large
    if bm > 1:
        parser.error("un seul bulletin météo")
    elif bm == 1:
        large = args.bmr_large or args.bms_large
        special = args.bms or args.bms_large

        if args.list:
            list_zones(large, args.tablefmt)
        elif not args.harbor:
            if special:
                show_special(large)
            else:
                print("missing zone")
        else:
            show_bm(args.harbor, special, large, args.tablefmt)
    else:
        if args.list:
            list_pois(args.tablefmt)
        else:
            show_harbor(args.harbor, args.tablefmt)
