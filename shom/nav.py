#!/usr/bin/env python3

from tides import Tides


def main():
    t = Tides()
    t.nav(
        "2022-10-22",
        3,
        [
            "LE_CROUESTY",
            "VANNES",
            "HOUAT",
            "HOEDIC",
            "LE_PALAIS",
            "LE_CROISIC",
            "LA_TRINITE-SUR-MER",
            "PORT-MARIA",
        ],
    )
    t.save("nav.tex")


if __name__ == "__main__":
    main()
