#!/usr/bin/env python3

import pyais
import click
import simplekml
import json


@click.command(help="AIS")
@click.option("--mmsi", help="filtre par MMSI", type=int)
@click.option("--gps", "flag_gps", help="trace gps", is_flag=True)
@click.option("--json", "flag_json", help="json output", is_flag=True)
@click.argument("filename")
def main(mmsi, flag_gps, flag_json, filename):

    multipart_ais = None
    coords = []
    first = True

    if flag_gps:
        flag_json = False

    if flag_json:
        print("[")

    for line in open(filename):
        timestamp, nmea = line.split(" ", 1)
        if nmea.startswith("!"):
            try:
                if multipart_ais:
                    message = pyais.decode(multipart_ais, nmea)
                    multipart_ais = None
                else:
                    message = pyais.decode(nmea)

                if mmsi and int(message.mmsi) != mmsi:
                    continue

                if flag_gps:
                    if "lon" in message.asdict():
                        coords.append((message.lon, message.lat))
                else:
                    if flag_json:
                        data = {"timestamp": timestamp, "message": message.asdict()}
                        if first:
                            first = False
                        else:
                            print(",")

                        print(json.dumps(data, indent=2), end="")
                    else:
                        print(timestamp, message)

            except pyais.exceptions.MissingMultipartMessageException as e:
                if multipart_ais is not None:
                    raise e
                multipart_ais = nmea

    if flag_json:
        print("\n]")

    if flag_gps:
        kml = simplekml.Kml(open=1)
        linestring = kml.newlinestring(name=f"mmsi {mmsi}")
        linestring.coords = coords
        linestring.altitudemode = simplekml.AltitudeMode.clamptoground
        output = f"{mmsi}.kml"
        kml.save(output)
        print(f"trace gps dans: {output}")


if __name__ == "__main__":
    main()
