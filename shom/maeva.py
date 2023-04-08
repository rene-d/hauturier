#!/usr/bin/env python3

from tides import Tides
import os


def main():
    t = Tides()
    t.nav(
        "2023-04-15",
        3,
        [
            "ROSCOFF",
            "TREBEURDEN",
            "PERROS-GUIREC_TRESTRAOU",
            "TREGUIER",
            "BREHAT_MEN_JOLIGUET",
            "LEZARDRIEUX_PORT",
        ],
    )
    t.save("nav.tex")
    os.system("texfot lualatex -output-format=pdf -interaction=nonstopmode nav.tex && open nav.pdf")


if __name__ == "__main__":
    main()
