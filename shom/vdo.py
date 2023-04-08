#!/usr/bin/env python3

from tides import Tides
import os


def main():
    t = Tides()
    t.nav(
        "2023-04-22",
        3,
        [
            "LE_CROUESTY",
            "VANNES",
            "HOUAT",
            "HOEDIC",
            "LE_PALAIS",
            "LA_TRINITE-SUR-MER",
            "PORT-MARIA",
            "LE_CROISIC",
        ],
    )
    t.save("nav.tex")
    os.system("texfot lualatex -output-format=pdf -interaction=nonstopmode nav.tex && open nav.pdf")


if __name__ == "__main__":
    main()
