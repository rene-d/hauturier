#!/usr/bin/env python3

import numpy as np
import json, re, os, sys
import typing as t
from collections import defaultdict
from datetime import datetime, timedelta, UTC
from pathlib import Path
import turtle
from PIL import Image, ImageDraw
from imgcat import imgcat

import re
from typing import List, Tuple, Dict

from shapely import LineString, Point

from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import PDFStream


# Définir une structure pour stocker les instructions
class PDFCommand:
    def __init__(self, operator: str, operands: List[str]):
        self.operator = operator
        self.operands = operands

    def __repr__(self):
        return f"{self.operands} {self.operator}"


# Liste des opérateurs graphiques simples à reconnaître
PDF_OPERATORS = {
    "m": "moveto",
    "l": "lineto",
    "S": "stroke",
    "f": "fill",
    "q": "save",
    "Q": "restore",
    "w": "Définit l'épaisseur du trait",
    "RG": "Définit la couleur de trait en RGB",
    "rg": "Définit la couleur de remplissage en RGB",
    "re": "rectangle (x y width height)",
    "c": "Bézier cubique (2 points de contrôle)",
    "h": "closePath",
    "n": "aucune peinture",
}


def parse_pdf_stream(stream_text: str) -> List[PDFCommand]:
    """
    Parse un flux vectoriel PDF en liste d'instructions.
    """
    tokens = stream_text.strip().split()
    commands = []
    stack = []

    skip_bt_et = False
    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token == "BT":
            skip_bt_et = True

        elif token == "ET" and skip_bt_et:
            skip_bt_et = False

        elif skip_bt_et:
            pass

        elif token in PDF_OPERATORS:
            # C'est un opérateur : ce qui précède sont les opérandes
            commands.append(PDFCommand(token, stack))
            stack = []
        else:
            # Sinon, on suppose que c’est un opérande
            stack.append(token)
        i += 1

    return commands


def check_collinearity(line: LineString, tol=1e-8) -> bool:
    points = np.array(line.coords)
    if len(points) < 2:
        return True  # Moins de 2 points = toujours colinéaires

    # Crée les vecteurs entre le premier point et les autres
    base_point = points[0]
    vectors = points[1:] - base_point

    # En 2D ou 3D, on peut utiliser le produit vectoriel
    if points.shape[1] == 2:
        ref = vectors[0]
        for v in vectors[1:]:
            cross = ref[0] * v[1] - ref[1] * v[0]
            if abs(cross) > tol:
                return False
        return True

    raise ValueError


def segments(line: LineString) -> t.List[LineString]:
    return list(map(LineString, zip(line.coords[:-1], line.coords[1:])))


im = Image.new("RGB", (6000, 10000), (255, 255, 255))
draw = ImageDraw.Draw(im)


twa_lines = []
vpp = []


fill = (0, 0, 0)


fname = "Polar_curves_-_Sun_Odyssey_419_-_Std_keel_-_140%_Genoa_+_Code_0.pdf"
fp = open(fname, "rb")
parser = PDFParser(fp)
doc = PDFDocument(parser, None)
objids = (objid for xref in doc.xrefs for objid in xref.get_objids())

for objid in sorted(objids):
    obj = doc.getobj(objid)
    if isinstance(obj, PDFStream):

        stream = obj.get_data().decode(errors="ignore")

        # uniquement {'Filter': /'FlateDecode', 'Length': XXX}
        if len(obj.attrs) != 2:
            continue

        parsed = parse_pdf_stream(stream)

        # print(parsed)
        #     lines = stream.splitlines()
        #     im = Image.new("RGB", (6000, 10000))
        #     draw = ImageDraw.Draw(im)

        line = []

        for cmd in parsed:
            if cmd.operator == "m":
                line.clear()
                geom, y = map(float, cmd.operands)
                line.append((round(geom * 10), round(y * 10)))

            if cmd.operator == "l":
                geom, y = map(float, cmd.operands)
                line.append((round(geom * 10), round(y * 10)))

            if cmd.operator == "S":

                if len(line) > 10 or fill == (0, 0, 0):
                    geom = LineString(line)
                    if fill == (0, 0, 0):
                        for y in segments(geom):
                            a, b = map(lambda p: complex(*p), y.coords)
                            if a.real > b.real:
                                a, b = b, a
                            twa = round(90 - np.angle(b - a, deg=True))

                            if y.length > 1000:
                                twa_lines.append((twa, y))
                                draw.line(y.coords, fill=fill, width=10)

                    else:
                        draw.line(line, fill=fill, width=20)
                        vpp.append(LineString(line))

                    # print(line)

            if cmd.operator == "RG":
                fill = tuple(map(lambda x: round(255 * float(x)), cmd.operands))


im = im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

# im.save("zz.png")

imgcat(im.resize((600, 1000)), height=40)

pts = defaultdict(lambda: 0)
for _, i in twa_lines:
    i: LineString
    pts[i.coords[0]] += 1
    pts[i.coords[1]] += 1

center = Point(max((n, pt) for pt, n in pts.items())[1])
print(center)

twa_map = {}

for twa, i in twa_lines:
    if i.coords[0] == center.coords[0] or i.coords[1] == center.coords[0]:
        twa_map[twa] = i


for twa in sorted(twa_map):
    s = []
    for i in vpp:
        p = i.intersection(twa_map[twa])
        if p:
            p -= center
            d = abs(complex(*p.coords[0]))
            s.append(d)
    print(twa, sorted(s))
