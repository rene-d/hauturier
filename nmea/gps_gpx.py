#!/usr/bin/env python3

# NMEA reference: https://gpsd.gitlab.io/gpsd/NMEA.html

import sys
from pathlib import Path

import click
import gpxpy
import gpxpy.gpx


def wgs84_angle(a, sign):
    a = float(a)
    a = round((a % 100) / 60 + a // 100, 6)
    return -a if sign == "S" or sign == "W" else a


@click.command(help="Extrait la trace GPS d'une capture NMEA au format GPX")
@click.argument("filename", type=Path)
@click.argument("output", default="")
def main(filename, output: Path):
    if output == "-":
        print("output to stdout", file=sys.stderr)
    else:
        if output == "":
            output = Path(filename).with_suffix(".gpx")
        else:
            output = Path(output)
        print(f"output to {output}")

    # gpx file/track/segment
    gpx = gpxpy.gpx.GPX()

    gpx_track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(gpx_track)

    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)

    for line in filename.open():
        _, nmea = line.split(" ", 1)
        if nmea.startswith("$YDGLL"):
            f = nmea.split(",")
            latitude = wgs84_angle(f[1], f[2])
            longitune = wgs84_angle(f[3], f[4])
            gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude, longitune))

    if output == "-":
        sys.stdout.write(gpx.to_xml())
    else:
        output.write_text(gpx.to_xml())


if __name__ == "__main__":
    main()
