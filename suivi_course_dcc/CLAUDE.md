# CLAUDE.md — tor2dcc

Convertisseur : tracker PredictWind de The Ocean Race Atlantic 2026 → fichiers
`.dcc` (descriptif de course Adrena) + `.txt` (posreport), lus par qtVlm et
Adrena.

**Le format de sortie est documenté dans [FORMAT-DCC.md](FORMAT-DCC.md).**
Ne pas le redécrire ici : une seule source de vérité.

## Commandes

```bash
python3 tor2dcc.py                   # -> out/<course>.{dcc,txt}
python3 tor2dcc.py --loop 300        # rafraîchit toutes les 5 min
python3 parcours.py                  # -> out/*.gpx (routes), out/*.kml (zones)
python3 -m pytest -q                 # tests, aucun accès réseau
ruff check . && ruff format . && mypy --strict tor2dcc.py dcc.py tracker.py parcours.py
```

Rafraîchir les fichiers de référence (ils changent : le `.dcc` est régénéré à
chaque requête) :

```bash
cd tests/fixtures
curl -sO https://yb.tl/paccup2024-adrenacompetitors.dcc
curl -sO https://yb.tl/paccup2024-adrena.txt
```

## Périmètre

- `tracker.py` — **seul** point de contact réseau. Tout le reste travaille sur
  des `Boat` normalisés (degrés décimaux signés, `datetime` timezone-aware).
- `dcc.py` — sérialisation et lecture DCC + posreport. Aucun I/O réseau.
- `tor2dcc.py` — CLI flotte, écriture atomique.
- `parcours.py` — parcours théorique, lignes et zones d'exclusion en GPX/KML.
  Routes en GPX, zones en KML : seul le `<Polygon>` KML porte la surface
  fermée. La source publie ses polygones **ouverts**, la fermeture est ajoutée
  à l'écriture.
- `tests/fixtures/` — relevés réels : deux oracles authentiques (YB Tracking
  v1.3 + posreport, Geovoile v1.5), bootstrap, trace et zones PredictWind. Les
  tests n'accèdent jamais au réseau.

Pas de `ids.json` : l'ID concurrent est le `trackId` de PredictWind, numérique
et stable par construction. Rien à persister, donc rien à désynchroniser.

Le posreport contient **toute la trace** de chaque bateau (N lignes par ID),
pas seulement sa dernière position : le format l'autorise et c'est ce qui
donne une trace exploitable dans qtVlm. `--dernier-point` revient à un
instantané, `--pas` et `--depuis` allègent.

## Source des données

`theoceanrace.com/fr/atlantic/2026/tracker` n'expose rien : la carte est une
iframe PredictWind. Deux étapes, **relevées le 2026-09-02**, détaillées en
tête de `tracker.py` :

1. `https://cdn.predictwind.com/ocean-race/?event=atlantic`
   → `<script id="inline-data">`, attributs `data-team-info` et
   `data-event-config` (JSON).
2. `https://cdn.predictwind.com/tracking/data/<trackDisplay>.json`
   → `{"route": [{"t", "p": {"lat", "lon"}, …}], "updated", …}`,
   un point par minute, `route` éventuellement segmentée (`.flat()`).

Les URL des ressources annexes sont portées par `<body>`, pas par
`#inline-data` (relevé le 2026-09-03) : `data-boundaries-json-url` donne les
zones d'exclusion, `data-whale-sightings-url` les observations de cétacés.
`#inline-data` porte aussi `data-course` (105 points), `data-start-line` et
`data-finish-line`. L'URL des zones est **lue dans la page**, jamais construite.

> **Ne jamais inventer une URL, un nom de champ JSON ou une clé d'API.** Si le
> flux change, le relever à nouveau (DevTools, filtres Fetch/XHR et WS, ou grep
> du bundle) et mettre à jour les fixtures — ne pas deviner.

Le DCC ne transporte que position + heure : BSP, cap, TWA, TWD, TWS présents
dans le flux sont jetés à la normalisation.

La source ne publie **ni skipper ni série** (vérifié aussi sur son API de
contenu Sanity). Le champ « type » reçoit le pays de l'équipe ; `--serie` force
une autre valeur.

## Invariants à ne pas casser

1. **Asymétrie des dates.** En-tête DCC en `JJ/MM/AA`, horodatages posreport en
   `MM/JJ/AA HH:MM:SS`. Mesuré sur une même paire, même générateur. Ne pas
   « harmoniser ».
2. **`POSADRENA` n'est pas une constante.** C'est le champ 6 de l'en-tête qui
   annonce la ligne magique du posreport ; Geovoile écrit `POSREPORT`. Ne
   jamais le coder en dur dans un lecteur.
3. **Stabilité des IDs.** Le posreport ne référence que l'ID : un ID qui change
   de titulaire fait téléporter un bateau. D'où le `trackId` de la source
   plutôt qu'un compteur local.
4. **Encodage.** Lecture en **cp1252** : l'oracle Geovoile contient `0x85` (…)
   et `0x92` (’), qui sont des contrôles en ISO-8859-1 — les lire en latin-1
   les perd en silence. Sortie strictement ISO-8859-1 : translittérer (table
   explicite, puis NFKD → ASCII) plutôt que d'émettre `?`. Remplacer tout `;` d'un nom
   par `,`. Ne pas normaliser les espaces internes : l'oracle contient
   `David  Raney`, le round-trip en dépend.
5. **Pas de `/` dans le nom de la course** : qtVlm en fait un chemin et échoue.
6. **Carry des minutes** : `59.996′ → 60.00′` bascule sur le degré supérieur.
7. **Écriture atomique** (temporaire + `os.replace`) : qtVlm relit les fichiers
   pendant qu'on les réécrit ; il ne doit jamais en voir un tronqué.

## Points non tranchés

- **Zéro-padding des coordonnées** (`003.2160W` vs `3.2160W`). L'oracle ne
  discrimine pas. Bloquant à l'arrivée à Lorient (~3°W). Produire les deux
  variantes (`--no-pad`) et trancher dans qtVlm **avant** la course.
- **Fuseau des horodatages.** Le code écrit en UTC ; non confirmé côté qtVlm.
- **Posreport de la v1.5** : aucun échantillon. L'URL du champ 14 de l'oracle
  Geovoile répond 404 depuis la fin de sa course.

## Conventions

- Python ≥ 3.11, stdlib seule (`urllib`, pas de `requests`).
- `dataclasses`, annotations partout, `pathlib`.
- Aucun `except: pass`. Une donnée douteuse est une exception, pas un défaut
  silencieux. Les lecteurs échouent bruyamment sur une ligne inattendue.
- Les tests de coordonnées vérifient contre des points géographiques connus
  (`21.2502N/157.4598W` ≈ Kaneohe Bay), pas contre la sortie du code.

## Attentes vis-à-vis de l'assistant

- Français, technique, direct. Pas de préambule, pas de reformulation de la
  demande, pas de récapitulatif de fin.
- Distinguer explicitement le vérifié du supposé. Une hypothèse est étiquetée.
- Si une prémisse de la demande est fausse, le dire d'abord, avant de coder.
- Prendre l'initiative technique (refactor, test, correctif) sans demander
  d'autorisation, tant que la rigueur logique est maintenue.
