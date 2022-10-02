#!/usr/bin/env python3

import datetime
import gzip
from argparse import ArgumentParser
from collections import defaultdict
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from types import BuiltinFunctionType, MethodWrapperType
from urllib.parse import unquote, urlencode

import pygrib
import pytz
import requests


class GribFile:
    data_dir = Path("data")

    def __init__(self, filename, url=None, no_check=False):
        self.no_check = no_check
        if isinstance(filename, str) and filename.startswith("https:") or filename.startswith("http:"):
            assert url is None
            self.filename = self.data_dir / Path(filename).name
            self.url = filename
        elif url:
            self.filename = self.data_dir / Path(filename)
            self.url = url
        else:
            self.filename = Path(filename)
            self.url = None

    def open(self):
        grib = pygrib.open(self.local_filename)
        grib.seek(0)
        return grib

    def __str__(self):
        return f"{self.filename} {self.url}"

    def info_ecccodes(self, details=False):

        import eccodes

        print(self.url or self.filename)

        with eccodes.FileReader(self.local_filename) as reader:
            for message in reader:
                print(
                    "|".join(
                        map(
                            str,
                            (
                                # message["centreDescription"],
                                # message["centre"],
                                # message["discipline"],
                                # message["parameterCategory"],
                                # message["parameterNumber"],
                                # message["parameterUnits"],
                                # message["parameterName"],
                                message["name"],
                                message["units"],
                                message["validityDate"],
                                message["validityTime"],
                            ),
                        )
                    )
                )

    def info(self, details=False):

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
        if self.url:
            filename = self.filename
            ts = filename.with_name("." + filename.name + ".timestamp")

            if filename.suffix in [".gz"]:
                uncompress = filename.suffix
                filename = filename.with_suffix("")
            else:
                uncompress = None

            if filename.is_file():
                if self.no_check:
                    return filename
                if ts.is_file():
                    print(f"\033[0;34mcheck {self.url}\033[0m")
                    r = requests.head(self.url)
                    mark = self.url + "\n" + r.headers["Last-Modified"].strip()
                    if mark == ts.read_text():
                        return filename

            print(f"\033[0;33mdownload {self.url}\033[0m")
            r = requests.get(self.url)
            if r.status_code == 200:
                filename.parent.mkdir(parents=True, exist_ok=True)

                if uncompress == ".gz":
                    filename.write_bytes(gzip.decompress(r.content))
                else:
                    filename.write_bytes(r.content)

                mark = self.url + "\n" + r.headers["Last-Modified"].strip()
                ts.write_text(mark)

                return filename

            raise FileNotFoundError(filename.name)

        return Path(self.filename)


class MeteoFrance(GribFile):
    """
    https://donneespubliques.meteofrance.fr/donnees_libres/Static/CacheDCPC_NWP.json
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

    def __init__(self, reference_time=None, time=0, model="Arome", HD=True, package="SP1", **kwargs):

        model = model.upper()

        # Champs constants (relief et masque terre-mer)
        if model.endswith("STATIC"):
            model = model[:-6].rstrip("_").upper()

            grid, _, _ = MeteoFrance.get_model_parameters(model, HD)

            url = f"https://donneespubliques.meteofrance.fr/donnees_libres/Static/gribsConstants/{model}_{grid}_CONSTANT.grib"
            return super().__init__(url, no_check=True)

        # date du run
        if not reference_time:
            reference_time = MeteoFrance.get_latest_runs(model)[0]
        elif not isinstance(reference_time, datetime.datetime):
            reference_time = datetime.datetime.fromisoformat(reference_time)

        grid, valid_ranges, packages = MeteoFrance.get_model_parameters(model, HD)

        if package not in packages:
            raise ValueError(package)

        if isinstance(time, int):
            for i in valid_ranges:
                if i.startswith(f"{time:02d}H"):
                    time = i
                    break
        if time not in valid_ranges:
            raise ValueError(time)

        url = "http://dcpc-nwp.meteo.fr/services/PS_GetCache_DCPCPreviNum?"
        query = {
            "token": self.token,
            "model": model,
            "grid": grid,
            "package": package,
            "time": time,
            "referencetime": reference_time.isoformat() + "Z",
            "format": "grib2",
        }

        d = datetime.datetime.fromisoformat(reference_time.isoformat())
        d = f"{d.year}{d.month:02d}{d.day:02d}{d.hour:02d}{d.minute:02d}"

        filename = f"W_fr-meteofrance,MODEL,{model}+{grid.replace('.','')}+{package}+{time}_C_LFPW_{d}--.grib2"

        super().__init__(filename, url + urlencode(query), **kwargs)

    def get_model_parameters(model, HD):
        if model == "ARPEGE" and HD:
            grid = "0.1"
            valid_ranges = ["00H12H", "13H24H", "25H36H", "37H48H", "49H60H", "61H72H", "73H84H", "85H96H", "97H102H", "103H114H"]
            packages = ["HP1", "HP2", "IP1", "IP2", "IP3", "IP4", "SP1", "SP2"]
        elif model == "ARPEGE" and not HD:
            grid = "0.5"
            valid_ranges = ["00H24H", "27H48H", "51H72H", "75H102H", "105H114H"]
            packages = ["HP1", "HP2", "IP1", "IP2", "IP3", "IP4", "SP1", "SP2"]
        elif model == "AROME" and HD:
            packages = ["HP1", "SP1", "SP2", "SP3"]
            valid_ranges = [f"{i:02d}H" for i in range(43)]
            grid = "0.01"
        elif model == "AROME" and not HD:
            packages = ["HP1", "HP2", "HP3", "IP1", "IP2", "IP3", "IP4", "IP5", "SP1", "SP2", "SP3"]
            valid_ranges = ["00H06H", "07H12H", "13H18H", "19H24H", "25H30H", "31H36H", "36H42H"]
            grid = "0.025"
        else:
            raise ValueError(model)
        return (grid, valid_ranges, packages)

    def get_latest_runs(model):
        if model == "AROME":
            runs = [0, 3, 6, 12]
        else:
            runs = [0, 6, 12, 18]
        utc_now = datetime.datetime.utcnow()
        i = max(i for i, v in enumerate(runs) if v <= utc_now.hour)

        latest = utc_now.replace(hour=runs[i], minute=0, second=0, microsecond=0)
        all_latest = [latest]

        for j in range(4):
            delta = runs[i] - runs[(i - j - 1) % len(runs)]
            all_latest.append(latest - datetime.timedelta(hours=delta))

        return all_latest


class MeteoConsult(GribFile):
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
    parser.add_argument("--mc", type=str, help="Meteo Consult Marine")
    parser.add_argument("--currents", action="store_true", help="currents (Meteo Consult)")

    parser.add_argument("-a", "--arome", action="store_true", help="Meteo France AROME")
    parser.add_argument("-g", "--arpege", action="store_true", help="Meteo France ARPEGE")
    parser.add_argument("--hd", action="store_true", help="HD (Meteo France)")
    parser.add_argument("-t", "--time", type=int, help="time (Meteo France)", default=0)

    parser.add_argument("grib", nargs="?")
    args = parser.parse_args()

    grib = None
    if args.mc:
        grib = MeteoConsult(args.mc, args.currents)

    elif args.arome:
        grib = MeteoFrance(package="SP1", model="AROME", time=args.time, no_check=True, HD=args.hd)

    elif args.arpege:
        grib = MeteoFrance(package="SP1", model="ARPEGE", time=args.time, no_check=True, HD=args.hd)

    elif args.grib:
        grib = GribFile(args.grib)

    if grib:
        grib.info(details=args.verbose)

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
