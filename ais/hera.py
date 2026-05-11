#!/usr/bin/env python3

import argparse
import json
import sys
import time
from pathlib import Path

import pyais.exceptions
import pyproj
from pyais.stream import TCPConnection

sys.path.append(Path("~/tile").expanduser().as_posix())
from nominatim import nominatim_query


# Reset
RESET = "\033[0m"

# Regular Colors
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

BG_RED = "\033[1;41;37m"

BOLD = "\033[1m"
DIMMED = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"
BLINK = "\033[5m"


class RawTextArgumentDefaultsHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    def __init__(self, prog, indent_increment=2, max_help_position=30, width=None):
        super().__init__(prog, indent_increment, max_help_position, width)


parser = argparse.ArgumentParser(formatter_class=RawTextArgumentDefaultsHelpFormatter)
parser.add_argument("-p", type=str, default="48.7 -4.0", help="coordonnées lat,lon")
parser.add_argument("-r", "--radius", type=float, default=50.0, help="rayon (NM)")
parser.add_argument("-d", "--duration", type=float, help="durée du scan (s)")
args = parser.parse_args()


radius = args.radius


try:
    p = args.p.replace(",", " ").split()
    lat, lon = map(lambda x: round(float(x), 2), p)
except ValueError:
    try:
        (lat, lon), _ = nominatim_query(args.p)
        print("nominatim:", lat, lon)
    except Exception as e:
        print(e)
        parser.error(f"mauvaises coordonnées: {args.p}")


ais_db = Path("ais.json")
if ais_db.is_file():
    ships = dict(json.loads(ais_db.read_text()))
else:
    ships = dict()


host = "hera.navimetrix.com"
port = 5000

conn = TCPConnection(host, port=port)

# conn._fobj.send(b"LAT 48.7 LON -4.0 RADIUS 20.0 AGE 2880\n")
conn._fobj.send(f"LAT {lat:.1f} LON {lon:.1f} RADIUS {radius:.1f} AGE 2880\n".encode())


ais_log = open("ais.log", "at")

geodesic = pyproj.Geod(ellps="WGS84")


current_ships = set()
modified_ships = set()


start_time = time.time()
last_write = time.time()
modified = False
delay = 10


try:
    for msg in conn:
        try:
            decoded_message = msg.decode()
        except pyais.exceptions.MissingPayloadException:
            pass
        ais_content = decoded_message

        print(ais_content, file=ais_log)
        # sys.stdout.flush()

        mmsi = str(ais_content.mmsi)

        if hasattr(ais_content, "shipname"):
            info = ships.get(mmsi, {})
            if "name" not in info:
                info["name"] = ais_content.shipname
                modified = True
                ships[mmsi] = info

                if "lat" in info and "lon" in info:
                    lat_ship = info.get("lat")
                    lon_ship = info.get("lon")

                    _, _, distance = geodesic.inv(lon_ship, lat_ship, lon, lat)

                    coords = f"{lat_ship:10.5f} {lon_ship:10.5f}    {distance / 1852:6.1f} NM"
                else:
                    coords = ""

                print(f"{mmsi:9} {info['name']:<20} {coords}")

        if hasattr(ais_content, "lon") and hasattr(ais_content, "lat"):
            info = ships.get(mmsi, {})
            info["lat"] = ais_content.lat
            info["lon"] = ais_content.lon
            ships[mmsi] = info
            current_ships.add(mmsi)
            modified_ships.add(mmsi)
            modified = True

        now = time.time()
        if args.duration and now >= start_time + args.duration:
            break

        if modified:
            if now > last_write + delay:
                ais_db.write_text(json.dumps(ships, indent=2))
                delay = 10
                last_write = now
                modified = False

                sys.stdout.write("\033[H\033[2J")
                for i, mmsi in enumerate(sorted(modified_ships), 1):
                    info = ships[mmsi]
                    name = info.get("name", "???")
                    lat = info.get("lat")
                    lon = info.get("lon")
                    xx = f"{name:<20} {lat},{lon}"
                    color = GREEN if mmsi in modified_ships else ""
                    print(f"{color}{i:3} {mmsi:<9} {xx}{RESET}")

                modified_ships.clear()

except KeyboardInterrupt:
    print("\nKeyboardInterrupt")
    pass

if modified:
    ais_db.write_text(json.dumps(ships, indent=2))
