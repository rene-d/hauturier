#!/usr/bin/env python3

# references:
#   skyfield            https://rhodesmill.org/skyfield/
#   geocoding (france)  https://adresse.data.gouv.fr/api-doc/adresse
#   RA→GHA              https://www.celnav.de/ragha.htm

# https://thenauticalalmanac.com/
# https://github.com/aendie/SFalmanac-Py3

import datetime
import json
from pathlib import Path
from typing import Tuple, cast
from urllib.parse import urlencode

import requests
import skyfield.jpllib
import skyfield.timelib
from skyfield import almanac
from skyfield.api import Angle, Loader, wgs84
from skyfield.nutationlib import iau2000b_radians
from skyfield.searchlib import find_discrete, find_maxima


def _angle_func(body, observer):
    """Returns the altitude of `body` in degrees when seen from `observer` at
    terrestrial time `t`.
    """

    def _alt(t) -> float:
        t._nutation_angles_radians = iau2000b_radians(t)
        return observer.at(t).observe(body).apparent().altaz()[0].degrees

    _alt.step_days = 0.04
    return _alt


def load_kernel(spk) -> Tuple[skyfield.jpllib.SpiceKernel, skyfield.timelib.Timescale]:
    Path("data").mkdir(parents=True, exist_ok=True)
    load = Loader("data", expire=False)
    return load(spk), load.timescale()


def ephem(latitude, longitude, city, date="now"):

    filename = Path("data/cities.json")

    if filename.is_file():
        cities = json.loads(filename.read_text())
    else:
        cities = {}

    if city:
        if city.lower() in cities:
            e = cities[city.lower()]
            city, longitude, latitude = e["label"], e["longitude"], e["latitude"]
        else:
            print(f"querying for place {city}")
            q = urlencode(
                {"q": city, "type": "municipality", "limit": 1},
                doseq=True,
            )
            r = requests.get(f"https://api-adresse.data.gouv.fr/search/?{q}")
            if r.status_code != 200:
                print(f"Erreur: {r.status_code}")
                return
            r = r.json()
            if "features" not in r or len(r["features"]) == 0:
                print(f"Error: {city} not found")
                return

            label = r["features"][0]["properties"]["label"]
            longitude, latitude = r["features"][0]["geometry"]["coordinates"]

            cities[city.lower()] = {"label": label, "longitude": longitude, "latitude": latitude}
            filename.parent.mkdir(exist_ok=True, parents=True)
            filename.write_text(json.dumps(cities, indent=2, ensure_ascii=False))
            city = label

    else:

        if f"{latitude},{longitude}" in cities:
            city = cities[f"{latitude},{longitude}"]["label"]
        else:
            print(f"querying for position {latitude},{longitude}")

            # # https://nominatim.org/release-docs/develop/api/Reverse/
            # r = requests.get(
            #     f"https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=jsonv2&addressdetails=0&extratags=0&namedetails=0&zoom=10"
            # )
            # r.raise_for_status()
            # r = r.json()
            # label = r.get("name", "none")

            label = "none"
            r = requests.get(f"https://api-adresse.data.gouv.fr/reverse/?lon={longitude}&lat={latitude}")
            r.raise_for_status()
            r = r.json()
            if "features" not in r or len(r["features"]) == 0:
                print(f"Error: {latitude},{longitude} not found")
            else:
                label = r["features"][0]["properties"]["label"]

            cities[f"{latitude},{longitude}"] = {"label": label, "longitude": longitude, "latitude": latitude}
            filename.parent.mkdir(exist_ok=True, parents=True)
            filename.write_text(json.dumps(cities, indent=4))
            city = label

    # ephemeris, ts = load_kernel("de441.bsp")  # JPL Development Ephemeris, 1900 to 2050, 17 MB, issued in 2008
    ephemeris, ts = load_kernel("de440s.bsp")  # JPL Development Ephemeris, 1849 to 2150, 32 MB, issued in 2020

    if date == "now":
        now = ts.now()
    else:
        date = date + "0000-01-01"[len(date) :]
        now = ts.utc(datetime.date.fromisoformat(date))

    earth, sun = ephemeris["earth"], ephemeris["sun"]
    latlon = wgs84.latlon(latitude, longitude)
    observer = earth + wgs84.latlon(latitude, longitude)
    astrometric = observer.at(now).observe(sun)
    alt, _, _ = astrometric.apparent().altaz()

    start_time = ts.utc(now.utc.year, now.utc.month, now.utc.day)
    end_time = ts.utc(now.utc.year, now.utc.month, now.utc.day + 1)

    times, _ = find_discrete(start_time, end_time, almanac.sunrise_sunset(ephemeris, latlon))
    culmination_time, alt = find_maxima(start_time, end_time, _angle_func(sun, observer))

    return {
        "city": city,
        "longitude": longitude,
        "latitude": latitude,
        "sun": {
            "rise": times[0].utc_datetime(),
            "set": times[1].utc_datetime(),
            "culmination": culmination_time[0].utc_datetime(),
            "altitude": alt[0],  # Angle(degrees=alt[0]),
        },
    }


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Ephemeride")
    parser.add_argument("-d", "--date", type=str, help="Date", default="now")
    parser.add_argument("harbor", help="Harbor")
    args = parser.parse_args()

    try:
        latlon = args.harbor.split(",", 1)
        lat, lon = float(latlon[0]), float(latlon[1])
    except ValueError:
        e = ephem(0, 0, args.harbor, args.date)
    else:
        e = ephem(lat, lon, None, args.date)

    class EphemEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime.datetime):
                return cast(datetime, obj).isoformat()
            elif isinstance(obj, Angle):
                return str(cast(Angle, obj))
            else:
                return json.JSONEncoder.default(self, obj)

    print(json.dumps(e, indent=2, cls=EphemEncoder, ensure_ascii=False))
