# Gribs

## Grib sources

### Meteo France

- AROME: https://donneespubliques.meteofrance.fr/?fond=produit&id_produit=131&id_rubrique=51
- ARPEGE: https://donneespubliques.meteofrance.fr/?fond=produit&id_produit=130&id_rubrique=51
- MFWAM: https://donneespubliques.meteofrance.fr/?fond=produit&id_produit=132&id_rubrique=51

### Meteo Consult Marine

- https://marine.meteoconsult.fr/services-marine/fichiers-grib

### Weather 4D

- http://grib.weather4d.com

### Private / alternatives souces

- https://opengribs.org/en/gribs
- https://openskiron.org/en/openwrf
- https://www.grib2.tk/
- Mirror of Meteo France: https://mf-models-on-aws.org/

## Softwares

### Libraries

- https://github.com/jswhit/pygrib
- https://docs.xarray.dev/
- https://confluence.ecmwf.int/display/ECC/
- https://github.com/ecmwf/cfgrib
- https://github.com/ecmwf/eccodes-python

### CLI

- <https://www.cpc.ncep.noaa.gov/products/wesley/wgrib.html>
- <https://www.cpc.ncep.noaa.gov/products/wesley/wgrib2/>

### wgrib2

- Docker: `docker build -t wgrib2 . && docker run --rm wgrib2`
- macOS: `FC=gfortran-11 CC=gcc-11 make USE_JASPER=0 USE_NETCDF3=0`