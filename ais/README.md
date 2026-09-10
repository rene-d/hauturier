# ais

Réception du trafic AIS de `hera.navimetrix.com:5000` (flux NMEA `!AIVDM`) et
carte web temps réel.

```sh
./aismap.py -p "48.7 -4.0" -r 60 --open   # carte sur http://127.0.0.1:8765/
./hera.py -p "48.7 -4.0" -r 50            # liste des navires dans le terminal
./raw_hera.py                             # flux brut décodé, sans filtre
```

Le serveur envoie une ligne `LAT <lat> LON <lon> RADIUS <NM> AGE <min>` à
l'ouverture de la connexion, puis diffuse du NMEA que `pyais` décode. Le filtre
géographique du serveur est large : `aismap.py` refiltre les cibles sur le rayon
demandé (case « monde entier » pour tout voir).

## aismap.py

| | |
|---|---|
| collecte | thread TCP, reconnexion à intervalle croissant, tous les champs reçus sont fusionnés par MMSI |
| carte | Leaflet, tuiles `*.mbtiles` de Nav&Co **par-dessus** OpenStreetMap : là où la tuile locale manque, OSM reste visible |
| cibles | canvas superposé — coque à l'échelle (dimensions AIS) au-delà de ~22 px, sinon triangle orienté, losange pour les aides à la navigation, cercle pour les stations côtières |
| infobulle | survol = tout ce qui a été reçu du MMSI, clic = épinglé, section « champs bruts décodés » pour le reste |
| état | `aismap.json`, relu au démarrage (`--state ''` pour ne rien garder) |

Options utiles : `-r` rayon affiché, `-a` âge demandé au serveur (min), `-m`
oubli d'une cible sans nouvelle (min), `--port`, `--log` (journal des messages
décodés), `--no-connect` (rejoue l'état sans réseau), `--mbtiles`.

Réglages dans la page : noms, traces, « en route » (SOG ≥ 0,5 nd), « monde
entier », longueur du vecteur vitesse (3 à 60 min, gradué à la minute).

Leaflet est mis en cache dans `~/.cache/aismap/vendor` au premier lancement,
l'application fonctionne ensuite sans accès au réseau autre que le flux AIS.

### API

| route | contenu |
|---|---|
| `/api/status` | connexion, débit, réglages, fonds de carte disponibles |
| `/api/ships?since=N` | fiches courtes, en delta depuis la séquence `N` (`&all=1` : sans filtre de rayon) |
| `/api/ship/<mmsi>` | tout ce qui a été reçu de ce MMSI + sa trace |
| `/api/tracks?minutes=M` | traces récentes de toutes les cibles |
| `/tiles/{z}/{x}/{y}.png` | tuile locale (PNG transparent si absente) |

## aisinfo.py

Tables ITU : MID → pays, types de navire (libellé + groupe de couleur), statuts
de navigation, EPFD, types d'aide à la navigation, et les valeurs « non
disponible » du message 8 DAC=1 FID=31 (météo/hydro), qui sinon s'afficheraient
comme des mesures (vent à 127 nds, air à −102,4 °C…).

## Fonds de carte

`~/Library/Application Support/com.mfdview.instruments/*.mbtiles` — cartes hors
ligne Nav&Co, PNG, zoom 1 à 15, écrites par MFDView. En leur absence, la carte
tourne sur OpenStreetMap seul.
