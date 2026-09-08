# nav — carnet de marées

Génère un PDF récapitulatif des marées (PM/BM, hauteurs, coefficients, lever et
coucher du soleil, phase de lune) pour une liste de ports et une plage de dates.

Successeur de `shom/` : l'endpoint SHOM `services.data.shom.fr` ne répond plus.

- **Source des données** : pages « horaires des marées » de
  [Météo Consult Marine](https://marine.meteoconsult.fr/) — une page HTML par port
  et par mois, scrapée avec `lxml`. Le pourcentage de lune éclairée n'y figure pas :
  il est calculé (`lune.py`, formules de Meeus) et sert aussi à dessiner la vignette
  à la bonne forme plutôt qu'en huit crans. La flèche qui suit le pourcentage donne
  le sens (↑ croissante, ↓ décroissante), déduit de la variation de l'illumination :
  c'est juste aussi les jours de nouvelle et de pleine lune, où la phase publiée ne
  dit rien du sens. Les horaires sont publiés à l'heure locale du
  port ; le décalage avec UTC (`+1` en bleu, `+2` en rouge) est recalculé horaire
  par horaire via `zoneinfo` et affiché en exposant, y compris les jours de
  changement d'heure où une même journée mélange les deux.
- **Mise en page** : [Typst](https://typst.app/) (`template.typ`), plus de LaTeX.
- **Configuration** : un fichier YAML (`config.yaml`).

```
config.yaml ──▶ nav.py ──▶ build/data.json ──▶ template.typ ──▶ build/nav.pdf
                  │
                  └──▶ meteoconsult.py (HTTP + cache dans cache/)
```

## Utilisation

```sh
./nav.py                            # config.yaml -> build/nav.pdf
./nav.py -c tregor.yml -o tregor.pdf
./nav.py --open                     # ouvre le PDF à la fin
./nav.py --no-cache                 # ignore le cache HTTP
./nav.py --search "aber"            # cherche l'identifiant d'un lieu de marée
make / make open / make refresh / make clean
```

Le shebang lance `uv run --script` : les dépendances (`requests`, `lxml`, `pyyaml`)
sont déclarées dans l'en-tête PEP 723 de `nav.py` et installées à la volée. Sans
`uv`, `python3 nav.py` fonctionne si ces trois paquets sont présents. `typst` doit
être dans le `PATH` (`brew install typst`).

Les pages mensuelles téléchargées et la correspondance nom → identifiant sont mises
en cache dans `cache/` ; `--no-cache` force le rechargement.

## Configuration

```yaml
title: Trégor        # titre du document
start: 2026-09-08    # date de début, ou "today"
days: 3              # nombre de jours (ou bien `end: 2026-09-10`)
columns: 3           # jours par tableau
paper: a4            # format de page Typst
landscape: false     # orientation ; par défaut, paysage dès `columns >= 5`
timezone: Europe/Paris   # facultatif : force le fuseau, sinon déduit du port

ports:
  - Brest                          # nom résolu par la recherche du site
  - L'Aber Wrac'h
  - name: Ile de Bréhat (Port Clos)
    label: Bréhat                  # nom affiché dans le tableau
  - id: 965                        # identifiant direct de la page marées
    slug: trebeurden
    label: Trébeurden
  - name: SAINT HELIER, JERSEY
    timezone: Europe/Jersey        # port hors de France : fuseau à préciser
```

### Porte de bassin à flot

Un item dont le nom commence par « PORTE » (ou qui porte une clé `gate:`) n'affiche
pas les marées mais les **créneaux d'ouverture de la porte** du bassin, déduits des
hauteurs d'eau : la porte s'ouvre quand la mer franchit sa cote d'ouverture en
montant et se referme au retour sous sa cote de fermeture.

```yaml
ports:
  - PORTE TREBEURDEN          # forme courte, réglages préenregistrés
  - PORTE PERROS-GUIREC
  - gate: Trébeurden          # forme explicite
    label: Porte Trébeurden
    draft: 2.10               # tirant d'eau ; sans lui, pas de créneau bateau
    clearance: 0.40           # pied de pilote
    sill: 2.80                # cote du radier / zéro des cartes
    threshold: 4.30           # cote d'ouverture
    close: 8.10               # cote de fermeture (défaut : celle d'ouverture)
    neap_close: 7.65          # cote de fermeture en mortes-eaux
    neap_below: 70            # coefficient sous lequel on passe en mortes-eaux
    min_coef: 49              # sous ce coefficient, la porte ne s'ouvre pas du tout
    height_offset: 0.25       # recalage des hauteurs de la source
    time_offset: 8            # recalage des horaires, en minutes
    model: sine               # `sine` ou `twelfths` (règle des douzièmes)
    warn_coef: 70             # au-delà, triangle d'avertissement
```

Deux ports sont préréglés dans `GATE_PRESETS` (`nav.py`) ; pour tout autre, il faut
au moins donner `threshold`. Les réglages viennent de la comparaison au calendrier
officiel de chaque port :

| | Trébeurden | Perros-Guirec (Linkin) |
|---|---|---|
| ouverture | 4,30 m | 7,40 m |
| fermeture | idem | 8,10 m, ou 7,65 m sous coef 70 |
| pas d'ouverture | — | coefficient < 49 |
| recalage source | +0,25 m, +8 min | aucun |
| écart au calendrier officiel | 4,6 min (436 horaires) | 4,3 min (178 horaires) |

**Vives-eaux et mortes-eaux.** Le seuil de fermeture n'est pas toujours le même
selon le marnage. À Perros-Guirec la cote relevée est de 8,10 m au-dessus du
coefficient 70 et de 7,63 m en dessous — deux régimes nets, à 0,07 m d'écart-type
chacun. Renseigner `neap_close` et `neap_below` fait passer l'écart moyen sur les
fermetures de 10,3 à 4,3 min. Sans `neap_close`, le seuil unique s'applique partout,
ce qui convient à Trébeurden.

**Coefficient minimal.** Certains bassins renoncent à la manœuvre en mortes-eaux
même quand la cote est atteinte : à Perros-Guirec le guide ne donne aucune ouverture
sous le coefficient 49. Sans `min_coef`, le calcul inventait 3 créneaux en septembre
et 4 en octobre ; avec, le compte tombe exactement sur celui du guide (44 et 45).

**Créneau du bateau.** Avec un tirant d'eau, un second créneau est calculé : celui où
le bateau passe au-dessus du radier, à `sill + draft + clearance`. À Trébeurden le
radier est à 2,80 m (il reste 1,50 m d'eau quand la porte s'ouvre à 4,30 m), donc
2,80 + 2,10 + 0,40 = **5,30 m** pour un tirant d'eau de 2,10 m. Le guide du port de
Perros-Guirec ne publie pas la cote de son radier : `draft` y est refusé avec un
message explicite plutôt que calculé sur une valeur inventée.

Un triangle orange marque les créneaux dont la pleine mer dépasse `warn_coef` : le
port de Trébeurden conseille alors d'attendre une vingtaine de minutes après
l'ouverture pour ne pas se faire surprendre par le courant dans la passe.

Deux limites à connaître :

- Quand une basse mer passe à moins de 25 cm d'un seuil, quelques centimètres
  d'erreur déplacent la fermeture d'une heure ou la suppriment : ces jours-là sont
  marqués d'un astérisque rouge.
- En morte-eau franche la porte peut rester ouverte plusieurs jours d'affilée
  (« ouverte en continu ») ; le bateau, lui, garde ses créneaux autour des pleines
  mers.

`./verif_porte_trebeurden.py` (`make verif`) mesure l'accord de Trébeurden avec le PDF officiel
du port, et `./perros.py` sert à trouver les seuils d'un bassin dont le port ne les
publie pas.

`timezone` ne décale aucun horaire : le site publie déjà l'heure locale du lieu,
c'est l'exposant `+1`/`+2` qui en dépend. À laisser tel quel pour la métropole.

Une plage de dates à cheval sur deux mois est gérée (deux pages sont téléchargées).
Chaque nom de port du tableau est un lien vers sa page de marées.

## Fichiers

| | |
|---|---|
| `nav.py` | CLI : lit le YAML, assemble `build/data.json`, appelle Typst |
| `meteoconsult.py` | client HTTP, cache, recherche de ports, parsing des pages |
| `lune.py` | fraction éclairée du disque lunaire |
| `porte.py` | interpolation des hauteurs et créneaux d'ouverture de porte |
| `verif_porte_trebeurden.py` | comparaison au calendrier officiel du port (nécessite `pdftotext`) |
| `perros.py` | script d'étude : créneaux d'ouverture pour un seuil à déterminer |
| `template.typ` | mise en page (tableau ports × jours, phases de lune dessinées) |
| `config.yaml` | exemple de configuration |
