#!/usr/bin/env python3
"""Convertit Maeva.plist (NSKeyedArchiver) vers le format .pol."""

import plistlib
import struct
import sys

def load_plist(path):
    with open(path, 'rb') as f:
        return plistlib.load(f)

def deref(objs, x):
    if isinstance(x, dict) and 'CF$UID' in x:
        return objs[x['CF$UID']]
    return x

def ns_dict(objs, d):
    keys = [deref(objs, k) for k in d['NS.keys']]
    vals = [deref(objs, v) for v in d['NS.objects']]
    return dict(zip(keys, vals))

def ns_array(objs, a):
    return [deref(objs, x) for x in a['NS.objects']]

def decode_f32(data):
    b = bytes(data)
    n = len(b) // 4
    return list(struct.unpack(f'<{n}f', b))

def fmt_speed(v):
    if abs(v) < 0.05:
        return '0'
    return f'{v:.1f}'

def fmt_tws(v):
    return str(int(v)) if v == int(v) else f'{v:.1f}'

def fmt_twa(v):
    return f'{v:.1f}'

def convert(plist_path):
    plist = load_plist(plist_path)
    objs  = plist['$objects']

    root    = deref(objs, plist['$top']['root'])
    root_d  = ns_dict(objs, root)
    polars  = ns_array(objs, root_d['polars'])

    for polar in polars:
        p = ns_dict(objs, polar)

        tws        = decode_f32(p['tws'])       # 11 valeurs
        twa        = decode_f32(p['twa'])       # 37 valeurs
        pd         = decode_f32(p['polarData']) # 37 × 11 valeurs, row-major

        n_tws = len(tws)
        n_twa = len(twa)
        matrix = [pd[i * n_tws:(i + 1) * n_tws] for i in range(n_twa)]

        # En-tête
        print('TWA\\TWS;' + ';'.join(fmt_tws(t) for t in tws))

        # Lignes
        for angle, row in zip(twa, matrix):
            print(fmt_twa(angle) + ';' + ';'.join(fmt_speed(s) for s in row))

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'Maeva.plist'
    convert(path)
