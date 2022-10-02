#!/usr/bin/env python3

"""
Géolocalise une adresse avec https://adresse.data.gouv.fr/api-doc/adresse
"""

import json
from urllib.parse import urlencode

import requests


def search(city):
    query = urlencode(
        {"q": city, "type": "municipality", "limit": 1, "autocomplete": 0},
        doseq=True,
    )

    r = requests.get(f"https://api-adresse.data.gouv.fr/search/?{query}")
    if r.status_code != 200:
        print(f"Erreur: {r.status_code}")
        return

    r = r.json()
    if "features" not in r:
        print(f"Error: {city} not found")
        return

    feature = r["features"][0]
    properties = feature["properties"]
    # print(json.dumps(feature, indent=2, ensure_ascii=False))
    longitude, latitude = feature["geometry"]["coordinates"]
    return {
        "lat": latitude,
        "lon": longitude,
        "name": properties["name"],
        "city": properties["city"],
        "citycode": properties["citycode"],
    }


def reverse(lat: float, lon: float):

    # curl "https://api-adresse.data.gouv.fr/reverse/?lon=2.37&lat=48.357"

    r = requests.get(f"https://api-adresse.data.gouv.fr/reverse/?lon={lon}&lat={lat}")
    if r.status_code != 200:
        print(f"Erreur: {r.status_code}")
        return

    feature = r["features"][0]
    properties = feature["properties"]
    # print(json.dumps(feature, indent=2, ensure_ascii=False))
    longitude, latitude = feature["geometry"]["coordinates"]
    return {
        "lat": latitude,
        "lon": longitude,
        "name": properties["name"],
        "city": properties["city"],
        "citycode": properties["citycode"],
    }


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("q", help="Query")
    args = parser.parse_args()

    print(search(args.q))
