#!/usr/bin/env python3

import re
import click


def _equal(a, b, precision=0.0001):
    return abs(a - b) < precision


def parse_dms(dms):
    """Convert degrees, minutes, seconds to decimal degrees."""

    sign = 1
    if "N" in dms or "E" in dms:
        sign = 1
    if "S" in dms or "W" in dms:
        sign = -1

    dms = dms.replace("h", "°")
    dms = dms.replace("m", "'")
    dms = dms.replace("s", '"')

    dms = dms.replace("''", '"')
    dms = dms.replace(",", ".")
    dms = dms.replace(" ", "")

    # 47° 30' 0"   47° 30' 0.0"
    r = re.search(r"(\d+)°(\d+)'(\d+(?:\.\d+)?)", dms)
    if r:
        d, m, s = r.groups()
        a = int(d) + int(m) / 60 + float(s) / 3600
        # print(r.groups(), a, sign)
        return sign * a

    # 47° 30'    47° 30.0'
    r = re.search(r"(\d+)°(\d+(?:\.\d+)?)'", dms)
    if r:
        d, m = r.groups()
        a = int(d) + float(m) / 60
        # print(r.groups(), a)
        return sign * a

    # 47°    47.0°
    r = re.search(r"(\d+(?:\.\d+)?)°", dms)
    if r:
        d = r.group(1)
        a = float(d)
        # print(r.groups(), a)
        return sign * a

    raise ValueError(f"Invalid dms: {dms}")


def to_dms(a, latitude=True):
    """Convert decimal degrees to degrees, minutes, seconds."""

    if latitude and a >= 0:
        sign = "N"
    elif latitude and a < 0:
        sign = "S"
        a = -a
    elif a >= 0:
        sign = "E"
    else:
        sign = "W"
        a = -a

    d = int(a)
    m = int(a * 60) % 60
    s = (a * 3600) % 60

    return f"{sign} {d}° {m}' {s:.3f}"


def to_dm(a, latitude=True):
    """Convert decimal degrees to degrees, minutes."""

    if latitude and a >= 0:
        sign = "N"
    elif latitude and a < 0:
        sign = "S"
        a = -a
    elif a >= 0:
        sign = "E"
    else:
        sign = "W"
        a = -a

    d = int(a)
    m = (a * 60) % 60

    return f"{sign} {d}° {m:.5f}'"


assert to_dms(47.5025, True) == "N 47° 30' 9.000"
assert to_dms(-3.50025, False) == "W 3° 30' 0.900"

assert to_dm(-47.5, True) == "S 47° 30.00000'"
assert to_dm(3.25, False) == "E 3° 15.00000'"

assert parse_dms("47° 30' 9.0\" N") == 47.5025
assert parse_dms("3° 30' 0.9\" W") == -3.50025

assert parse_dms("47° 30' N") == 47.5
assert parse_dms("47° 30.6' N") == 47.51

assert parse_dms("47°  S") == -47
assert parse_dms("3.25° E") == 3.25

assert _equal(parse_dms("12h 3m 51s"), 12.064166, 1e-6)
assert _equal(parse_dms("22h 38m"), 22.63333, 1e-5)


@click.command()
@click.argument("angle")
def main(angle):
    print(parse_dms(angle))


if __name__ == "__main__":
    main()
