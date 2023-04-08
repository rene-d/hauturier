#!/usr/bin/env python3

from tides import Tides
import os


def main():
    t = Tides()
    t.nav(
        "2023-03-17",
        3,
        [
            "LE_HAVRE",
        ],
    )
    t.save("nav.tex")
    os.system("texfot lualatex -output-format=pdf -interaction=nonstopmode nav.tex && open nav.pdf")


if __name__ == "__main__":
    main()
