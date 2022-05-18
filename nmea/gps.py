#!/usr/bin/env python3

# NMEA reference: https://gpsd.gitlab.io/gpsd/NMEA.html

import simplekml
from pathlib import Path
import click
import sys


def wgs84_angle(a, sign):
    a = float(a)
    a = (a % 100) / 60 + a // 100
    return -a if sign == "S" or sign == "W" else a


@click.command(help="Extrait la trace GPS")
@click.argument("filename")
@click.argument("output", default="")
def main(filename, output):

    filename = Path(filename)

    if output == "-":
        print("output to stdout", file=sys.stderr)
    else:
        if output == "":
            output = Path(filename).with_suffix(".kml")
        else:
            output = Path(output)
        print(f"output to {output}")

    coords = []

    for line in filename.open():
        _, nmea = line.split(" ", 1)
        if nmea.startswith("$YDGLL"):
            f = nmea.split(",")
            latitude = wgs84_angle(f[1], f[2])
            longitune = wgs84_angle(f[3], f[4])
            coords.append((longitune, latitude))

    kml = simplekml.Kml(open=1)
    linestring = kml.newlinestring(name=f"{filename.stem}")

    linestring.coords = coords
    linestring.altitudemode = simplekml.AltitudeMode.clamptoground

    if output == "-":
        kml.save("/dev/stdout")
    else:
        kml.save(output)


if __name__ == "__main__":
    main()
