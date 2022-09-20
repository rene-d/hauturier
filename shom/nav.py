#!/usr/bin/env python3

from tides import Tides


def main():
    # t = Tides()
    # t.plot("BREST", "2022-09-26", standalone=True, count=6)
    # t.save("brest.tex")

    t = Tides()
    t.nav(
        "2022-09-23",
        3,
        [
            "LANILDUT",
            "ABER_WRAC_H",
            "BRIGNOGAN",
            "ROSCOFF",
            "TREBEURDEN",
            "PERROS-GUIREC_TRESTRAOU",
            "TREGUIER",
            "BREHAT_MEN_JOLIGUET",
            "LEZARDRIEUX_PORT",
        ],
    )
    t.save("nav.tex")

    t.nav(
        "2022-09-26",
        6,
        [
            ############ LUNDI ############
            ["ROSCOFF", 0, 1],
            ["ABER_WRAC_H", 0, 2],  # 35
            ############ MARDI ############
            # "LANILDUT",
            ["OUESSANT_LAMPAUL", 1, 2],
            # "MOLENE_NORD",
            # "LE_CONQUET",
            # "BREST",
            ["CAMARET-SUR-MER", 1, 2],  # 36
            ############ MERCREDI ############
            ["DOUARNENEZ", 1, 2],
            ["ILE_DE_SEIN_NORD", 2, 2],
            ["AUDIERNE", 2, 2],  # 46
            ############ JEUDI ############
            # "BENODET",
            ["CONCARNEAU", 3, 2],  # 37
            ############ VENDREDI ############
            ["LORIENT", 4, 1],  # 30
        ],
    )
    t.save("nav2.tex")


if __name__ == "__main__":
    main()
