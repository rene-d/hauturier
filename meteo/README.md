# meteo

Récupération des informations de [météo marine](https://meteofrance.com/meteo-marine) publiée par Météo France.

## Description API Météo France

Il y a plusieurs endpoints (non documentés, donc à la pérennité incertaine) utilisés dans la page web.

Prévisions à 7 jours d'un port ou d'une localisation:

`http://webservice.meteofrance.com/forecast/marine?lat=<latitude>&lon=<longitude>&id=&token=xxx`

Bulletin météo régulier ou spécial pour une zone côte ou large:

`http://webservice.meteofrance.com/report?token=xxx&domain=yyy&report_type=marine&report_subtype=zzz&format=xml`

Liste des BMS en cours pour une zone:

`http://webservice.meteofrance.com/warning/timelaps?token=xxx&domain=yyy&depth=1&warning_type=BMS`

## Usage en ligne de commande

### Installation des prérequis

Sans [virtual environment](https://docs.python.org/3/library/venv.html):

```shell
pip3 install -r requirements.txt
```

Avec [virtual environment](https://docs.python.org/3/library/venv.html):

```shell
python3 -m venv .meteo
. .meteo/bin/activate
pip install -r requirements.txt
```

### Météo d'un port (de référence ou non) ou à partir d'une position

```shell
./meteo.py brest            # port de référence
./meteo.py roscoff          # géolocalisation
./meteo.py 48.41,-4.79      # coordonnées latitude,longitude
```

```shell
./meteo.py -l               # liste des ports
```

### Liste des BMS en cours

```shell
./meteo.py -s               # liste des BMS côte
./meteo.py -S               # liste des BMS large
```

### Bulletin Météo Régulier (BMR) ou Bulletin Météo Spécial (BMS) côte

```shell
./meteo.py -b 1-3           # BMR côte (zone BMSCOTE-01-03)
./meteo.py -s corse         # BMS côte (zone BMSCOTE-02-04 si en cours)
```

```shell
./meteo.py -b -l            # liste des zones de BMR/BMS côte
```

### Bulletin Météo Régulier (BMR) ou Bulletin Météo Spécial (BMS) large

```shell
./meteo.py -B 1             # BMR large (zone BMSLARGE-01)
./meteo.py -S iroise        # BMS large (zone BMSLARGE-01-03 si en cours)
```

```shell
./meteo.py -B -l            # liste des zones de BMR/BMS large
```

## Zones des Bulletins Météo Réguliers (BMR) et Spéciaux (BMS)

### Côte

| nom zone                                  | id            |
|-------------------------------------------|---------------|
| Frontière belge / Baie de Somme           | BMSCOTE-01-01 |
| Baie de Somme / Cap de la Hague           | BMSCOTE-01-02 |
| Cap de la Hague / Penmarc'h               | BMSCOTE-01-03 |
| Penmarc'h / Anse de l'Aiguillon           | BMSCOTE-01-04 |
| Anse de l'Aiguillon / Frontière espagnole | BMSCOTE-01-05 |
| Frontière espagnole / Port-Camargue       | BMSCOTE-02-01 |
| Port-Camargue / Saint-Raphaël             | BMSCOTE-02-02 |
| Saint-Raphaël / Menton                    | BMSCOTE-02-03 |
| Corse                                     | BMSCOTE-02-04 |

### Large

| nom zone      | id             | nom zone         | id             |
|---------------|----------------|------------------|----------------|
| Casquets      | BMSLARGE-01-01 | Est de Cabrera   | BMSLARGE-03-01 |
| Ouessant      | BMSLARGE-01-02 | Baléares         | BMSLARGE-03-02 |
| Iroise        | BMSLARGE-01-03 | Minorque         | BMSLARGE-03-03 |
| Yeu           | BMSLARGE-01-04 | Lion             | BMSLARGE-03-04 |
| Rochebonne    | BMSLARGE-01-05 | Provence         | BMSLARGE-03-05 |
| Cantabrico    | BMSLARGE-01-06 | Ligure           | BMSLARGE-03-06 |
| Finisterre    | BMSLARGE-01-07 | Corse            | BMSLARGE-03-07 |
| Pazenn        | BMSLARGE-01-08 | Sardaigne        | BMSLARGE-03-08 |
| Sole          | BMSLARGE-01-09 | Maddalena        | BMSLARGE-03-09 |
| Shannon       | BMSLARGE-01-10 | Elbe             | BMSLARGE-03-10 |
| Fastnet       | BMSLARGE-01-11 | Alboran          | BMSLARGE-03-11 |
| Lundy         | BMSLARGE-01-12 | Palos            | BMSLARGE-03-12 |
| Irish Sea     | BMSLARGE-01-13 | Alger            | BMSLARGE-03-13 |
| Rockall       | BMSLARGE-01-14 | Ouest de Cabrera | BMSLARGE-03-14 |
| Malin         | BMSLARGE-01-15 | Annaba           | BMSLARGE-03-15 |
| Hebrides      | BMSLARGE-01-16 | Tunisie          | BMSLARGE-03-16 |
| Humber        | BMSLARGE-02-01 | Carbonara        | BMSLARGE-03-17 |
| Tamise        | BMSLARGE-02-02 | Lipari           | BMSLARGE-03-18 |
| Pas-de-Calais | BMSLARGE-02-03 | Circeo           | BMSLARGE-03-19 |
| Antifer       | BMSLARGE-02-04 |                  |                |
