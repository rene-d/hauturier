#!/usr/bin/env python3

# NMEA reference: https://gpsd.gitlab.io/gpsd/NMEA.html
# AIS info: https://gpsd.gitlab.io/gpsd/AIVDM.html

from collections import defaultdict
from pathlib import Path

import click

TALKER_IDS = {
    "GP": "Global Positioning System",
    "YD": "Transducer - Displacement, Angular or Linear (obsolete)",
}

SENTENCES = {
    "GLL": "Geographic Position - Latitude/Longitude",
    "GRS": "GPS Range Residuals",
    "MTW": "Mean Temperature of Water",
    "MWV": "Wind Speed and Angle",
    "DBT": "Depth below transducer",
    "ROT": "Rate Of Turn",
    "GSV": "Satellites in view",
    "ZDA": "Time & Date - UTC, day, month, year and local time zone",
    "HDM": "Heading Magnetic",
    "VLW": "Distance Traveled through Water",
    "VDR": "Set and Drift",
    "VTG": "Track made good and Ground speed",
    "RMC": "Recommended Minimum Navigation Information",
    "HDG": "Heading - Deviation & Variation",
    "RSA": "Rudder Sensor Angle",
    "MDA": "Meteorological Composite",
    "GGA": "Global Positioning System Fix Data",
    "HDT": "Heading - True",
    "DBS": "Depth Below Surface",
    "MWD": "Wind Direction & Speed",
    "DPT": "Depth of Water",
    "VWR": "Relative Wind Speed & Angle",
    "XDR": "Transducer Measurement",
    "VHW": "Water Speed and Heading",
    "DTM": "Datum Reference",
    "VWT": "True Wind Speed and Angle",
    "BWR": "Bearing and Distance to Waypoint - Rhumb Line",
    "RMB": "Recommended Minimum Navigation Information",
    "BOD": "Bearing - Waypoint to Waypoint",
    "XTE": "Cross-Track Error, Measured",
    "APB": 'Autopilot Sentence "B"',
}


@click.command(help="Stats trames NMEA")
@click.argument("filename")
def main(filename):
    filename = Path(filename)

    talker_ids = defaultdict(int)
    sentences = defaultdict(int)
    ais = defaultdict(int)

    for line in filename.open():
        _, nmea = line.split(" ", 1)
        tag = nmea.split(",", 1)[0]

        if tag.startswith("$"):
            talker_ids[tag[1:3]] += 1
            sentences[tag[3:6]] += 1
        elif tag.startswith("!AI"):  # Mobile AIS station
            ais[tag[1:6]] += 1
        else:
            print(f"UNKNOWN TAG {nmea}")
            exit(2)

    print("Talker IDs:")
    for talker_id, count in talker_ids.items():
        print(f"  {talker_id}   {TALKER_IDS[talker_id]:<62} {count:6}")

    print("Sentences:")
    for sentence, count in sentences.items():
        print(f"  {sentence}  {SENTENCES[sentence]:<62} {count:6}")

    print("AIS:")
    for msg, count in ais.items():
        print(f"  {msg}  {'':<60} {count:6}")


if __name__ == "__main__":
    main()
