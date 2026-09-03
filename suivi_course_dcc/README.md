# tor2dcc

Tracker PredictWind de **The Ocean Race Atlantic 2026** → fichiers Adrena
(`.dcc` + `.txt` posreport), lus par **qtVlm** et Adrena.

```bash
python3 tor2dcc.py                 # -> out/<course>.dcc et out/<course>.txt
python3 tor2dcc.py --loop 300      # rafraîchit toutes les 5 min
python3 tor2dcc.py --help          # --pas, --depuis, --dernier-point, --no-pad…
python3 parcours.py                # -> out/*.gpx (routes) et out/*.kml (zones)
python3 -m pytest -q               # tests, aucun accès réseau
```

Python ≥ 3.11, stdlib seule (`urllib`, pas de `requests`).

## Ce que produit le convertisseur

| Fichier | Contenu |
|---|---|
| `<course>.dcc` | descriptif des concurrents : nom, type, ID |
| `<course>.txt` | posreport : **toute la trace** de chaque bateau, N lignes par ID |

Le posreport garde l'historique complet, pas seulement la dernière position :
c'est ce qui donne une trace exploitable dans qtVlm. `--dernier-point` réduit à
un instantané, `--pas` et `--depuis` allègent.

L'ID concurrent est le `trackId` de PredictWind — numérique, stable par
construction, donc rien à persister et rien à désynchroniser.

Format de sortie : **[FORMAT-DCC.md](FORMAT-DCC.md)**, rétro-ingénierie
documentée (aucune spec publique n'existe), chaque affirmation étiquetée
mesurée / hypothèse / inconnue. Deux oracles authentiques l'étayent : YB
Tracking (v1.3, avec posreport) et Geovoile (v1.5). Le convertisseur **écrit**
du 1.3 — seule version dont on ait une paire complète — et **lit** les deux.

## Organisation

| Module | Rôle |
|---|---|
| `tracker.py` | **seul** point de contact réseau ; renvoie des `Boat` normalisés |
| `dcc.py` | sérialisation et lecture DCC + posreport, aucun I/O réseau |
| `tor2dcc.py` | CLI flotte, écriture atomique (qtVlm relit pendant qu'on réécrit) |
| `parcours.py` | CLI parcours et zones -> GPX/KML, aucun I/O réseau hors `tracker` |
| `tests/fixtures/` | relevés réels : oracles YB Tracking et Geovoile, bootstrap, trace et zones PredictWind |

## Sources de données

`theoceanrace.com/fr/atlantic/2026/tracker` n'expose rien : la carte est une
iframe PredictWind. Tout ce qui suit a été **relevé sur le réseau**, jamais
deviné — si le flux change, le relever à nouveau plutôt que d'extrapoler.

| Ressource | URL (relative à `https://cdn.predictwind.com/`) | Relevé |
|---|---|---|
| Bootstrap (attributs `data-*`) | `ocean-race/?event=atlantic` | 2026-09-02 |
| Trace d'un bateau | `tracking/data/<trackDisplay>.json` | 2026-09-02 |
| Zones d'exclusion | `ocean-race/atlantic/boundaries.json` | 2026-09-03 |
| Observations de cétacés | `whale-sightings.json` | 2026-09-03 |

Le bootstrap porte aussi `data-start-line`, `data-finish-line`, `data-course`
(parcours de référence) et `data-boundaries-json-url`.

Ligne de départ et ligne d'arrivée, deux points chacune :

| | Extrémité 1 | Extrémité 2 |
|---|---|---|
| Départ (au large de New York) | 39,6667 N / 71,2500 W | 39,6167 N / 71,2500 W |
| Arrivée (au large de Lorient) | 47,6842 N / 3,4192 W | 47,6862 N / 3,4212 W |

## Zones d'exclusion → KML

`boundaries.json` est un dictionnaire `clé → {name, lat[], lon[], timestamp}` :
deux tableaux parallèles, **pas** du GeoJSON, et le polygone y est laissé
**ouvert** (retour au premier point implicite).

`python3 parcours.py` écrit huit KML, un `<Polygon>` par fichier (le
`LinearRing` impose la fermeture, ajoutée à l'export) :

| Fichier | Zone | Sommets |
|---|---|---|
| `zone-marine-mammal-exclusion-zone.kml` | Marine Mammal Exclusion Zone | 541 |
| `zone-azores-exclusion-zone.kml` | Azores Exclusion Zone | 7 |
| `zone-finisterre-tss.kml` | Finisterre TSS | 6 |
| `zone-ushant-ouessant-tss.kml` | Ushant (Ouessant) TSS | 5 |
| `zone-madeira-exclusion-zone.kml` | Madeira Exclusion Zone | 5 |
| `zone-ice-exclusion-zone.kml` | Ice Exclusion Zone | 5 |
| `zone-west-scilly-tss.kml` | West Scilly TSS | 4 |
| `zone-south-scilly-tss.kml` | South Scilly TSS | 4 |

La Marine Mammal Exclusion Zone n'est pas un rectangle : cinq sommets forment
sa limite au large (39,833 N/71,333 W → 39,733/71,250 → 39,667/69,917 →
40,583/65,417 → 45,000/51,417 W), les ~536 autres suivent le trait de côte de
Terre-Neuve à Long Island.

Les routes restent en GPX :

| Fichier | Contenu |
|---|---|
| `course.gpx` | route théorique, `<rte>` de 105 `<rtept>` (attribut `data-course`) |
| `ligne-depart.gpx` | ligne de départ, 2 `<rtept>` |
| `ligne-arrivee.gpx` | ligne d'arrivée, 2 `<rtept>` |

La route théorique va du milieu de la ligne de départ au point d'arrivée,
2987 nm cumulés contre 2890 nm d'orthodromie. Ses points n'ont ni horodatage
ni nom dans la source (`type` vaut 0 partout, sans autre champ) : ce sont des
sommets de tracé, pas des marques de parcours à valider. **[H]**

⚠️ `out/` est gitignoré : ces fichiers ne survivent pas à un nettoyage, il suffit
de relancer `parcours.py`. `boundaries.json` porte un `timestamp`
(2026-08-31T05:28:54Z au relevé) et peut évoluer avant le départ.

## À trancher avant la course

- **Zéro-padding des coordonnées** (`003.2160W` vs `3.2160W`) : l'oracle ne
  discrimine pas et l'arrivée est vers 3°W. Produire les deux variantes
  (`--no-pad`) et trancher dans qtVlm.
- **Fuseau des horodatages** : le code écrit en UTC, non confirmé côté qtVlm.
- **Posreport de la v1.5** : jamais observé. L'oracle Geovoile annonce le sien
  par URL (champ 14), mais elle répond 404 depuis la fin de sa course.
