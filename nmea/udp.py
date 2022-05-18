#!/usr/bin/env python3

from scapy.all import rdpcap, IP, UDP
from pathlib import Path
import click
import sys
from datetime import datetime


@click.command(help="Extrait les trames UDP sport 1456 d'une capture")
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
        if u.sport == 1456 and u.len > 0:
            s = u.load.decode()
            for line in s.splitlines():
                timestamp = datetime.fromtimestamp(float(p.time)).isoformat()
                print(timestamp, line, file=out)


if __name__ == "__main__":
    main()