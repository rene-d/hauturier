#!/usr/bin/env python3

"""
Géolocalise une adresse avec https://adresse.data.gouv.fr/api-doc/adresse
"""

import json
from urllib.parse import urlencode

import requests


def search(city, verbose=False):
    query = urlencode(
        {"q": city, "type": "municipality", "limit": 1, "autocomplete": 0},
        doseq=True,
    )

    r = requests.get(f"https://api-adresse.data.gouv.fr/search/?{query}")
    if r.status_code != 200:
        print(f"Erreur: {r.status_code}")
        return

    r = r.json()
    if "features" not in r or len(r["features"]) == 0:
        print(f"\033[3mError: {city} not found\033[0m")
        return

    feature = r["features"][0]
    properties = feature["properties"]
    if verbose:
        print(f"\033[2m{json.dumps(feature, indent=2, ensure_ascii=False)}\033[0m")
    longitude, latitude = feature["geometry"]["coordinates"]
    return {
        "lat": latitude,
        "lon": longitude,
        "name": properties["name"],
        "city": properties["city"],
        "citycode": properties["citycode"],
    }


def reverse(lat: float, lon: float, verbose=False):
    # curl "https://api-adresse.data.gouv.fr/reverse/?lon=2.37&lat=48.357"

    r = requests.get(f"https://api-adresse.data.gouv.fr/reverse/?lon={lon}&lat={lat}")
    if r.status_code != 200:
        print(f"Erreur: {r.status_code}")
        return

    r = r.json()
    if "features" not in r or len(r["features"]) == 0:
        print(f"\033[3mError: {lat},{lon} not found\033[0m")
        return

    feature = r["features"][0]
    properties = feature["properties"]
    if verbose:
        print(f"\033[2m{json.dumps(feature, indent=2, ensure_ascii=False)}\033[0m")
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
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    parser.add_argument("q", help="Query")
    args = parser.parse_args()

    try:
        lat, lon = map(float, args.q.split(",", maxsplit=2))
        print(reverse(lat, lon, verbose=args.verbose))
    except ValueError:
        print(search(args.q, verbose=args.verbose))
