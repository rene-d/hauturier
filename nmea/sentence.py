#!/usr/bin/env python3

# NMEA reference: https://gpsd.gitlab.io/gpsd/NMEA.html

from pathlib import Path

import click


def validate_sentence(ctx, param, value):
    if len(value) == 3:
        return value.upper()
    raise click.BadParameter("must be 3 uppercase letters")


@click.command(help="Cherche une sentence NMEA")
@click.argument("sentence", type=click.UNPROCESSED, callback=validate_sentence)
@click.argument("filename", type=Path)
def main(filename, sentence):
    for line in filename.open():
        _, nmea = line.rstrip().split(maxsplit=1)
        if nmea.startswith("$") and nmea[3:6] == sentence:
            print(nmea)


if __name__ == "__main__":
    main()
