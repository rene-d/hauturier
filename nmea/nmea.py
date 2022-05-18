#!/usr/bin/env python3

# NMEA reference: https://gpsd.gitlab.io/gpsd/NMEA.html

from pathlib import Path
import click


@click.command(help="Extrait ...")
@click.option("-s", "--sentence")
@click.argument("filename")
def main(filename, sentence):

    filename = Path(filename)

    for line in filename.open():
        _, nmea = line.rstrip().split(" ", 1)
        if nmea.startswith("$") and nmea[3:6] == sentence:
            print(nmea)


if __name__ == "__main__":
    main()
