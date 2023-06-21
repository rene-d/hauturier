#!/usr/bin/env python3

import re
import socket
import time
from datetime import datetime

import click
from scapy.all import IP, UDP, rdpcap


def read_file(filename):
    if filename.endswith(".txt"):
        with open(filename, "rb") as f:
            for line in f:
                timestamp, data = line.split(b" ")
                timestamp = datetime.strptime(timestamp.decode(), "%Y-%m-%dT%H:%M:%S.%f").timestamp()
                yield timestamp, data
    else:
        for p in rdpcap(filename):
            u = p / IP() / UDP()
            if u.sport == 11101 and u.len > 0:
                yield p.time, u.load

    yield 2**63 - 1, b""


def nmea_checksum(sentence):
    checksum = 0
    for b in sentence[1:-3]:
        if b != b"I":
            checksum ^= b
    return sentence[:-2] + f"{checksum:02X}".encode()


def update_date(now, sentence):
    sentence = sentence.rstrip()

    if sentence[3:6] == b"RMC":
        f = sentence.split(b",")
        f[1] = f"{now.hour:02}{now.minute:02}{now.second:02}.{now.microsecond//10000:02}".encode()
        f[9] = f"{now.day:02}{now.month:02}{now.year%100:02}".encode()
        sentence = nmea_checksum(b",".join(f))

    if sentence[3:6] == b"ZDA":
        f = sentence.split(b",")
        f[1] = f"{now.hour:02}{now.minute:02}{now.second:02}.{now.microsecond//10000:02}".encode()
        f[2] = f"{now.day:02}".encode()
        f[3] = f"{now.month:02}".encode()
        f[4] = f"{now.year:04}".encode()
        sentence = nmea_checksum(b",".join(f))

    if sentence[3:6] == b"GGA":
        f = sentence.split(b",")
        f[1] = f"{now.hour:02}{now.minute:02}{now.second:02}.{now.microsecond//10000:02}".encode()
        sentence = nmea_checksum(b",".join(f))

    if sentence[3:6] == b"GRS":
        f = sentence.split(b",")
        f[1] = f"{now.hour:02}{now.minute:02}{now.second:02}.{now.microsecond//10000:02}".encode()
        print(sentence)
        sentence = nmea_checksum(b",".join(f))

    if sentence[3:6] == b"GLL":
        f = sentence.split(b",")
        f[5] = f"{now.hour:02}{now.minute:02}{now.second:02}.{now.microsecond//10000:02}".encode()
        sentence = nmea_checksum(b",".join(f))

    return sentence


@click.command(help="Rejoue les trames NMEA")
@click.option("-b", "--broadcast", is_flag=True, help="Envoyer les trames en broadcast")
@click.option("-p", "--port", type=int, default=11101, help="Port UDP")
@click.option("-a", "--address", type=str, default="localhost", help="Adresse de destination")
@click.option("-i", "--info", "opt_info", is_flag=True, help="Afficher les informations")
@click.option("-r", "--range", "opt_range", type=str, default=0, help="Numéro de plage")
@click.option("-s", "--speed", "opt_speed", type=click.IntRange(1, 10), default=1, help="Vitesse de rejeu")
@click.argument("filename")
def main(broadcast, port, address, opt_info, opt_range, opt_speed, filename):
    # ouvre la socket pour envoyer les trames
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    if broadcast:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # analyse l'option de plage
    plages = []
    for r in opt_range.split(","):
        m = re.match(
            r"""
        ^(\d+)$                     # uniquement numéro de plage
        |
        ^                           # avec plage horaire
        (?:
            (\d+)                   # numéro de plage (optionnel)
            :                       # séparateur plage:début-fin
        )?
        (?:                         # horaire début optionnel
            (\d+)                   # heure début
            (?:[Hh](\d*))?          # minutes début
        )?
        \-                          # séparateur début-fin
        (?:                         # horaire fin optionnel
            (\d+)                   # heure fin
            (?:[Hh](\d*))?          # minutes fin
        )?
        $""",
            r,
            re.VERBOSE,
        )

        try:
            if m is None:
                raise ValueError

            if m[1] is not None:
                plages.append((int(m[1]), 0, 24 * 60))
            else:
                plages.append(
                    (
                        int(m[2] or 0),  # numéro de plage
                        int(m[3] or 0) * 60 + int(m[4] or 0),  # heure début
                        int(m[5] or 24) * 60 + int(m[6] or 0),  # heure fin
                    )
                )

        except (ValueError, TypeError):
            click.echo("Erreur: plage invalide: « " + click.style(r, fg="red") + " »", color=True)
            return 1

    time_offset = None
    rattrapage = 0

    debut = 0
    fin = 0
    plage = 1
    nb = 0

    for ptime, data in read_file(filename):
        if debut == 0:
            debut = ptime
        else:
            if ptime - fin > 120:
                if opt_info:
                    print(
                        f"plage {plage:2} :",
                        datetime.fromtimestamp(debut).isoformat(),
                        datetime.fromtimestamp(fin).isoformat(),
                        f"{nb:6} {int(ptime - debut) if data else '':6}",
                    )
                plage += 1
                debut = ptime
                nb = 0
        fin = ptime
        nb += 1

        if opt_info:
            continue

        timestamp_orig = None

        if len(plages) != 0:
            for r in plages:
                if plage == r[0] or r[0] == 0:  # matche le numéro de plage
                    timestamp_orig = datetime.fromtimestamp(float(ptime))
                    minutes = timestamp_orig.hour * 60 + timestamp_orig.minute

                    if minutes >= r[1] and minutes < r[2]:  # matche la plage horaire
                        break
            else:
                continue

        if not timestamp_orig:
            timestamp_orig = datetime.fromtimestamp(float(ptime))

        now = datetime.now()
        now_rattrapage = now.timestamp() + rattrapage
        if time_offset is None:
            time_offset = now_rattrapage - float(ptime)

        delay = float(ptime) + time_offset - now_rattrapage
        if delay > 30:
            rattrapage += delay - 30
            print()
            print(f"Delay {delay}s")
            print()
            delay = 10

        if delay > 0:
            rattrapage += delay * (opt_speed - 1) / 10
            delay *= (11 - opt_speed) / 10
            time.sleep(delay)

        timestamp = datetime.fromtimestamp(float(ptime) + time_offset).isoformat()

        msg = repr(data.decode())
        if len(msg) > 40:
            msg = msg[:38] + "…'"
        click.echo(timestamp + " " + click.style(timestamp_orig.isoformat(), fg="blue") + f" send {msg}")

        # data = b"\r\n".join(update_date(now, d) for d in data.split(b"\n"))+b"\r\n"

        if broadcast:
            sock.sendto(data, ("<broadcast>", port))
        else:
            sock.sendto(data, (address, port))


if __name__ == "__main__":
    main()
