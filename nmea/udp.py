#!/usr/bin/env python3


import logging

logging.getLogger("scapy.runtime").setLevel(logging.ERROR + 1)

import sys
from datetime import datetime
from pathlib import Path

import click
from scapy.all import IP, UDP, rdpcap


@click.command(help="Extrait les trames UDP port 11101 d'une capture (scapy version)")
@click.argument("filename")
@click.argument("output", default="")
def main(filename, output):
    if output == "-":
        out = sys.stdout
        print("output to stdout", file=sys.stderr)
    else:
        if output == "":
            output = Path(filename).with_suffix(".txt")
        else:
            output = Path(output)
        print(f"output to {output}")
        out = output.open("w")

    for p in rdpcap(filename):
        u = p / IP() / UDP()
        if u.sport == 11101 and u.len > 0:
            s = u.load.decode()
            for line in s.splitlines():
                timestamp = datetime.fromtimestamp(float(p.time)).isoformat()
                print(timestamp, line, file=out)


if __name__ == "__main__":
    main()
