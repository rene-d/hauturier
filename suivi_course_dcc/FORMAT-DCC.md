# Le couple DCC / posreport (Adrena)

Format de suivi de course d'Adrena, également lu par qtVlm. **Aucune spec
officielle publique** : tout ce qui suit est de la rétro-ingénierie.

Chaque affirmation est étiquetée :

- **[M]** *mesuré* sur un fichier **authentique** ;
- **[N]** observé sur un échantillon **non authentifié** (voir *Provenance*).
  Depuis l'obtention d'un oracle 1.5 authentique, **plus aucune affirmation de
  ce document ne repose sur cette étiquette** ; elle reste définie pour que la
  distinction garde un nom ;
- **[H]** *hypothèse*, cohérente avec les données mais non démontrée ;
- **[?]** *inconnu*.

## Provenance des échantillons

| Fichier | Version | Provenance | Statut |
|---|---|---|---|
| `paccup2024-adrena*.{dcc,txt}` | 1.3 | Produit par **YB Tracking** pour la Pacific Cup 2024, servi publiquement | **Authentique.** Oracle 1.3 + posreport. |
| `capmartinique2026.dcc` | 1.5 | Produit par **Geovoile** pour la Cap Martinique 2026, servi publiquement | **Authentique.** Oracle 1.5. 45 concurrents. |
| `the-ocean-race-atlantic-2026.dcc` | 1.5 | **Produit par ChatGPT** (cf. l'URL en `.chatgpt.site` de son champ 14) | **Non authentifié.** Conservé pour mémoire. |

Cette distinction n'est pas un détail de forme. Un fichier écrit par un modèle
de langage est *plausible par construction* : il reproduit peut-être fidèlement
un vrai DCC 1.5, ou il peut avoir inventé des champs cohérents avec eux-mêmes.
Les deux se ressemblent, et l'erreur ne se verrait qu'à l'usage.

L'oracle Geovoile tranche : **la structure v1.5 est confirmée** — 14 champs
d'en-tête sans `;` final, 24 champs par concurrent avec `;` final, aux mêmes
places. Le fichier ChatGPT était donc structurellement juste. Il se trompait
en revanche sur trois points, tous détaillés plus bas : le magic du posreport
n'est pas une constante (`POSREPORT` ici, `POSADRENA` chez YB), le champ 12
porte le **skipper** et non le nom répété, et le bloc du champ 22 ne reprend
**pas** la couleur du champ 6.

Restent les champs que ni l'un ni l'autre ne discrimine : deux générateurs
indépendants peuvent recopier la même constante sans que sa sémantique soit
connue. Et **aucun des deux ne prouve ce qu'Adrena accepte en entrée** : seul
un chargement dans qtVlm ou Adrena le dira.

## Fichiers de référence

Le seul jeu public connu, produit par YB Tracking pour la Pacific Cup 2024 :

```bash
curl -sO https://yb.tl/paccup2024-adrenacompetitors.dcc   # descriptif
curl -sO https://yb.tl/paccup2024-adrena.txt              # positions
```

64 concurrents, 64 positions. **[M]** Le `.dcc` est régénéré à chaque
requête : sa date d'en-tête est celle du jour du téléchargement.

Pour la v1.5, `capmartinique2026.dcc` (Geovoile, Cap Martinique 2026, 45
concurrents). Son champ 14 annonce le posreport apparié :

```
https://www.geovoile.net/capmartinique/public/posreport/?key=<32 hex>
```

**[M]** Cette URL répond **404** au 2026-09-03, la course étant terminée : le
posreport v1.5 reste donc **non observé**, et rien ici ne décrit sa forme.

## Vue d'ensemble

Deux fichiers complémentaires, à fournir ensemble :

| | `.dcc` | `.txt` (posreport) |
|---|---|---|
| Rôle | qui court | où ils sont |
| Contenu | nom, série, skipper, **ID** | **ID**, position, heure |
| Cardinalité | 1 par course | 1, rafraîchi ou empilé |
| Jointure | champ 8 | champ 2 |

**[M]** Le posreport ne porte que des ID numériques : sans son `.dcc`, il est
orphelin — rien n'y désigne ni la course ni les bateaux.

**[M]** L'échantillon de référence ne contient qu'un point par bateau — mais
c'est une propriété de *cet* échantillon, **pas une contrainte du format** :
rien n'interdit N lignes portant le même ID à des instants différents, et
c'est ainsi qu'une trace tient dans un seul fichier. **[H]** confirmée par
l'usage : c'est ce que produit ce dépôt.

Les deux stratégies sont donc possibles :

- une trace par fichier, N lignes par bateau — un seul fichier à rafraîchir ;
- un instantané par fichier, 1 ligne par bateau, l'historique se reconstituant
  en empilant N posreports successifs (ce que fait YB Tracking).

## Deux versions observées

Le champ 2 de l'en-tête porte une version de format, et elle change tout :

| | **1.3** | **1.5** |
|---|---|---|
| Référence | `paccup2024-adrenacompetitors.dcc` | `capmartinique2026.dcc` |
| Provenance | YB Tracking — **authentique** | Geovoile — **authentique** |
| Fin de ligne | `LF` | **`CRLF`**, y compris la dernière |
| Date d'en-tête | `JJ/MM/AA` (`02/09/26`) | **`JJ/MM/AAAA`** (`14/04/2026`) |
| En-tête | 6 champs, `;` final | **14 champs, sans `;` final** |
| Ligne concurrent | 14 champs, `;` final | **24 champs, `;` final** |
| Magic du posreport (champ 6) | `POSADRENA` | `POSREPORT` — **c'est un champ, pas une constante** |
| Skipper | champ 12 | champ 12, **même place** |
| URL de mise à jour | absente | **champ 14 de l'en-tête** |
| Couleur, dimensions, rating | absents | **champs 4, 5, 6, 10** |

Tout est **[M]** : chaque colonne est mesurée sur son propre oracle
authentique.

Un lecteur doit donc **brancher sur le champ 2** et accepter les deux fins de
ligne. Les sections qui suivent décrivent 1.3 puis 1.5.

## Conventions communes

| Propriété | Valeur | |
|---|---|---|
| Séparateur | `;` | **[M]** |
| Échappement | aucun | **[M]** — un `;` dans un nom casserait le découpage |
| Fin de ligne | 1.3 : `LF` (`0x0A`) — 1.5 : `CRLF` | **[M]** — zéro `0x0D` chez YB, 46 `CRLF` et zéro `LF` seul chez Geovoile |
| Fin de fichier | fin de ligne terminale | **[M]** dans les deux versions |
| Encodage | **Windows-1252** | **[M]** — voir ci-dessous |
| Lignes vides | absentes | **[M]** |

### L'encodage est du cp1252, pas de l'ISO-8859-1 **[M]**

Les fichiers YB sont intégralement ASCII et ne prouvaient rien. L'oracle
Geovoile tranche : `é` y est un octet `0xE9`, ce qui exclut UTF-8, **et** il
contient deux octets de la plage `0x80-0x9F` :

| Octet | ISO-8859-1 | Windows-1252 | Dans l'oracle |
|---|---|---|---|
| `0x85` | `NEL`, contrôle | `…` | `Acromégalies, Pas Seulement…` |
| `0x92` | contrôle | `’` | apostrophe typographique d'un nom |

Un lecteur strictement ISO-8859-1 en fait donc des **caractères de contrôle**,
silencieusement. **Lire en `cp1252`** : c'est un sur-ensemble de l'ISO-8859-1,
aucun octet valide n'est perdu.

En écriture, rester dans le sous-ensemble ISO-8859-1 (translittérer `…` et `’`)
reste le choix sûr : les deux producteurs le lisent, et rien ne prouve
qu'Adrena accepte la plage C1 en entrée. **[H]**

## Fichier `.dcc`

### En-tête — 6 champs, `;` final

```
Adrena - descriptif des concurrents;1.3;02/09/26;Pacific Cup;0;POSADRENA;
```

| # | Champ | Exemple | |
|---|---|---|---|
| 1 | magic | `Adrena - descriptif des concurrents` | **[M]** invariant |
| 2 | version de format | `1.3` | **[M]** |
| 3 | date de génération, **`JJ/MM/AA`** | `02/09/26` | **[M]** cf. *Dates* |
| 4 | nom de la course | `Pacific Cup` | **[M]** sert de nom de fichier côté qtVlm |
| 5 | ? | `0` | **[?]** constant sur la référence |
| 6 | magic attendu en tête du posreport | `POSADRENA` | **[M]** |

Le champ 4 ne doit pas contenir de `/` : qtVlm en fait un chemin et échoue.

### Lignes concurrent — 14 champs, `;` final

```
the Boss;J35;1;3;1;;;55;;;;Chad Stenwick;;;
```

| # | Champ | Exemple | |
|---|---|---|---|
| 1 | nom du bateau | `the Boss` | **[M]** |
| 2 | série / type | `J35`, `Santa Cruz 27` | **[M]** texte libre, peut être vide |
| 3 | ? | `1` | **[?]** constant sur les 64 lignes |
| 4 | ? | `3` | **[?]** constant sur les 64 lignes |
| 5 | ? | `1` | **[?]** constant sur les 64 lignes |
| 6 | — | vide | **[?]** |
| 7 | — | vide | **[?]** |
| 8 | **ID concurrent** | `55` | **[M]** entier, clé de jointure |
| 9–11 | — | vides | **[?]** |
| 12 | skipper | `Chad Stenwick` | **[M]** texte libre, peut être vide |
| 13–14 | — | vides | **[?]** |

**[M]** Sur la référence YB, les ID sont uniques mais ni consécutifs ni
ordonnés, et l'ordre des lignes est décroissant par nom (ASCII). Chez Geovoile
(v1.5) c'est l'inverse : ID consécutifs de 1 à 45, lignes croissantes par ID,
noms triés alphabétiquement selon une collation linguistique et non par octets
(`Acromégalies` < `AD HOC` < `Afuté`). Deux conventions opposées : **l'ordre
n'est pas signifiant** et un lecteur ne doit rien en déduire. **[M]**

**[M]** Les champs 3–5 valent `1;3;1` partout. À recopier tels quels faute de
savoir ce qu'ils encodent.

**[M]** Les espaces internes sont significatifs à l'octet près : la référence
contient `David  Raney` et `Erica  Mattson Siegel`, avec deux espaces. Ne pas
normaliser.

## Fichier `.txt` (posreport)

### Ligne magique

```
POSADRENA
```

**[M]** Sans `;`. Sa valeur est annoncée par le champ 6 de l'en-tête `.dcc` —
et l'oracle Geovoile montre qu'elle **change bien d'un producteur à l'autre**
(`POSREPORT` au lieu de `POSADRENA`). Un lecteur doit donc prendre la valeur
dans le `.dcc` apparié plutôt que la coder en dur.

### Lignes de position — 5 champs, **pas** de `;` final

Une ligne par position. Plusieurs lignes peuvent porter le même ID : elles
forment alors la trace de ce bateau, à donner dans l'ordre chronologique.

```
1;55;21.2502N;157.4598W;07/29/24 02:17:50
```

| # | Champ | Exemple | |
|---|---|---|---|
| 1 | type d'enregistrement | `1` | **[H]** constant sur la référence |
| 2 | **ID concurrent** | `55` | **[M]** jointure avec le champ 8 du `.dcc` |
| 3 | latitude | `21.2502N` | **[M]** |
| 4 | longitude | `157.4598W` | **[M]** |
| 5 | horodatage, **`MM/JJ/AA HH:MM:SS`** | `07/29/24 02:17:50` | **[M]** cf. *Dates* |

L'absence de `;` final ici, alors que le `.dcc` en a un partout, est
**[M]** mesurée — ce n'est pas une coquille de la référence.

## Version 1.5 — en-tête, 14 champs, **pas** de `;` final

Mesuré sur `capmartinique2026.dcc` (Geovoile) :

```
Adrena - descriptif des concurrents;1.5;14/04/2026;cap martinique;0;POSREPORT;1;;;;;;;https://www.geovoile.net/capmartinique/public/posreport/?key=a78c…
```

| # | Champ | Exemple | |
|---|---|---|---|
| 1 | magic | `Adrena - descriptif des concurrents` | **[M]** identique à 1.3 |
| 2 | version | `1.5` | **[M]** |
| 3 | date, **`JJ/MM/AAAA`** | `14/04/2026` | **[M]** année sur 4 chiffres, contrairement à 1.3 |
| 4 | nom de la course | `cap martinique` | **[M]** casse libre, non normalisée |
| 5 | ? | `0` | **[?]** `0` chez les deux producteurs, dans les deux versions |
| 6 | **magic du posreport** | `POSREPORT` | **[M]** **variable** : `POSADRENA` chez YB, `POSREPORT` chez Geovoile |
| 7 | ? | `1` | **[?]** absent en 1.3 ; peut-être l'activation de la MAJ par URL **[H]** |
| 8–13 | — | vides | **[M]** vides chez les deux producteurs |
| 14 | **URL du posreport** | `https://…/posreport/?key=<32 hex>` | **[M]** |

Le champ 14 est ce qui distingue la variante dite « http » : le fichier de
positions n'a plus à être déposé localement, le logiciel va le chercher à
cette URL et le rafraîchit lui-même. Chez Geovoile l'URL n'a pas d'extension
et porte une **clé en query string** — donc ni chemin ni suffixe imposés, et
un consommateur doit prendre l'URL telle quelle.

**Le champ 6 n'est pas la constante que la v1.3 laissait croire.** Deux
producteurs, deux valeurs. Un lecteur qui teste `== "POSADRENA"` rejette un
fichier Geovoile parfaitement valide : c'est le champ 6 du `.dcc` qui dit
quelle ligne magique attendre en tête du posreport, pas l'inverse.

## Version 1.5 — lignes concurrent, 24 champs, `;` final

Mesuré sur les 45 lignes de `capmartinique2026.dcc` :

```
Acromégalies, Pas Seulement…;Duo;1;21.00;7.00;36863;;1;0;1.046000000000000041;O;Perrin Laurent;0;1;0;;-1;100;0;N;1;0,0,255,-1,default.wav,10,,0,,,,,,,,;1;0,0,255,-1,default.wav,10,,0,,,,,,,,;
```

« Varie ? » se lit **à l'intérieur de cet oracle** : un champ constant sur 45
concurrents d'une même course peut rester un réglage par flotte.

| # | Champ | Exemple | Varie ? | |
|---|---|---|---|---|
| 1 | nom du bateau | `Acromégalies, Pas Seulement…` | oui | **[M]** virgules et cp1252 admis |
| 2 | série / catégorie | `Duo`, `Solo` | oui | **[M]** texte libre : Geovoile y met la catégorie, pas la série |
| 3 | ? | `1` | non | **[?]** `1` chez les deux producteurs |
| 4 | **longueur**, m | `21.00` | non | **[H]** voir ci-dessous |
| 5 | **largeur** (bau), m | `7.00` | non | **[H]** voir ci-dessous |
| 6 | **couleur, entier RGB** | `36863` | oui | **[M]** `R<<16 \| G<<8 \| B`, 45 valeurs distinctes |
| 7 | — | vide | non | **[M]** vide chez les deux |
| 8 | **ID concurrent** | `1` | oui | **[M]** 1…45, consécutifs ; même position qu'en 1.3 |
| 9 | ? | `0` | non | **[?]** |
| 10 | **rating** | `1.046000000000000041` | oui | **[M]** ~0,98 à 1,05 ; **peut être vide** ou `0` |
| 11 | ? | `O` | non | **[?]** la lettre O, pas un zéro. Bool. « Oui » ? Non élucidé |
| 12 | **skipper** | `Perrin Laurent` | oui | **[M]** `Nom Prénom` ici ; **même place qu'en 1.3** |
| 13 | ? | `0` | non | **[?]** |
| 14 | ? | `1` | non | **[?]** |
| 15 | ? | `0` | non | **[?]** |
| 16 | — | vide | non | **[?]** |
| 17 | ? | `-1` | non | **[?]** |
| 18 | ? | `100` | non | **[?]** |
| 19 | ? | `0` | non | **[?]** |
| 20 | ? | `N` | non | **[?]** la lettre N. Bool. « Non » ? Non élucidé |
| 21 | ? | `1` | non | **[?]** |
| 22 | bloc d'affichage / alarme | `0,0,255,-1,default.wav,10,,0,,,,,,,,` | non | **[M]** |
| 23 | ? | `1` | non | **[?]** identique au 21 |
| 24 | bloc identique au 22 | idem | non | **[M]** |

**[M]** Les champs 3, 7, 9, 11, 13 à 21 et 23 portent **les mêmes valeurs
chez les deux producteurs** (`1;…;;…;0;…;O`, `0;1;0;;-1;100;0;N;1`). Deux
générateurs indépendants recopiant la même suite : c'est le squelette attendu
par le lecteur. À recopier tel quel, sans prétendre le comprendre.

### Champ 12 : le skipper, pas le nom répété

Le fichier ChatGPT répétait le nom du bateau à cette place, ce qui laissait la
question ouverte. Geovoile y met 45 patronymes distincts, tous différents du
nom du bateau : **le champ 12 reste le skipper, exactement comme en 1.3**.

### Champs 4 et 5 : dimensions, mais valeurs par défaut ici **[H]**

`21.00` et `7.00` sur les 45 lignes — d'une flotte de voiliers de série de 9 à
12 m. Ce ne sont donc **pas** les dimensions réelles, mais un défaut de
générateur. La sémantique longueur/largeur reste plausible (l'autre échantillon
porte `18.28`/`5.85`, soit exactement 60 pieds), elle n'est **pas** démontrée
et le champ n'est de toute façon pas fiable à la lecture.

### Champ 10 : rating

45 valeurs, de `0.9799999999999999822` à `1.046000000000000041` — un double
sérialisé sans arrondi, à recopier tel quel plutôt qu'à reformater. Un
concurrent a le champ **vide**, un autre `0` : ne pas exiger un nombre.

### La couleur, champ 6 — vérifié

Entier décimal, `R<<16 | G<<8 | B`. Contrôlé sur les six équipes contre les
couleurs publiées par le tracker PredictWind, dont quatre sont asymétriques
et donc discriminantes :

| Équipe | Champ 6 | RGB | Couleur du tracker |
|---|---|---|---|
| MSIG Europe | `3022968` | 46, 32, 120 | `#2e2078` |
| 11th Hour Racing | `16745984` | 255, 134, 0 | `#ff8600` |
| United by the Ocean | `3109375` | 47, 113, 255 | `#2f71ff` |
| Team Malizia | `14232092` | 217, 42, 28 | `#d92a1c` |

Ce n'est donc **pas** le `TColor` de Delphi, qui serait en BGR — malgré
l'ascendance Windows du logiciel.

L'oracle Geovoile confirme l'usage : 45 concurrents, 45 entiers distincts, de
`10905` (0,42,153) à `16771072` (255,222,0) — des teintes vives et bien
réparties, ce qu'on attend d'une palette de flotte.

### Les blocs 22 et 24

Sous-champs séparés par des virgules, 16 positions, les deux blocs identiques
sur tous les échantillons :

```
0,0,255,-1,default.wav,10,,0,,,,,,,,
│ │  │   │       │      │   │
│ │  │   │       │      │   └── 8  : ?  `0`
│ │  │   │       │      └────── 6  : ?  `10`
│ │  │   │       └───────────── 5  : fichier son, `default.wav`
│ │  │   └───────────────────── 4  : ?  `-1`
└─┴──┴───────────────────────── 1-3: un triplet R, G, B
```

Les positions 7 et 9 à 16 sont vides. La présence d'un `.wav` et d'un `-1`
évoque une configuration d'alarme par concurrent **[H]** ; les deux blocs
pourraient être deux alarmes distinctes, ou une alarme et un réglage
d'affichage. **[?]**

**Correction : le triplet ne reprend pas le champ 6.** Chez Geovoile il vaut
`0,0,255` sur les 45 lignes, pendant que le champ 6 prend 45 valeurs
distinctes. Le fichier ChatGPT, où les deux coïncidaient, avait tous ses
concurrents en blanc — coïncidence, pas règle. Le triplet est donc une couleur
**d'alarme ou d'affichage**, indépendante de la couleur du bateau. **[H]**

## Coordonnées

Degrés et minutes décimales **concaténés autour du point**, hémisphère suffixé.
Ce n'est ni un degré décimal, ni du NMEA standard.

```
21.2502N
││ ││ └┴── centièmes de minute
││ └┴───── minutes entières
└┴──────── degrés
        = 21° 25,02′ N = 21,4170°
```

- **[M]** Toujours 4 chiffres après le point : `MMmm`.
- **[M]** Suffixe `N`/`S` en latitude, `E`/`W` en longitude.
- **[M]** Aucun signe, aucun espace.
- Résolution : 0,01′ ≈ **18,5 m**.
- Report du carry : 59,996′ arrondit à 60,00′, qui appartient au degré suivant
  — `21,99993°` s'écrit `22.0000N`, jamais `21.6000N`.

### Zéro-padding : non tranché **[?]**

La référence ne contient que des latitudes 21°–37° et des longitudes
122°–157° : **aucune valeur sous 10° ou sous 100°**. Impossible d'y distinguer
largeur fixe de largeur libre.

L'arrivée à Lorient est vers 3°W, donc la question est bloquante :

```
003.2160W    largeur fixe (2 chiffres en lat, 3 en lon) — hypothèse NMEA
  3.2160W    largeur libre
```

À trancher **empiriquement** dans qtVlm avec un fichier de test, avant la
course. Tant que ce n'est pas fait, produire les deux variantes.

## Dates : deux formats, volontairement

| Emplacement | Format | Exemple |
|---|---|---|
| `.dcc`, en-tête champ 3 | `JJ/MM/AA` | `02/09/26` = 2 septembre 2026 |
| `.txt`, champ 5 | `MM/JJ/AA HH:MM:SS` | `07/29/24` = 29 juillet 2024 |

**[M]** Confirmé sur une même paire issue du même générateur au même instant :

- le `.dcc` de `yb.tl` est régénéré à chaque requête et son en-tête porte la
  date du jour du téléchargement — un téléchargement le 2 septembre 2026 donne
  `02/09/26`, donc `JJ/MM/AA` ;
- le posreport de cette même flotte porte `07/26/24` à `08/02/24`, avec des
  valeurs 26 à 31 en deuxième position — impossibles comme mois, donc
  `MM/JJ/AA`.

Ne pas « harmoniser » les deux.

**[?] Fuseau horaire.** Non déterminé. UTC est probable **[H]**. Test : comparer
la position affichée par qtVlm à l'heure du dernier point du tracker source.

## Grammaire

```abnf
; version 1.3 ; en 1.5 : CRLF, date sur 4 chiffres d'année, 14 champs
; d'en-tête sans ";" final et 24 champs par concurrent.
dcc          = dcc-header LF *(competitor LF)
dcc-header   = "Adrena - descriptif des concurrents" ";" version ";" ddmmyy
               ";" race ";" "0" ";" posmagic ";"
competitor   = name ";" class ";" "1;3;1;;" ";" id ";;;" ";" skipper ";;" ";"

; posmagic est un champ, pas une constante : "POSADRENA" (YB Tracking),
; "POSREPORT" (Geovoile). Le posreport doit porter celui de son .dcc.
posreport    = posmagic LF *(fix LF)
fix          = "1" ";" id ";" lat ";" lon ";" mmddyy SP hhmmss
posmagic     = 1*(%x21-3A / %x3C-FF)

lat          = 1*3DIGIT "." 4DIGIT ("N" / "S")
lon          = 1*3DIGIT "." 4DIGIT ("E" / "W")
id           = 1*DIGIT
name         = 1*(%x20-3A / %x3C-FF)      ; tout sauf ";" et les contrôles
```

## Exemple minimal complet

`atlantic2026.dcc` :

```
Adrena - descriptif des concurrents;1.3;15/01/26;Atlantic 2026;0;POSADRENA;
Biotherm;IMOCA;1;3;1;;;1;;;;Paul Meilhat;;;
Malizia - Seaexplorer;IMOCA;1;3;1;;;2;;;;Boris Herrmann;;;
```

`atlantic2026.txt` :

```
POSADRENA
1;1;47.4489N;003.2170W;01/15/26 11:00:00
1;1;47.4501N;003.2204W;01/15/26 12:00:00
1;2;21.2502N;157.4598W;01/15/26 10:04:30
```

Le bateau 1 a deux positions : c'est sa trace. Le bateau 2 n'en a qu'une.

## Pièges

1. **Les ID sont la seule identité.** Un ID qui change de titulaire entre deux
   posreports fait téléporter un bateau. Le mapping nom → ID doit être
   persistant et append-only.
2. **Pas d'échappement.** Un `;` dans un nom décale tous les champs suivants.
   Le remplacer, par exemple par une virgule.
3. **Encodage.** Un nom accentué écrit en UTF-8 dans un fichier lu en
   ISO-8859-1 donne du charabia silencieux — jamais une erreur. Symétriquement,
   **lire du cp1252 comme de l'ISO-8859-1** transforme `…` et `’` en
   caractères de contrôle, tout aussi silencieusement : lire en `cp1252`.
4. **`/` dans le nom de course** : qtVlm en fait un chemin et échoue.
5. **Carry des minutes** à l'arrondi (voir *Coordonnées*).
6. **Le posreport n'a pas de `;` final**, contrairement au `.dcc`.
7. **`POSADRENA` n'est pas une constante.** C'est la valeur du champ 6 du
   `.dcc` apparié ; Geovoile écrit `POSREPORT`. Un lecteur qui la code en dur
   rejette des fichiers valides.
8. **Un seul point par bateau ne donne pas de trace.** L'échantillon de
   référence est un instantané ; en déduire que le format l'impose est une
   erreur de lecture — coûteuse, puisqu'elle produit un fichier qui semble
   correct mais n'affiche presque rien.

## Non exploré

- **Le posreport de la v1.5.** Aucun échantillon : l'URL du champ 14 de
  l'oracle Geovoile répond 404 depuis la fin de la course. On ignore donc si
  ses lignes de position diffèrent de celles de la 1.3 — nombre de champs,
  fin de ligne, format de date. **[?]**
- **À trancher en priorité : qu'accepte qtVlm ?** Charger `capmartinique2026.dcc`
  (v1.5 authentique) puis un fichier de ce dépôt. La structure v1.5 est
  maintenant mesurée, mais rien ne dit encore ce que le *lecteur* tolère.
- **[?]** Sémantique des champs 1.3 : 3–5, 6–7, 9–11, 13–14.
- **[?]** Sémantique des champs 1.5 restants : 3, 7, 9, 11 (`O`), 13–21, 23,
  et les sous-champs 4 à 16 des blocs d'alarme.
- **[?]** Amplitude admise pour l'ID concurrent. Les échantillons n'emploient
  que de petits entiers — 1 à 64 chez YB, 1 à 45 chez Geovoile. Rien ne dit
  qu'un ID à six chiffres passe.
- **[?]** Autres valeurs possibles du magic posreport et du champ « type
  d'enregistrement ».
- **[?]** Le format varie d'une course à l'autre selon les producteurs. Écrire
  des lecteurs stricts qui échouent bruyamment plutôt que de deviner.
