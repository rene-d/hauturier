# nav — carnet de marées

Génère un PDF de marées et de créneaux de porte de bassin pour une liste de ports et
une plage de dates. Successeur de `../shom/`, dont l'endpoint SHOM
`services.data.shom.fr` ne répond plus (l'ancien répertoire est conservé tel quel).

Python + Typst. Pas de LaTeX. Aucune éphéméride ni base de données embarquée.

## Commandes

```sh
./nav.py                       # config.yaml -> build/nav.pdf
./nav.py -c x.yml -o x.pdf --open
./nav.py --no-cache            # ignore le cache HTTP
./nav.py --search "aber"       # cherche l'identifiant d'un lieu de marée
make | make open | make refresh | make verif | make clean | make distclean

./verif_porte_trebeurden.py    # écart entre la porte de Trébeurden et son PDF officiel
./verif_porte_trebeurden.py --calibrate   # balaye seuil × décalage
./perros.py -j 12-18 -s 7.40:8.10:7.65   # étude des seuils d'un bassin
```

Les scripts ont un shebang `uv run --script` avec dépendances PEP 723
(`requests`, `lxml`, `pyyaml`). `typst` doit être dans le `PATH`, et `pdftotext`
(poppler) pour `verif_porte_trebeurden.py` seulement.

## Flux

```
config.yaml ─▶ nav.py ─▶ build/data.json ─▶ template.typ ─▶ build/nav.pdf
                 │
                 ├─▶ meteoconsult.py   HTTP + cache disque, parsing des pages
                 ├─▶ porte.py          interpolation des hauteurs, créneaux de porte
                 └─▶ lune.py           fraction éclairée du disque lunaire
```

`nav.py` ne produit qu'un JSON ; `template.typ` le lit via `json(sys.inputs.data)`.
La mise en page se retouche donc sans toucher au Python. Les pages mensuelles et la
correspondance nom → identifiant sont mises en cache dans `cache/`.

| fichier | rôle |
|---|---|
| `nav.py` | CLI, lecture du YAML, assemblage du JSON, appel à Typst |
| `meteoconsult.py` | client HTTP, recherche de ports, parsing des pages mensuelles |
| `porte.py` | dataclass `Gate`, interpolation, créneaux d'ouverture |
| `lune.py` | fraction éclairée et sens (croissante / décroissante) |
| `template.typ` | mise en page (tableau ports × jours, dessins) |
| `verif_porte_trebeurden.py` | comparaison au calendrier officiel de Trébeurden |
| `perros.py` | script d'étude : trouver les seuils d'un bassin |

## Source des marées

**marine.meteoconsult.fr**, une page HTML par port et par mois, scrapée avec `lxml` :
heures, hauteurs, coefficients, lever/coucher du soleil, phase de lune.

- Recherche d'un port : `GET /meteo-marine/recherche-horaires-marees?q=<nom>`
  redirige en 302 vers la page du port quand la réponse est unique, et renvoie une
  liste sinon. Une seule requête, pas de table de ports à maintenir.
- Page mensuelle :
  `/meteo-marine/horaires-des-marees/<slug>-<id>/<mois>-<annee>`.
  Chaque journée est un `div.tide` : `div.tide-line` (un demi-cycle et son
  coefficient) et `div.ephemeris` (soleil, lune).

### Pièges vérifiés

- **Les mois écoulés ne sont pas publiés.** Le site sert alors silencieusement la
  même période de l'année suivante : demander « janvier 2026 » en septembre 2026
  renvoie janvier 2027. `Client.month_page()` compare le titre de la page au mois
  demandé et lève `ScrapeError`. Ne pas retirer cette vérification : sans elle, un
  document se remplit de données fausses sans le moindre signe.
- **Les mois de débordement d'une porte sont optionnels.** Un créneau peut être à
  cheval sur la frontière du mois, donc `collect()` charge aussi les mois adjacents ;
  leur absence n'est pas bloquante (avertissement sur stderr), contrairement aux mois
  réellement demandés.
- **Chaque port est publié à son heure locale** : Portsmouth et les îles
  anglo-normandes sont en heure britannique, pas française. Le fuseau est déduit
  automatiquement du **pays annoncé dans la page** (`Pays':\`Royaume-Uni\``), via la
  table `COUNTRY_TZ` de `meteoconsult.py` ; la **longitude**, également présente dans
  la page, départage les archipels à fuseau distinct (Canaries, Açores, Madère). Le
  fuseau est mémorisé dans `cache/ports.json` avec l'identifiant du port.
  Priorité : `timezone` de l'entrée > `timezone` global du YAML > fuseau déduit >
  `Europe/Paris` avec avertissement sur stderr. Ne pas coder le fuseau en dur dans un
  YAML sans raison : la détection est plus sûre qu'une saisie manuelle.
- **Pas de coefficients hors de France** (Jersey, Guernesey) : colonne vide, ce n'est
  pas un défaut de parsing.
- Le décalage UTC est recalculé horaire par horaire via `zoneinfo`, pas déduit de la
  date : les jours de changement d'heure mélangent `+1` et `+2`.

### Recouper avec une autre source (îles Britanniques)

ADMIRALTY EasyTide (UKHO, officiel) expose du JSON sans clé ni inscription :

```
https://easytide.admiralty.co.uk/Home/GetStations
    GeoJSON, 709 stations : Id, Name, Country, coordonnées
https://easytide.admiralty.co.uk/Home/GetPredictionData?stationId=0065&PredictionLength=7
    tidalEventList (eventType 0 = PM, 1 = BM), courbe 30 min, phases de lune
https://easytide.admiralty.co.uk/Home/GetOffsetMinutes?stationId=0065
    {"baseOffset":0,"currentOffset":60,"dstOffset":60}
```

**Piège** : les `dateTime` de `tidalEventList` sont en **GMT** malgré l'absence de
suffixe `Z` ; c'est le navigateur qui ajoute `currentOffset` (le site l'annonce par
« All times have been adjusted by adding one hour to GMT »). Les lire comme des
heures locales donne un faux décalage d'une heure — erreur commise puis corrigée.

L'horizon est de 7 jours glissants, quel que soit `PredictionLength` (14 ou 28
renvoient la même chose). Pour l'année complète il faut l'API Premium ou le Tidal
Prediction Service, payants.

Recoupement fait en septembre 2026, après conversion correcte : Portsmouth +4,3 min,
St Helier −4,5, St Peter Port −5,8, Dover +11,1 ; hauteurs à 0,11 m près. Météo
Consult publie donc bien ces ports en heure locale britannique, marées **et** soleil.
La dispersion de Portsmouth (−23 à +39 min) tient à la pleine mer en palier du
Solent, dont l'instant se définit différemment selon les modèles.

Contrôle indépendant du fuseau, sans source tierce : le milieu entre lever et coucher
publiés doit tomber sur le midi solaire vrai (12 h − longitude×4 min − équation du
temps). Écart mesuré : +0,5 min à Portsmouth en heure britannique, +0,6 min à Brest
en heure française.

## Portes de bassin

Une porte s'ouvre quand la hauteur d'eau franchit sa cote d'ouverture en montant et
se referme au retour sous sa cote de fermeture. Entre deux extrêmes, la hauteur est
interpolée (`sine` par défaut, `twelfths` pour la règle des douzièmes ; l'écart entre
les deux est de l'ordre de 0,3 min).

Le calcul se fait sur des `datetime` *aware* convertis en absolu, sinon les nuits de
changement d'heure décalent d'une heure.

`Gate` (dans `porte.py`) porte tous les réglages : `threshold`, `close`,
`neap_close` / `neap_below`, `min_coef`, `model`, `time_offset`, `height_offset`.
Les ports connus sont dans `GATE_PRESETS` (`nav.py`) ; pour tout autre bassin,
`threshold` devient obligatoire. Tout est surchargeable depuis le YAML.

### Trébeurden — bassin à flot

Cote d'ouverture annoncée **4,30 m** / zéro des cartes, radier à **2,80 m** (il reste
1,50 m d'eau à l'ouverture). Météo Consult y publie des hauteurs **0,25 m plus
basses** que la référence du port et des horaires **8 min en avance** : d'où
`height_offset: 0.25` et `time_offset: 8`, qui traduisent un décalage de datum et non
un seuil bricolé.

Vérifié par `verif_porte_trebeurden.py` contre le PDF officiel du port, 436 horaires de
septembre à décembre 2026 : **4,6 min** d'écart moyen (ouvertures 6,2 ; fermetures
3,1 ; 91 % à ±10 min).

Avec un `draft`, un second créneau donne le passage du bateau au-dessus du radier, à
`sill + draft + clearance` — soit 2,80 + 2,10 + 0,40 = **5,30 m**.

### Perros-Guirec — seuil basculant du Linkin

Le port ne publie pas ses cotes ; elles ont été retrouvées en inversant le calcul
depuis les horaires du guide annuel (méthode : relever une heure d'ouverture réelle,
demander la hauteur d'eau à cet instant — c'est ce que fait `perros.py --hauteur`).

- ouverture **7,40 m** (écart-type 0,01 m sur les relevés)
- fermeture **8,10 m** en vives-eaux, **7,65 m** sous le coefficient 70 — deux
  régimes nets, séparés par une discontinuité franche entre coef 69 et 70
- **pas d'ouverture sous le coefficient 49** : le port ne manœuvre pas, même quand la
  cote est atteinte
- aucun recalage de la source : les heures Météo Consult y sont justes
- pas de créneau bateau : le guide ne publie pas la cote du radier, donc `draft` y est
  refusé avec un message explicite plutôt que calculé sur une valeur inventée

Sur les 178 horaires de septembre-octobre 2026 : ouvertures **0,8 min** (97 % à
±5 min), fermetures **5,1 min** (75 %). Le nombre de créneaux tombe exactement sur
celui du guide (44 en septembre, 45 en octobre).

### Limites connues

- Quand une basse mer passe à moins de 25 cm d'un seuil (`GATE_MARGIN`), quelques
  centimètres d'erreur déplacent la fermeture d'une heure ou la suppriment. Ces jours
  sont marqués d'un astérisque rouge plutôt que donnés pour exacts.
- En morte-eau franche la porte peut rester ouverte plusieurs jours (« ouverte en
  continu ») ; le bateau garde ses créneaux autour des pleines mers.
- Quand la pleine mer n'atteint pas la cote de fermeture, le calcul retombe sur la
  cote d'ouverture. Le guide de Perros ferme alors *à l'étale* : environ 33 min
  d'écart, toujours du côté prudent. Non corrigé à ce jour.

## Lune

Météo Consult ne publie que la phase en huit crans. `lune.py` calcule la fraction
éclairée par les formules abrégées de Meeus (ch. 47-48), précises à mieux que 0,5 %,
et le sens par la variation de l'illumination — ce qui reste juste les jours de
nouvelle et de pleine lune, où la phase publiée ne dit rien du sens. Contrôlé sur
122 jours publiés : zéro désaccord hors de ces deux phases.

Le pourcentage sert aussi à dessiner la vignette à la bonne forme (largeur du
terminateur) au lieu de huit formes figées.

## Mise en page

`template.typ` — tableau ports en lignes × jours en colonnes, découpé en tranches de
`columns` jours. Points à connaître :

- Tout est dessiné en Typst, sans police à emojis ni image : lune, porte de bassin,
  triangle d'avertissement. Un PDF doit rester lisible partout.
- Les cellules sont `breakable: false`, sinon une ligne se scinde entre deux pages en
  laissant sa ligne soleil orpheline.
- Le bloc lune déborde vers le haut (`place` dans un box de faible hauteur) pour ne
  pas coûter de hauteur à chaque ligne — il en coûtait 26 % en empilement naïf.
- Le décalage UTC est un exposant coloré (rouge `+2`, bleu `+1`) à droite de l'heure.
- `landscape` bascule automatiquement dès `columns >= 5`.
- Au-delà de 7 colonnes, les cellules deviennent trop étroites et les hauteurs
  chevauchent les heures. Connu, non corrigé.

## Conventions

- Commentaires et messages en français, comme le reste du dépôt.
- Le fichier de configuration est `config.yaml` ; `config.yml` reste accepté.
- Les chiffres de calage ne se changent pas à vue : ils viennent d'une comparaison
  mesurée à un calendrier officiel. Si un réglage bouge, relancer `make verif` (ou
  `perros.py`) et reporter le nouveau chiffre ici et dans le `README.md`.
- Le cache est volontairement agressif : les pages mensuelles sont figées. Utiliser
  `--no-cache` pour forcer, `make distclean` pour tout purger.
