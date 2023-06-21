#!/usr/bin/env python3

from operator import itemgetter

import click
import pyais


@click.command(help="Extrait les shipnames de trames NMEA AIS")
@click.option("-a", "--all", "all_mmsi", help="toutes les données", is_flag=True)
@click.argument("filename")
def main(all_mmsi, filename):
    multipart_ais = None
    ships = {}

    for line in open(filename):
        timestamp, nmea = line.split(" ", 1)
        if nmea.startswith("!"):
            try:
                if multipart_ais:
                    message = pyais.decode(multipart_ais, nmea)
                    multipart_ais = None
                else:
                    message = pyais.decode(nmea)

                if message.mmsi not in ships:
                    ships[message.mmsi] = "?"

                if "shipname" in message.asdict():
                    name = ships[message.mmsi]
                    if name != "?" and name != message.shipname:
                        print("mmsi/shipname mismatch:", message.mmsi, message.shipname, ships[message.mmsi])
                        exit(2)
                    ships[message.mmsi] = message.shipname

            except pyais.exceptions.MissingMultipartMessageException as e:
                if multipart_ais is not None:
                    raise e
                multipart_ais = nmea

    for mmsi, name in sorted(ships.items(), key=itemgetter(0)):
        if all_mmsi or name != "?":
            print(f"{mmsi:8} {name}")


if __name__ == "__main__":
    main()
