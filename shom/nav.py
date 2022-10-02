#!/usr/bin/env python3

from tides import Tides


def main():
    t = Tides()
    t.nav(
        "2022-09-26",
        6,
        [
            ["ROSCOFF", 0, 2],
            ["ABER_WRAC_H", 1, 2],
            ["OUESSANT_LAMPAUL", 1, 2],
            ["LE_CONQUET", 1, 2],
            ["CAMARET-SUR-MER", 1, 3],
            ["ILE_DE_SEIN_NORD", 1, 3],
            ["CONCARNEAU", 3, 2],
            ["LORIENT", 3, 2],
        ],
    )
    t.save("nav.tex")


if __name__ == "__main__":
    main()
