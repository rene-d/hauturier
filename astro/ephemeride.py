#!/usr/bin/env python3

# references:
#   skyfield            https://rhodesmill.org/skyfield/
#   geocoding (france)  https://adresse.data.gouv.fr/api-doc/adresse
#   RA→GHA              https://www.celnav.de/ragha.htm

# https://thenauticalalmanac.com/
# https://github.com/aendie/SFalmanac-Py3

from datetime import datetime
from distutils.log import debug

from skyfield_data import get_skyfield_data_path
from skyfield.api import Loader, wgs84, N, W, E, S, Angle, load as load_skyfield
from skyfield.searchlib import find_discrete, find_maxima
import skyfield.jpllib
import click
import requests
from typing import Tuple
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


def load_kernel(spk) -> Tuple[skyfield.jpllib.SpiceKernel, skyfield.timelib.Timescale]:
    load_skyfield(spk)
    load = Loader(get_skyfield_data_path(), expire=False)
    return load(spk), load.timescale()


def fmt_dm(angle: Angle) -> str:
    """Format Angle in degrees° minutes'."""
    d, m = divmod(abs(angle.degrees) * 60, 60)
    dm = f"{d:.0f}° {m:.1f}'"
    if angle._degrees < 0:
        dm = "-" + dm
    return dm


@click.command(help="Ephéméride du Soleil", context_settings=dict(help_option_names=["-h", "--help"]))
@click.option("-lat", "--latitude", default=45.0, type=float, show_default=True, help="Latitude observateur")
@click.option("-lon", "--longitude", default=0.0, type=float, show_default=True, help="Longitude observateur")
@click.option("-c", "--city", type=str, help="Position observateur")
@click.option("-o", "--object", type=str, default="sun", show_default=True, help="Objet observé")
@click.option("-d", "--date", default="now", type=str, show_default=True)
def main(latitude, longitude, city, object, date):

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

    # planets, ts = load_kernel("de441.bsp")  # JPL Development Ephemeris, 1900 to 2050, 17 MB, issued in 2008
    planets, ts = load_kernel("de440s.bsp")  # JPL Development Ephemeris, 1849 to 2150, 32 MB, issued in 2020

    earth, celestial_body = planets["earth"], planets[object]

    if date == "now":
        now = ts.now()
    else:
        date = date + "0000-01-01T00:00:00+00:00"[len(date) :]
        now = ts.from_datetime(datetime.fromisoformat(date))

    observer = earth + wgs84.latlon(latitude, longitude)

    astrometric = observer.at(now).observe(celestial_body)

    print(f"Observateur:  {observer.target}")
    print()

    alt, az, d = astrometric.apparent().altaz()
    print(f"Heure:        {now.utc_datetime()}")
    print(f"Hauteur:      {alt}")
    print(f"Azimuth:      {az}")
    print()

    global ra, declinaison, a

    ra, declinaison, _ = earth.at(now).observe(celestial_body).apparent().radec(epoch="date")
    print(f"Déclinaison:      {declinaison}    {fmt_dm(declinaison)}")  #   {declinaison.degrees}")

    gha, dec, _ = (earth + wgs84.latlon(0, 0)).at(now).observe(celestial_body).apparent().hadec()
    if gha._degrees < 0:
        gha = Angle(degrees=gha._degrees + 360)
    else:
        gha = Angle(gha)
    print(f"GHA:              {gha}    {fmt_dm(gha)}")
    print()

    # earth.at(now).observe(sun).apparent().hadec()

    start_time = ts.utc(now.utc.year, now.utc.month, now.utc.day)
    end_time = ts.utc(now.utc.year, now.utc.month, now.utc.day + 1)

    times, _ = find_discrete(start_time, end_time, is_risen(celestial_body, observer))
    culmination_time, alt = find_maxima(start_time, end_time, get_angle(celestial_body, observer))
    print(f"Lever:        {times[0].utc_datetime()}")
    print(f"Culmination:  {culmination_time[0].utc_datetime()}     Hauteur: {Angle(degrees=alt[0])}")
    print(f"Coucher:      {times[1].utc_datetime()}")

    c = culmination_time[0].utc_datetime()
    c = (c - c.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()


if __name__ == "__main__":
    main(standalone_mode=False)
