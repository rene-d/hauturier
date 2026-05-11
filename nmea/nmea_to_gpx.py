#!/usr/bin/env python3
"""Convert NMEA logs (.bin) to a single GPX file.

Each .bin file becomes one <trkseg>. Uses $GPRMC for position/time/validity
and $GPGGA for altitude (matched by timestamp).
"""

import glob
import os
import re
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent


def nmea_checksum_ok(sentence):
    """Verify NMEA checksum (the *XX part)."""
    match = re.match(r'^\$(.+)\*([0-9A-Fa-f]{2})$', sentence.strip())
    if not match:
        return False
    data, checksum = match.group(1), match.group(2)
    calc = 0
    for ch in data:
        calc ^= ord(ch)
    return calc == int(checksum, 16)


def parse_coord(value, direction):
    """Convert NMEA DDMM.MMMM + N/S/E/W to decimal degrees."""
    if not value:
        return None
    # Latitude: DDMM.MMMM  /  Longitude: DDDMM.MMMM
    dot = value.index('.')
    deg = float(value[:dot - 2])
    minutes = float(value[dot - 2:])
    decimal = deg + minutes / 60.0
    if direction in ('S', 'W'):
        decimal = -decimal
    return decimal


def extract_sentences(path):
    """Yield NMEA sentence strings from a binary file."""
    with open(path, 'rb') as f:
        data = f.read()
    text = data.decode('ascii', errors='replace')
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('$GP'):
            yield line


def parse_file(path):
    """Return list of dicts with keys: lat, lon, ele, time (datetime UTC)."""
    # First pass: collect GGA altitudes keyed by hhmmss
    altitudes = {}
    rmc_rows = []

    for sentence in extract_sentences(path):
        if not nmea_checksum_ok(sentence):
            continue
        fields = sentence.split(',')
        msg_type = fields[0]

        if msg_type == '$GPGGA' and len(fields) >= 10:
            time_str = fields[1][:6]   # hhmmss
            alt_str  = fields[9]
            if alt_str:
                try:
                    altitudes[time_str] = float(alt_str)
                except ValueError:
                    pass

        elif msg_type == '$GPRMC' and len(fields) >= 10:
            status   = fields[2]       # A=valid, V=void
            time_raw = fields[1]       # hhmmss.ss
            date_raw = fields[9]       # ddmmyy
            lat_val  = fields[3]
            lat_dir  = fields[4]
            lon_val  = fields[5]
            lon_dir  = fields[6]

            if status != 'A' or not lat_val or not lon_val:
                continue
            if len(date_raw) < 6 or len(time_raw) < 6:
                continue

            try:
                lat = parse_coord(lat_val, lat_dir)
                lon = parse_coord(lon_val, lon_dir)
                dt = datetime(
                    year   = 2000 + int(date_raw[4:6]),
                    month  = int(date_raw[2:4]),
                    day    = int(date_raw[0:2]),
                    hour   = int(time_raw[0:2]),
                    minute = int(time_raw[2:4]),
                    second = int(time_raw[4:6]),
                    tzinfo = timezone.utc,
                )
            except (ValueError, IndexError):
                continue

            rmc_rows.append({
                'lat':      lat,
                'lon':      lon,
                'time':     dt,
                'time_key': time_raw[:6],
            })

    # Merge altitude
    points = []
    for row in rmc_rows:
        row['ele'] = altitudes.get(row['time_key'])
        points.append(row)

    return points


def build_gpx(all_segments):
    """Build a GPX ElementTree from a list of (name, [points]) segments."""
    gpx = Element('gpx', attrib={
        'version': '1.1',
        'creator': 'nmea_to_gpx.py',
        'xmlns':              'http://www.topografix.com/GPX/1/1',
        'xmlns:xsi':          'http://www.w3.org/2001/XMLSchema-instance',
        'xsi:schemaLocation': ('http://www.topografix.com/GPX/1/1 '
                               'http://www.topografix.com/GPX/1/1/gpx.xsd'),
    })

    trk = SubElement(gpx, 'trk')
    SubElement(trk, 'name').text = 'GPS Log'

    for seg_name, points in all_segments:
        if not points:
            continue
        trkseg = SubElement(trk, 'trkseg')
        for p in points:
            trkpt = SubElement(trkseg, 'trkpt', attrib={
                'lat': f"{p['lat']:.8f}",
                'lon': f"{p['lon']:.8f}",
            })
            if p.get('ele') is not None:
                SubElement(trkpt, 'ele').text = f"{p['ele']:.1f}"
            SubElement(trkpt, 'time').text = p['time'].strftime('%Y-%m-%dT%H:%M:%SZ')

    return gpx


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bin_files = sorted(glob.glob(os.path.join(base_dir, '*.bin')))

    if not bin_files:
        print("No .bin files found.")
        return

    total_points = 0
    all_segments = []

    for path in bin_files:
        name = os.path.basename(path)
        points = parse_file(path)
        all_segments.append((name, points))
        print(f"  {name}: {len(points)} valid points")
        total_points += len(points)

    print(f"\nTotal: {total_points} points across {len(bin_files)} files")

    gpx = build_gpx(all_segments)
    indent(gpx, space='  ')

    out_path = os.path.join(base_dir, 'output.gpx')
    tree = ElementTree(gpx)
    tree.write(out_path, encoding='utf-8', xml_declaration=True)
    print(f"Written → {out_path}")


if __name__ == '__main__':
    main()
