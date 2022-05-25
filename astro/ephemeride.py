#!/usr/bin/env python3

# references:
#   skyfield            https://rhodesmill.org/skyfield/
#   skyfield-data       https://github.com/brunobord/skyfield-data
#   geocoding (france)  https://adresse.data.gouv.fr/api-doc/adresse


from datetime import datetime
from skyfield_data import get_skyfield_data_path
from skyfield.api import Loader, wgs84, N, W, E, S, Angle
from skyfield.searchlib import find_discrete, find_maxima
import click
import requests
from urllib.parse import urlencode

RISEN_ANGLE = -0.8333


def get_angle(for_aster, observer):
    def fun(time) -> float:
        return observer.at(time).observe(for_aster).apparent().altaz()[0].degrees

    fun.rough_period = 1.0
    return fun


def is_risen(for_aster, observer):
    def fun(time) -> bool:
        return get_angle(for_aster, observer)(time) > RISEN_ANGLE

    fun.rough_period = 0.5
    return fun


@click.command(help="Ephéméride du Soleil")
@click.option("-lat", "--latitude", default=45.0, type=float, show_default=True)
@click.option("-lon", "--longitude", default=0.0, type=float, show_default=True)
@click.option("-c", "--city", type=str)
@click.option("-d", "--date", default="now", type=str, show_default=True)
def main(latitude, longitude, city, date):

    if city:
        q = urlencode(
            {"q": city, "type": "municipality", "limit": 1},
            doseq=True,
        )
        r = requests.get(f"https://api-adresse.data.gouv.fr/search/?{q}")
        if r.status_code != 200:
            print(f"Erreur: {r.status_code}")
            return
        r = r.json()
        if "features" not in r:
            print(f"Error: {city} not found")
            return
        city = r["features"][0]["properties"]["label"]
        longitude, latitude = r["features"][0]["geometry"]["coordinates"]
        print(f"Ville:        {city}  {latitude}  {longitude}")

    load = Loader(get_skyfield_data_path(), expire=False)
    planets = load("de421.bsp")
    # planets = load("de440s.bsp")

    earth, sun = planets["earth"], planets["sun"]

    ts = load.timescale()

    if date == "now":
        now = ts.now()
    else:
        now = ts.from_datetime(datetime.fromisoformat(date))

    observer = earth + wgs84.latlon(latitude, longitude)

    astrometric = observer.at(now).observe(sun)

    print(f"Observateur:  {observer.target}")
    print()

    alt, az, d = astrometric.apparent().altaz()
    print(f"Heure:        {now.utc_datetime()}")
    print(f"Hauteur:      {alt}")
    print(f"Azimuth:      {az}")
    print()

    start_time = ts.utc(now.utc.year, now.utc.month, now.utc.day)
    end_time = ts.utc(now.utc.year, now.utc.month, now.utc.day + 1)

    times, _ = find_discrete(start_time, end_time, is_risen(sun, observer))
    culmination_time, alt = find_maxima(start_time, end_time, get_angle(sun, observer))
    print(f"Lever:        {times[0].utc_datetime()}")
    print(f"Culmination:  {culmination_time[0].utc_datetime()}     Hauteur: {Angle(degrees=alt[0])}")
    print(f"Coucher:      {times[1].utc_datetime()}")


if __name__ == "__main__":
    main()
