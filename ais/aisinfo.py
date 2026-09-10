"""Tables de correspondance AIS : MID, types de navire, statuts, aides à la navigation.

Aucune dépendance : ce module est importé par `aismap.py` pour transformer les
champs bruts décodés par pyais en libellés lisibles.

Références : ITU-R M.585 (MMSI/MID), ITU-R M.1371 (types, statuts, EPFD, AtoN),
IMO SN.1/Circ.289 (message 8 DAC=1 FID=31, valeurs « non disponible »).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# MID -> pays (ITU-R M.585)
# ---------------------------------------------------------------------------

MID: dict[str, str] = {
    "201": "Albanie", "202": "Andorre", "203": "Autriche", "204": "Açores",
    "205": "Belgique", "206": "Biélorussie", "207": "Bulgarie", "208": "Vatican",
    "209": "Chypre", "210": "Chypre", "211": "Allemagne", "212": "Chypre",
    "213": "Géorgie", "214": "Moldavie", "215": "Malte", "216": "Arménie",
    "218": "Allemagne", "219": "Danemark", "220": "Danemark", "224": "Espagne",
    "225": "Espagne", "226": "France", "227": "France", "228": "France",
    "229": "Malte", "230": "Finlande", "231": "Îles Féroé", "232": "Royaume-Uni",
    "233": "Royaume-Uni", "234": "Royaume-Uni", "235": "Royaume-Uni",
    "236": "Gibraltar", "237": "Grèce", "238": "Croatie", "239": "Grèce",
    "240": "Grèce", "241": "Grèce", "242": "Maroc", "243": "Hongrie",
    "244": "Pays-Bas", "245": "Pays-Bas", "246": "Pays-Bas", "247": "Italie",
    "248": "Malte", "249": "Malte", "250": "Irlande", "251": "Islande",
    "252": "Liechtenstein", "253": "Luxembourg", "254": "Monaco", "255": "Madère",
    "256": "Malte", "257": "Norvège", "258": "Norvège", "259": "Norvège",
    "261": "Pologne", "262": "Monténégro", "263": "Portugal", "264": "Roumanie",
    "265": "Suède", "266": "Suède", "267": "Slovaquie", "268": "Saint-Marin",
    "269": "Suisse", "270": "Tchéquie", "271": "Turquie", "272": "Ukraine",
    "273": "Russie", "274": "Macédoine du Nord", "275": "Lettonie",
    "276": "Estonie", "277": "Lituanie", "278": "Slovénie", "279": "Serbie",
    "301": "Anguilla", "303": "Alaska", "304": "Antigua-et-Barbuda",
    "305": "Antigua-et-Barbuda", "306": "Antilles néerlandaises", "307": "Aruba",
    "308": "Bahamas", "309": "Bahamas", "310": "Bermudes", "311": "Bahamas",
    "312": "Belize", "314": "Barbade", "316": "Canada", "319": "Îles Caïmans",
    "321": "Costa Rica", "323": "Cuba", "325": "Dominique",
    "327": "République dominicaine", "329": "Guadeloupe", "330": "Grenade",
    "331": "Groenland", "332": "Guatemala", "334": "Honduras", "336": "Haïti",
    "338": "États-Unis", "339": "Jamaïque", "341": "Saint-Kitts-et-Nevis",
    "343": "Sainte-Lucie", "345": "Mexique", "347": "Martinique",
    "348": "Montserrat", "350": "Nicaragua", "351": "Panama", "352": "Panama",
    "353": "Panama", "354": "Panama", "355": "Panama", "356": "Panama",
    "357": "Panama", "358": "Porto Rico", "359": "Salvador",
    "361": "Saint-Pierre-et-Miquelon", "362": "Trinité-et-Tobago",
    "364": "Îles Turques-et-Caïques", "366": "États-Unis", "367": "États-Unis",
    "368": "États-Unis", "369": "États-Unis", "370": "Panama", "371": "Panama",
    "372": "Panama", "373": "Panama", "374": "Panama",
    "375": "Saint-Vincent-et-les-Grenadines", "376": "Saint-Vincent-et-les-Grenadines",
    "377": "Saint-Vincent-et-les-Grenadines", "378": "Îles Vierges britanniques",
    "379": "Îles Vierges américaines",
    "401": "Afghanistan", "403": "Arabie saoudite", "405": "Bangladesh",
    "408": "Bahreïn", "410": "Bhoutan", "412": "Chine", "413": "Chine",
    "414": "Chine", "416": "Taïwan", "417": "Sri Lanka", "419": "Inde",
    "422": "Iran", "423": "Azerbaïdjan", "425": "Irak", "428": "Israël",
    "431": "Japon", "432": "Japon", "434": "Turkménistan", "436": "Kazakhstan",
    "437": "Ouzbékistan", "438": "Jordanie", "440": "Corée du Sud",
    "441": "Corée du Sud", "443": "Palestine", "445": "Corée du Nord",
    "447": "Koweït", "450": "Liban", "451": "Kirghizistan", "453": "Macao",
    "455": "Maldives", "457": "Mongolie", "459": "Népal", "461": "Oman",
    "463": "Pakistan", "466": "Qatar", "468": "Syrie",
    "470": "Émirats arabes unis", "471": "Émirats arabes unis", "472": "Tadjikistan",
    "473": "Yémen", "475": "Yémen", "477": "Hong Kong", "478": "Bosnie-Herzégovine",
    "501": "Terre Adélie", "503": "Australie", "506": "Birmanie", "508": "Brunei",
    "510": "Micronésie", "511": "Palaos", "512": "Nouvelle-Zélande",
    "514": "Cambodge", "515": "Cambodge", "516": "Île Christmas",
    "518": "Îles Cook", "520": "Fidji", "523": "Îles Cocos", "525": "Indonésie",
    "529": "Kiribati", "531": "Laos", "533": "Malaisie",
    "536": "Îles Mariannes du Nord", "538": "Îles Marshall",
    "540": "Nouvelle-Calédonie", "542": "Niue", "544": "Nauru",
    "546": "Polynésie française", "548": "Philippines", "550": "Timor oriental",
    "553": "Papouasie-Nouvelle-Guinée", "555": "Îles Pitcairn",
    "557": "Îles Salomon", "559": "Samoa américaines", "561": "Samoa",
    "563": "Singapour", "564": "Singapour", "565": "Singapour", "566": "Singapour",
    "567": "Thaïlande", "570": "Tonga", "572": "Tuvalu", "574": "Viêt Nam",
    "576": "Vanuatu", "577": "Vanuatu", "578": "Wallis-et-Futuna",
    "601": "Afrique du Sud", "603": "Angola", "605": "Algérie",
    "607": "Îles Saint-Paul", "608": "Ascension", "609": "Burundi", "610": "Bénin",
    "611": "Botswana", "612": "Centrafrique", "613": "Cameroun", "615": "Congo",
    "616": "Comores", "617": "Cap-Vert", "618": "Terres australes françaises",
    "619": "Côte d'Ivoire", "620": "Comores", "621": "Djibouti", "622": "Égypte",
    "624": "Éthiopie", "625": "Érythrée", "626": "Gabon", "627": "Ghana",
    "629": "Gambie", "630": "Guinée-Bissau", "631": "Guinée équatoriale",
    "632": "Guinée", "633": "Burkina Faso", "634": "Kenya", "635": "Kerguelen",
    "636": "Liberia", "637": "Liberia", "638": "Soudan du Sud", "642": "Libye",
    "644": "Lesotho", "645": "Maurice", "647": "Madagascar", "649": "Mali",
    "650": "Mozambique", "654": "Mauritanie", "655": "Malawi", "656": "Niger",
    "657": "Nigeria", "659": "Namibie", "660": "La Réunion", "661": "Rwanda",
    "662": "Soudan", "663": "Sénégal", "664": "Seychelles", "665": "Sainte-Hélène",
    "666": "Somalie", "667": "Sierra Leone", "668": "São Tomé-et-Príncipe",
    "669": "Eswatini", "670": "Tchad", "671": "Togo", "672": "Tunisie",
    "674": "Tanzanie", "675": "Ouganda", "676": "RD Congo", "677": "Tanzanie",
    "678": "Zambie", "679": "Zimbabwe",
    "701": "Argentine", "710": "Brésil", "720": "Bolivie", "725": "Chili",
    "730": "Colombie", "735": "Équateur", "740": "Malouines",
    "745": "Guyane française", "750": "Guyana", "755": "Paraguay", "760": "Pérou",
    "765": "Suriname", "770": "Uruguay", "775": "Venezuela",
}


def mmsi_info(mmsi: int | str) -> dict[str, str]:
    """Nature de la station et pays d'immatriculation déduits du MMSI."""
    s = f"{int(mmsi):09d}"

    if s.startswith("00"):
        kind, mid = "coast", s[2:5]
    elif s.startswith("99"):
        kind, mid = "aton", s[2:5]
    elif s.startswith("98"):
        kind, mid = "auxiliary", s[2:5]
    elif s.startswith("970"):
        kind, mid = "sart", ""
    elif s.startswith("972"):
        kind, mid = "mob", ""
    elif s.startswith("974"):
        kind, mid = "epirb", ""
    elif s.startswith("111"):
        kind, mid = "sar_aircraft", s[3:6]
    elif s.startswith("0"):
        kind, mid = "group", s[1:4]
    else:
        kind, mid = "vessel", s[0:3]

    return {"kind": kind, "mid": mid, "country": MID.get(mid, "")}


# ---------------------------------------------------------------------------
# Types de navire (ITU-R M.1371, table 53)
# ---------------------------------------------------------------------------

_SHIP_TYPE_SPECIAL = {
    30: ("Pêche", "fishing"),
    31: ("Remorqueur", "tug"),
    32: ("Remorqueur (convoi > 200 m)", "tug"),
    33: ("Drague / travaux sous-marins", "special"),
    34: ("Plongée", "special"),
    35: ("Militaire", "military"),
    36: ("Voilier", "sailing"),
    37: ("Navire de plaisance", "pleasure"),
    50: ("Pilote", "special"),
    51: ("SAR — recherche et sauvetage", "sar"),
    52: ("Remorqueur", "tug"),
    53: ("Servitude portuaire", "special"),
    54: ("Lutte antipollution", "special"),
    55: ("Police / douane", "special"),
    56: ("Usage local", "other"),
    57: ("Usage local", "other"),
    58: ("Transport médical", "special"),
    59: ("Navire non combattant (RR 18)", "special"),
}

_SHIP_TYPE_DECADE = {
    2: ("Aéroglisseur (WIG)", "hsc"),
    4: ("Navire à grande vitesse", "hsc"),
    6: ("Passagers", "passenger"),
    7: ("Cargo", "cargo"),
    8: ("Pétrolier / chimiquier", "tanker"),
    9: ("Autre type", "other"),
}

_CARGO_SUFFIX = {
    1: "matières dangereuses A", 2: "matières dangereuses B",
    3: "matières dangereuses C", 4: "matières dangereuses D",
}


def ship_type(code: int | None) -> tuple[str, str]:
    """(libellé, groupe) pour un code de type AIS. Le groupe pilote la couleur."""
    if code is None:
        return ("", "unknown")
    code = int(code)
    if code == 0:
        return ("non précisé", "unknown")
    if code in _SHIP_TYPE_SPECIAL:
        return _SHIP_TYPE_SPECIAL[code]
    label, group = _SHIP_TYPE_DECADE.get(code // 10, ("", "unknown"))
    if not label:
        return (f"type {code}", "unknown")
    suffix = _CARGO_SUFFIX.get(code % 10)
    return (f"{label} ({suffix})" if suffix else label, group)


# ---------------------------------------------------------------------------
# Énumérations diverses
# ---------------------------------------------------------------------------

NAV_STATUS = {
    0: "en route au moteur", 1: "au mouillage", 2: "sans commande",
    3: "manœuvrabilité restreinte", 4: "contraint par son tirant d'eau",
    5: "à quai", 6: "échoué", 7: "en pêche", 8: "en route à la voile",
    9: "réservé (HSC)", 10: "réservé (WIG)", 11: "remorquage arrière",
    12: "remorquage avant/latéral", 13: "réservé", 14: "AIS-SART / MOB / EPIRB",
    15: "non défini",
}

MANEUVER = {0: "non disponible", 1: "pas de manœuvre particulière", 2: "manœuvre d'évitement"}

EPFD = {
    0: "non défini", 1: "GPS", 2: "GLONASS", 3: "GPS + GLONASS", 4: "Loran-C",
    5: "Chayka", 6: "centrale inertielle", 7: "relevé topographique",
    8: "Galileo", 15: "GNSS interne",
}

NAVAID = {
    0: "type non précisé", 1: "réflecteur radar", 2: "structure fixe hors mer",
    3: "danger isolé", 4: "eaux saines", 5: "marque spéciale",
    6: "cardinale Nord", 7: "cardinale Est", 8: "cardinale Sud",
    9: "cardinale Ouest", 10: "latérale bâbord", 11: "latérale tribord",
    12: "latérale bâbord préférée", 13: "latérale tribord préférée",
    14: "danger isolé", 15: "eaux saines", 16: "marque spéciale",
    17: "phare sans AIS", 18: "phare avec AIS", 19: "bateau-feu / LANBY",
    20: "amer / balise (référence)", 21: "tour RACON", 22: "structure offshore",
    23: "structure flottante", 24: "latérale bâbord", 25: "latérale tribord",
    26: "latérale bâbord préférée", 27: "latérale tribord préférée",
    28: "cardinale Nord", 29: "cardinale Est", 30: "cardinale Sud",
    31: "cardinale Ouest",
}

# ---------------------------------------------------------------------------
# Message 8 DAC=1 FID=31 (météo/hydro) : valeurs « non disponible »
# ---------------------------------------------------------------------------

METEO_NA = {
    "wspeed": (127,), "wgust": (127,), "wdir": (360,), "wgustdir": (360,),
    "airtemp": (-102.4,), "humidity": (101,), "dewpoint": (50.1,),
    "pressure": (1310, 1311), "pressuretend": (3,), "visibility": (12.7,),
    "waterlevel": (30.01, 5.65, -10.01), "leveltrend": (3,),
    "cspeed": (25.5,), "cdir": (360,), "cspeed2": (25.5,), "cdir2": (360,),
    "cdepth2": (31,), "cspeed3": (25.5,), "cdir3": (360,), "cdepth3": (31,),
    "waveheight": (25.5,), "waveperiod": (63,), "wavedir": (360,),
    "swellheight": (25.5,), "swellperiod": (63,), "swelldir": (360,),
    "seastate": (13,), "watertemp": (50.1,), "preciptype": (7,),
    "salinity": (51.0, 51.1), "ice": (3,),
}

METEO_LABELS = {
    "wspeed": ("Vent moyen", "nds"), "wgust": ("Rafales", "nds"),
    "wdir": ("Direction du vent", "°"), "wgustdir": ("Direction des rafales", "°"),
    "airtemp": ("Température de l'air", "°C"), "humidity": ("Humidité", "%"),
    "dewpoint": ("Point de rosée", "°C"), "pressure": ("Pression", "hPa"),
    "visibility": ("Visibilité", "NM"), "waterlevel": ("Niveau d'eau", "m"),
    "cspeed": ("Courant de surface", "nds"), "cdir": ("Direction du courant", "°"),
    "cspeed2": ("Courant (2)", "nds"), "cdir2": ("Direction courant (2)", "°"),
    "cdepth2": ("Profondeur mesure (2)", "m"),
    "cspeed3": ("Courant (3)", "nds"), "cdir3": ("Direction courant (3)", "°"),
    "cdepth3": ("Profondeur mesure (3)", "m"),
    "waveheight": ("Hauteur des vagues", "m"), "waveperiod": ("Période des vagues", "s"),
    "wavedir": ("Direction des vagues", "°"), "swellheight": ("Houle", "m"),
    "swellperiod": ("Période de houle", "s"), "swelldir": ("Direction de la houle", "°"),
    "seastate": ("État de la mer (Beaufort)", ""), "watertemp": ("Température de l'eau", "°C"),
    "salinity": ("Salinité", "‰"),
}

PRESSURE_TEND = {0: "en baisse", 1: "stable", 2: "en hausse"}
PRECIP_TYPE = {
    0: "réservé", 1: "pluie", 2: "grésil", 3: "grêle", 4: "neige", 5: "mixte",
    6: "embruns",
}
ICE = {0: "pas de glace", 1: "glace"}


def meteo_clean(d: dict) -> dict:
    """Ne garde que les champs météo réellement mesurés (rejette les sentinelles)."""
    out = {}
    for key, value in d.items():
        if value is None or key not in METEO_NA:
            continue
        if value in METEO_NA[key]:
            continue
        out[key] = value
    if "pressuretend" in d and d["pressuretend"] in PRESSURE_TEND:
        out["pressuretend"] = PRESSURE_TEND[d["pressuretend"]]
    if "preciptype" in d and d["preciptype"] in PRECIP_TYPE:
        out["preciptype"] = PRECIP_TYPE[d["preciptype"]]
    if "ice" in d and d["ice"] in ICE:
        out["ice"] = ICE[d["ice"]]
    return out
