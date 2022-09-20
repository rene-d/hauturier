#!/usr/bin/env python3

import json
import locale
import re
from datetime import datetime, timedelta
from pathlib import Path

from dateutil import tz

from ephem import ephem

# from spm import SPM
from hdm import SPM, Harbors
from oceano import Oceano, Spots

try:
    locale.setlocale(locale.LC_TIME, "fr_FR")
except locale.Error:
    pass


def _(text, values):
    """
    Format a string with @oid@ markups.
    Examples:
        _("@3@ @4.1@ @5.a@", [1, 2, 3, 4, [5, 6], {"a": 7}]) == "4 6 7"
        _("@a@ @b.1@ @c.d.e@ @d.0.e.1@", {"a": 1, "b": [1, 2], "c": {"d": {"e": 3}}, "d": [{"e": [3, 4]}]}) == "1 2 3 4"
    """

    def value(k):
        """Find a value by its oid."""
        v = values
        for e in k.split("."):
            if isinstance(v, list) and e.isdigit() and 0 <= int(e) < len(v):
                v = v[int(e)]
            elif isinstance(v, dict):
                v = v.get(e)
                if not v:
                    return
            else:
                return
        return str(v)

    return re.sub(r"@([\w\._]+)@", lambda x: value(x[1]), text)


class Tides:
    def __init__(self) -> None:
        self.harbors = Harbors()
        self.lines = []
        self.spm = SPM()
        self.cache = None
        self.spots = Spots(exact=False)

    def add(self, text, values=None):
        if values is None:
            self.lines.append(text)
        else:
            self.lines.append(_(text, values))

    def save(self, filename):
        Path(filename).write_text("\n".join(self.lines))

    def print(self):
        print("\n".join(self.lines))

    def ephem(self, latitude, longitude, date):
        if self.cache is None:
            if Path("ephem.json").is_file():
                self.cache = json.loads(Path("ephem.json").read_bytes())
            else:
                self.cache = {}

        key = f"{latitude},{longitude},{date}"
        v = self.cache.get(key)
        if v:
            return v

        v = ephem(latitude, longitude, None, date)
        local_zone = tz.tzlocal()
        w = {
            "sun": {
                "rise": v["sun"]["rise"].astimezone(local_zone).strftime("%H:%M"),
                "set": v["sun"]["set"].astimezone(local_zone).strftime("%H:%M"),
            }
        }
        self.cache[key] = w
        Path("ephem.json").write_text(json.dumps(self.cache, indent=2))
        return w

    def day(self, harbor, date_ymd: datetime, show_harbour=True):
        """Crée un tableau avec les marées du jour."""

        harbor = self.harbors[harbor]

        e = self.ephem(harbor["lat"], harbor["lon"], date_ymd.strftime("%Y-%m-%d"))
        harbor_name = harbor["toponyme"]

        _, _, hlt = self.spm.hlt(harbor["cst"], date_ymd)

        r = self.spots.filter(harbor_name)
        if len(r) == 0:
            url = Oceano().html(lat=harbor["lat"], lon=harbor["lon"])
        else:
            url = Oceano().html(spot=r[0]["cst"])

        if show_harbour:
            self.add(
                r"""
\begin{tabular}{|c|c c c c|}\hline
\multirow{6}{1.8em}{\rotatebox[origin=c]{90}{
\parbox[c]{1.5cm}{\centering \href{@url@}{@harbor_name@}}}}
& \multicolumn{4}{c|}{@date_ymd@} \\
\cline{2-5}
""",
                {"date_ymd": date_ymd.strftime("%a %Y-%m-%d"), "harbor_name": harbor_name, "url": url},
            )
        else:
            self.add(
                r"""
\begin{tabular}{|c c c c|}\hline
\multicolumn{4}{|c|}{@date_ymd@} \\
\hline""",
                {"date_ymd": date_ymd.strftime("%a %Y-%m-%d")},
            )

        for tide, hour, height, coeff in hlt:
            tide = {
                "tide.high": "PM",
                "tide.low": "BM",
                "tide.none": "--",
            }[tide]

            sep = "& " if show_harbour else ""

            self.add(rf"{sep}{tide} & {hour} & {height} & {coeff} \\")

        if show_harbour:
            self.add(r"\cline{2-5}")
        else:
            self.add(r"\cline{1-4}")

        self.add(
            sep + r"Lever & @sunrise@ & Coucher & @sunset@ \\",
            {
                "sunrise": e["sun"]["rise"],
                "sunset": e["sun"]["set"],
            },
        )

        self.add(r"\hline\end{tabular}")

    def day_multiple(self, harbor, start, days=3):
        """Crée un tableau avec plusieurs jours consécutifs."""

        if isinstance(start, str):
            start = datetime.strptime(start, "%Y-%m-%d")

        self.add(r"\begin{tabular}{" + "c " * days + "}")

        self.day(harbor, start, True)
        for i in range(1, days):
            self.add(r"&")
            self.day(harbor, start + timedelta(i), False)
        self.add(r"\\")

        self.add(r"\end{tabular}")

    def plot(self, harbor, date_ymd: datetime, count=1, standalone=False):

        if isinstance(date_ymd, str):
            date_ymd = datetime.strptime(date_ymd, "%Y-%m-%d")

        if standalone:
            self.lines.clear()
            self.add(
                r"""\documentclass{standalone}
\usepackage{pgfplots}
\pgfplotsset{compat = newest}
\usepgfplotslibrary{dateplot}
\usepackage{multirow}
\usepackage{rotating}
\usepackage{filecontents}
\usepackage{pgfplots, pgfplotstable}

\begin{document}
    """
            )

        self.add(
            r"""
%\resizebox{5cm}{!}{
\begin{tikzpicture}
\begin{axis}[
    xmin = @date_min@ 00:00:00, xmax = @date_max@ 00:00:00,
    date coordinates in=x,
    xtick distance = 0.125,
    xticklabel style={rotate=90},
    xticklabel={\hour:\minute},
    ymin = 0, ymax = 10.0,
    ytick distance = 1,
    yticklabel=\pgfkeys{/pgf/number format/.cd,fixed,precision=0,zerofill}\pgfmathprintnumber{\tick}{ m},
    grid = both,
    minor tick num = 1,
    major grid style = {lightgray},
    minor grid style = {lightgray!25},
    width = \textwidth,
    height = 0.5\textwidth,]

\addplot[
    smooth,
    thin,
    red,
    dashed
]  coordinates {
""",
            {
                "date_min": date_ymd.strftime("%Y-%m-%d"),
                "date_max": (date_ymd + timedelta(days=count)).strftime("%Y-%m-%d"),
            },
        )

        for day in range(count):
            d = date_ymd + timedelta(days=day)
            wl = self.spm.wl(harbor, d)
            for time, height in wl:
                self.add(f"({d.strftime('%Y-%m-%d')} {time}, {height})")

        self.add(r"};")

        for day in range(1, count):
            self.add(
                r"""
\addplot[mark=none, draw=blue, line width=1pt] coordinates { (@date@ 00:00:00, 0) (@date@ 00:00:00, 10) };
""",
                {"date": (date_ymd + timedelta(day)).strftime("%Y-%m-%d")},
            )

        self.add(
            r"""
\end{axis}
\end{tikzpicture}
%}
"""
        )

        if standalone:
            self.add(r"""\end{document}""")

    def nav(self, start, count, stages):
        print(f"nav {start} {count} jours")

        start = datetime.strptime(start, "%Y-%m-%d")

        self.lines.clear()
        self.add(
            r"""\documentclass{article}
% \usepackage[T1]{fontenc}
\usepackage{tgbonum}
\usepackage{geometry}
\geometry{
a4paper,
total={190mm,277mm},
left=10mm,
top=10mm,
}
\usepackage{pgfplots}
\pgfplotsset{compat = newest}
\usepgfplotslibrary{dateplot}
\usepackage{multirow}
\usepackage{rotating}
\usepackage{pgfplots, pgfplotstable}
\usepackage{longtable}
\usepackage{hyperref}

\setlength\parindent{0pt}
\pagenumbering{gobble}

\usepackage{eso-pic,graphicx}

\AddToShipoutPicture{
\unitlength=1cm
\put(9.5,0.7){\includegraphics[height=1.3cm]{shom}}}

\setlength\LTleft{0pt}
\setlength\LTright{0pt}

\begin{document}
%{\fontfamily{qcr}\selectfont
"""
        )

        def _add(stage):
            nonlocal start, count
            if isinstance(stage, str):
                self.day_multiple(stage, start, count)
            else:
                stage, offset, stage_count = stage
                self.day_multiple(stage, start + timedelta(offset), stage_count)
            self.add(r"\\")

        self.add(r" ")

        self.add(r"  \begin{longtable}{l}")

        _add(stages[0])

        for stage in stages[1:]:
            self.add(r"\\")
            _add(stage)

        self.add(r"\\")
        self.add(r"\end{longtable} ")

        self.add(r"%}")
        self.add(r"\end{document}")


if __name__ == "__main__":
    t = Tides()
    t.plot("BREST", "2022-09-26", standalone=True, count=6)
    t.save("brest.tex")

    t = Tides()
    t.nav("2022-09-26", 3, ["ROSCOFF"])
    t.save("nav.tex")
