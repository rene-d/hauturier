#!/usr/bin/env python3

import datetime
import gzip
import json
import logging
import os
import time
from argparse import ArgumentParser
from collections import defaultdict
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from types import BuiltinFunctionType, MethodWrapperType
from urllib.parse import unquote, urlencode

import eccodes
import pygrib
import pytz
import requests
from dateutil.parser import parse as parsedate


class GribFile:
    """
    A grib file, URL or local file.
    """

    data_dir = Path("data")

    def __init__(self, filename, url=None, no_check=False):
        """
        Initialize a grib file.

        `filename` local filename or remote url resource.
        `url` optional url for remote resource, `filename` has to be a local filename in this case.
        `no_check` if True, never check the remote file and do not create the timestamp file.
        """
        self.no_check = no_check
        if isinstance(filename, str) and filename.startswith("https:") or filename.startswith("http:"):
            # assert url is None
            if url is not None:
                raise ValueError(f"url should be None")
            self.filename = self.data_dir / Path(filename).name
            self.url = filename
        elif url:
            self.filename = self.data_dir / Path(filename)
            self.url = url
        else:
            self.filename = Path(filename)
            self.url = None

    def open(self):
        """
        Open the grib, return the object.
        """
        grib = pygrib.open(self.local_filename)
        grib.seek(0)
        return grib

    def __str__(self):
        """
        Return a string representing the grib: filename and the optional url.
        """
        return f"{self.filename} {self.url}"

    def info_ecccodes(self, details=False):
        """
        Displays some info with ecccodes library.
        """

        print(self.url or self.filename)
        with eccodes.FileReader(self.local_filename) as reader:
            for message in reader:
                print(
                    "|".join(
                        map(
                            str,
                            (
                                # message["centreDescription"], message["centre"], message["discipline"], message["parameterCategory"],
                                # message["parameterNumber"], message["parameterUnits"], message["parameterName"],
                                message["name"],
                                message["units"],
                                message["validityDate"],
                                message["validityTime"],
                            ),
                        )
                    )
                )

    def info(self, details=False):
        """
        Show grib messages (layers).
        """
        print(self.filename)

        grib = self.open()

        class Stat:
            count = 0
            min_validDate = None
            max_validDate = None

            def __str__(self) -> str:
                return f"{self.count:4} {self.min_validDate} +{self.max_validDate-self.min_validDate}"

            def validDate(self, d):
                if not d:
                    return
                if not self.min_validDate:
                    self.min_validDate = d
                    self.max_validDate = d
                else:
                    self.min_validDate = min(d, self.min_validDate)
                    self.max_validDate = max(d, self.max_validDate)

        names = defaultdict(lambda: Stat())
        for i, message in enumerate(grib):
            names[message.name].count += 1
            names[message.name].validDate(message.validDate)
            if details:
                print(i, message)
                for k in sorted(set(dir(message))):
                    if k == "__doc__":
                        continue
                    v = getattr(message, k)
                    if k.startswith("__") and k.endswith("__") and isinstance(v, (MethodWrapperType, BuiltinFunctionType)):
                        continue
                    if isinstance(v, (str, int, float, datetime.datetime)):
                        print(f"  {k:40} = {v}")
                    else:
                        print(f"  {k:40} = {type(v)} ?")

        for k, v in names.items():
            print(f"{k:60} {v}")

    @property
    def local_filename(self):
        """
        Obtain a local filename for the grib, by downloading the remote resource if necessary.
        Also expand compressed files.
        """
        if self.url:
            filename = self.filename
            timestamp_file = filename.with_name("." + filename.name + ".timestamp")

            if filename.suffix in [".gz"]:
                uncompress = filename.suffix
                filename = filename.with_suffix("")
            else:
                uncompress = None

            if filename.is_file():
                if self.no_check:
                    return filename
                if timestamp_file.is_file():
                    logging.info(f"\033[0;34mcheck {self.url}\033[0m")
                    r = requests.head(self.url)
                    mark = self.url + "\n" + r.headers["Last-Modified"].strip()
                    if mark == timestamp_file.read_text():
                        return filename

            logging.info(f"\033[0;33mdownload {self.url}\033[0m")
            r = requests.get(self.url)
            r.raise_for_status()

            filename.parent.mkdir(parents=True, exist_ok=True)

            if uncompress == ".gz":
                filename.write_bytes(gzip.decompress(r.content))
            else:
                filename.write_bytes(r.content)

            if not self.no_check:
                mark = self.url + "\n" + r.headers["Last-Modified"].strip()
                timestamp_file.write_text(mark)

            if "Last-Modified" in r.headers:
                url_date = parsedate(r.headers["Last-Modified"])
                logging.debug(url_date)
                mtime = round(url_date.timestamp() * 1_000_000_000)
                os.utime(filename, ns=(mtime, mtime))
                if not self.no_check:
                    os.utime(timestamp_file, ns=(mtime, mtime))

            return filename

        return Path(self.filename)


class MeteoFrance(GribFile):
    """
    Arpège: https://donneespubliques.meteofrance.fr/?fond=produit&id_produit=130&id_rubrique=51
    Arome: https://donneespubliques.meteofrance.fr/?fond=produit&id_produit=131&id_rubrique=51
    """

    # nomsSsPaquets = {
    #     "SP1": "Paramètres courants à la surface",
    #     "SP2": "Paramètres additionnels à la surface",
    #     "SP3": "Paramètres additionnels (2) à la surface",
    #     "HP1": "Paramètres courants en niveaux hauteur",
    #     "HP2": "Paramètres additionnels en niveaux hauteur",
    #     "HP3": "Paramètres additionnels (2) en niveaux hauteur",
    #     "IP1": "Paramètres courants en niveaux isobares",
    #     "IP2": "Paramètres additionnels en niveaux isobares",
    #     "IP3": "Paramètres additionnels (2) en niveaux isobares",
    #     "IP4": "Paramètres additionnels (3) en niveaux isobares",
    #     "IP5": "Paramètres additionnels (4) en niveaux isobares",
    # }

    token = "__5yLVTdr-sGeHoPitnFc7TZ6MhBcJxuSsoZp6y0leVHU__"

    def __init__(self, reference_time=None, echeance=0, model="Arome", HD=True, package="SP1", static=False, **kwargs):

        # validate the parameters
        model = model.upper()
        grid, echeance = MeteoFrance.get_model_parameters(model, HD, echeance, package)

        # Champs constants (relief et masque terre-mer)
        if static:
            url = f"https://donneespubliques.meteofrance.fr/donnees_libres/Static/gribsConstants/{model}_{grid}_CONSTANT.grib"
            return super().__init__(url, no_check=True)

        # date du run: doit être au format ISO8601
        if not reference_time:
            reference_time = self.get_latest_run(model, package, grid, echeance)

        self.reference_time = reference_time
        self.echeance = echeance
        self.package = package
        self.grid = grid

        url = "http://dcpc-nwp.meteo.fr/services/PS_GetCache_DCPCPreviNum?"
        query = {
            "token": self.token,
            "model": model,
            "grid": grid,
            "package": package,
            "time": echeance,
            "referencetime": reference_time,
            "format": "grib2",
        }

        reftime = datetime.datetime.fromisoformat(reference_time.replace("Z", "+00:00"))
        short_reftime = reftime.strftime("%Y%m%d%H%M")

        filename = f"W_fr-meteofrance,MODEL,{model}+{grid.replace('.','')}+{package}+{echeance}_C_LFPW_{short_reftime}--.grib2"

        logging.debug(f"{model} {grid} {package} {echeance} {reftime.strftime('%Y-%m-%d %H UTC')}")
        logging.debug(f"filename {filename}")

        super().__init__(filename, url + urlencode(query), no_check=True, **kwargs)

    def get_model_parameters(model, HD, echeance, package):
        """
        Validates parameters for AROME and ARPEGE models.
        """

        if model == "ARPEGE" and HD:
            grid = "0.1"
            valid_echeances = ["00H12H", "13H24H", "25H36H", "37H48H", "49H60H", "61H72H", "73H84H", "85H96H", "97H102H", "103H114H"]
            packages = ["HP1", "HP2", "IP1", "IP2", "IP3", "IP4", "SP1", "SP2"]

        elif model == "ARPEGE" and not HD:
            grid = "0.5"
            valid_echeances = ["00H24H", "27H48H", "51H72H", "75H102H", "105H114H"]
            packages = ["HP1", "HP2", "IP1", "IP2", "IP3", "IP4", "SP1", "SP2"]

        elif model == "AROME" and HD:
            packages = ["HP1", "SP1", "SP2", "SP3"]
            valid_echeances = [f"{i:02d}H" for i in range(43)]
            grid = "0.01"

        elif model == "AROME" and not HD:
            packages = ["HP1", "HP2", "HP3", "IP1", "IP2", "IP3", "IP4", "IP5", "SP1", "SP2", "SP3"]
            valid_echeances = ["00H06H", "07H12H", "13H18H", "19H24H", "25H30H", "31H36H", "36H42H"]
            grid = "0.025"

        else:
            raise ValueError(f"unknown model {model}")

        # check the package name
        if package not in packages:
            raise ValueError(f"unknown package {package} for model {model}")

        # check the echeance (int or the actual string)
        if isinstance(echeance, int):
            for i in valid_echeances:
                if i.startswith(f"{echeance:02d}H"):
                    echeance = i
                    break
        if echeance not in valid_echeances:
            raise ValueError(f"bad time: {echeance}")

        return (grid, echeance)

    def get_latest_run(self, model, package, grid, echeance):
        """
        Get the most recent run date for the model.
        """

        f = self.data_dir / "CacheDCPC_NWP.json"
        if f.is_file() and time.time() - f.stat().st_mtime < 1800:
            logging.debug(f"load cached {f.stem}")
            r = json.loads(f.read_bytes())
        else:
            url = "https://donneespubliques.meteofrance.fr/donnees_libres/Static/CacheDCPC_NWP.json"
            r = requests.get(url)
            r.raise_for_status()
            f.parent.mkdir(exist_ok=True, parents=True)
            f.write_bytes(r.content)
            logging.debug(f"write {f.stem}")
            r = r.json()

        # the JSON contains nested dictionaries for all models, all packages and all echeance times.
        for i in r:
            if i["modele"] == model and i["grille"] == grid:
                for j in i["refPacks"]:
                    if j["codePack"] == package:
                        for k in j["refGrpEchs"]:
                            if k["echeance"] == echeance:
                                return sorted(k["refReseauxDispos"])[-1]

        raise ValueError(f"no last run for {model},{package},{grid},{echeance}")


class MeteoConsult(GribFile):
    """
    WIP
    """

    def __init__(self, zone, current=False, **kwargs):
        class MeteoConsultGribs(HTMLParser):
            zones = set()

            def __init__(self, zone):
                self.zone = zone.replace(" ", "").lower()
                super().__init__()

            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    if ("class", "restriction-link") in attrs:
                        wind, current, zone = None, None, None
                        for name, value in attrs:
                            if name == "href":
                                wind = unquote(value)
                            elif name == "data-linkgribtotalcurrent":
                                current = unquote(value)
                            elif name == "data-title":
                                zone = unquote(value)
                        if zone.replace(" ", "").lower() == self.zone and wind and current:
                            raise StopIteration((wind, current))
                        else:
                            self.zones.add(zone)

        today = datetime.datetime.now().strftime("%Y%m%d")
        zone = zone.replace(" ", "").lower()
        if current:
            filename = f"meteoconsult_{zone}_{today}_current.grb"
        else:
            filename = f"meteoconsult_{zone}_{today}_wind.grb"

        index_html = None
        f = self.data_dir / "meteoconsult_gribs"
        e = self.data_dir / "meteoconsult_expires"

        if f.is_file() and e.is_file():
            expires = parsedate_to_datetime(e.read_text())
            now = datetime.datetime.now().astimezone(pytz.UTC)
            if now < expires:
                index_html = f.read_text()

        if not index_html:
            print("download index")
            r = requests.get("https://marine.meteoconsult.fr/services-marine/fichiers-grib")
            if r.status_code != 200:
                raise requests.HTTPError(e.status_code)
            index_html = r.text

            f.write_text(index_html)
            e.write_text(r.headers["Expires"].strip())

        try:
            parser = MeteoConsultGribs(zone)
            parser.feed(index_html)
            print(f"Available zones: {parser.zones}")
        except StopIteration as e:
            url = e.value[current]
            super().__init__(filename, url, **kwargs)
        else:
            raise FileNotFoundError(zone)


if __name__ == "__main__":
    parser = ArgumentParser(description="grib downloader")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-d", "--details", action="store_true", help="show some grib details")

    # parser.add_argument("--mc", type=str, help="Meteo Consult Marine")
    # parser.add_argument("--currents", action="store_true", help="currents (Meteo Consult)")

    parser.add_argument("-a", "--arome", action="store_true", help="Meteo France AROME (modèle haute résolution) paquet SP1")
    parser.add_argument("-g", "--arpege", action="store_true", help="Meteo France ARPEGE (modèle global) paquet SP1")
    parser.add_argument("--hd", action="store_true", help="grille haute définition (Meteo France)")
    parser.add_argument("-t", "--time", dest="echeance", type=int, help="échéance (Meteo France)", default=0)

    parser.add_argument("grib", nargs="?")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s", level=logging.DEBUG, datefmt="%H:%M:%S")

    grib = None
    # if args.mc or args.currents:
    #     grib = MeteoConsult(args.mc, args.currents)

    try:

        if args.arome:
            grib = MeteoFrance(package="SP1", model="AROME", echeance=args.echeance, HD=args.hd)

        elif args.arpege:
            grib = MeteoFrance(package="SP1", model="ARPEGE", echeance=args.echeance, HD=args.hd)

        elif args.grib:
            grib = GribFile(args.grib)

    except Exception as e:
        parser.error(f"could not open grib")

    if grib:
        grib.info(details=args.details)

    # MeteoFrance(package="SP1", time="00H", no_check=True).info()
    # MeteoFrance(package="SP1", time="42H").info()
    # MeteoFrance(package="SP1", reference_time="2022-08-30T12:00:00Z", time=0, no_check=True, HD=False).info()

    # http://grib.weather4d.com/MyOcean/
    # http://grib.weather4d.com/AromeHD/
    # GribFile("http://grib.weather4d.com/MyOcean/Bretagne.grb.gz").info()
    # GribFile("http://grib.weather4d.com/AromeHD/Manche-lastest.grb").info()
    # GribFile("http://grib.weather4d.com/AromeHD/Atlantique-lastest.grb")

    # https://www.grib2.tk/ALL/
    # https://www.grib2.tk/HD/
    # https://www.grib2.tk/IFREMER/
    # GribFile("https://www.grib2.tk/IFREMER/FINIS250.grb").info()
    # GribFile("https://www.grib2.tk/IFREMER/SUDBZH250.grb").info()
    # GribFile("https://www.grib2.tk/IFREMER/MANE250.grb").info()
    # GribFile("https://www.grib2.tk/IFREMER/MANW250.grb").info()
