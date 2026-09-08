// Carnet de marées — mise en page.
//
// Les données sont produites par nav.py :
//   typst compile --input data=build/data.json template.typ build/nav.pdf

#let data = json(sys.inputs.at("data", default: "build/data.json"))

#let ink       = rgb("#1c2128")
#let muted     = rgb("#6b7684")
#let rule      = rgb("#d5dae1")
#let band      = rgb("#eef2f6")
#let sea       = rgb("#0d5c8a")
#let night     = rgb("#3b4654")

// Palette des coefficients (mêmes seuils que les almanachs : mortes-eaux -> vives-eaux)
#let coef-color(c) = {
  if c == none { muted }
  else if c < 45 { rgb("#7d8a99") }
  else if c < 70 { rgb("#2f7d4f") }
  else if c < 95 { rgb("#b8791b") }
  else { rgb("#b3341f") }
}

// Phase de lune dessinée (pas de dépendance à une police à emojis) : un disque
// sombre, une moitié éclairée du bon côté, et un terminateur elliptique dont la
// largeur suit la fraction réellement éclairée.
#let moon(phase, pct, up, size: 8pt) = {
  let lit = rgb("#f2c14e")
  let dark = rgb("#9aa5b3")
  let k = if pct == none { if phase == "full" { 1.0 } else { 0.0 } } else { pct / 100 }

  box(baseline: 15%, clip: true, radius: 50%, width: size, height: size, fill: dark, {
    if phase != none {
      place(if up { right } else { left } + horizon,
        rect(width: size / 2, height: size, fill: lit, stroke: none))
      place(center + horizon, ellipse(
        width: calc.abs(1 - 2 * k) * size, height: size,
        fill: if k > 0.5 { lit } else { dark }, stroke: none))
    }
  })
}

// Vignette de lune, fraction éclairée et sens (montante / descendante). Le bloc
// déborde vers le haut au lieu de pousser la ligne : il ne coûte que la hauteur
// du pourcentage.
#let moon-block(day) = {
  let pct = day.at("moon_pct", default: none)
  let up = day.at("moon_waxing", default: true)
  box(width: 24pt, height: 5.5pt, {
    place(bottom + center, dy: -4.8pt, moon(day.moon, pct, up, size: 7pt))
    if pct != none {
      place(bottom + center, dy: 1.2pt, text(size: 5pt, fill: muted, {
        // espace fine insécable : « 100 % » doit tenir sur une ligne
        str(pct) + "\u{202F}%"
        h(0.8pt)
        if up { sym.arrow.t } else { sym.arrow.b }
      }))
    }
  })
}

#let hour(t) = if t == none { "--" } else { t }

// Triangle d'avertissement (dessiné : pas de dépendance à une police à emojis).
#let warn(s: 7.5pt) = box(width: s, height: s, baseline: 15%, {
  place(top + left, polygon(fill: rgb("#e0a03a"),
    (s / 2, 0pt), (s, s * 0.88), (0pt, s * 0.88)))
  place(top + left, dx: s / 2 - 0.6pt, dy: s * 0.3,
    rect(width: 1.2pt, height: s * 0.3, fill: white))
  place(top + left, dx: s / 2 - 0.6pt, dy: s * 0.68,
    rect(width: 1.2pt, height: 1.2pt, fill: white))
})

// Porte de bassin à flot, vue de face : deux bajoyers, deux vantaux, la ligne d'eau.
#let gate-icon(s: 15pt) = {
  let w = s * 1.5
  let post = s * 0.15
  let leaf = (w - 2 * post) / 2
  box(width: w, height: s, {
    place(top + left, dx: 0pt, rect(width: post, height: s * 0.8, fill: night))
    place(top + left, dx: w - post, rect(width: post, height: s * 0.8, fill: night))
    for i in (0, 1) {
      place(top + left, dx: post + i * leaf, dy: s * 0.14,
        rect(width: leaf, height: s * 0.52, stroke: 0.7pt + night, fill: white))
    }
    place(top + left, dy: s * 0.86, curve(
      stroke: 0.8pt + sea,
      curve.move((0pt, s * 0.06)),
      curve.quad((w * 0.25, -s * 0.04), (w * 0.5, s * 0.06)),
      curve.quad((w * 0.75, s * 0.16), (w, s * 0.06)),
    ))
  })
}

// Décalage avec UTC, en petit à droite de l'heure : rouge en été, bleu en hiver.
#let tz(u) = if u == none { [] } else {
  text(size: 5.5pt, weight: "regular", baseline: -2.5pt,
       fill: if u == "+2" { rgb("#b3341f") } else { rgb("#1f5fb3") },
       u)
}

// Une case = les marées d'un jour dans un port.
#let day-cell(day) = {
  if day == "pad" { return [] }
  if day == none {
    return align(center + horizon, text(fill: muted, size: 8pt)[pas de donnée])
  }

  set text(size: 8.5pt)
  block(width: 100%, breakable: false, {
    grid(
      columns: (auto, 1fr, auto, auto),
      column-gutter: (3pt, 3pt, 4pt),
      row-gutter: 1.7pt,
      ..day.tides.map(t => {
        let high = t.kind == "PM"
        let c = if high { sea } else { night }
        (
          text(fill: c, weight: if high { "bold" } else { "regular" }, t.kind),
          {
            text(fill: c, weight: if high { "bold" } else { "regular" }, hour(t.hour))
            tz(t.utc)
          },
          align(right, text(fill: muted, if t.height == none { "" } else { t.height + " m" })),
          align(right, if t.coef == none { [] } else {
            text(fill: coef-color(t.coef), weight: "bold", str(t.coef))
          }),
        )
      }).flatten()
    )

    v(2.5pt)
    line(length: 100%, stroke: 0.4pt + rule)
    v(2.5pt)
    text(size: 7.5pt, fill: muted)[
      #sym.arrow.tr #hour(day.sunrise)#tz(day.sunrise_utc)
      #h(5pt) #sym.arrow.br #hour(day.sunset)#tz(day.sunset_utc)
      #h(1fr) #moon-block(day) #h(1pt)
    ]
  })
}

// Une case « porte de bassin » = les créneaux d'ouverture du jour, et, si un tirant
// d'eau est configuré, les créneaux où le bateau franchit le radier.
#let gate-cell(day) = {
  if day == "pad" { return [] }
  if day == none {
    return align(center + horizon, text(fill: muted, size: 8pt)[pas de donnée])
  }

  set text(size: if day.labelled { 8pt } else { 8.5pt })
  block(width: 100%, breakable: false, {
    let doubt = if day.at("uncertain", default: false) {
      text(size: 7pt, fill: rgb("#b3341f"), baseline: -2.5pt, " *")
    } else { [] }

    if day.windows.len() == 0 {
      text(fill: muted)[fermée]
      doubt
    } else {
      grid(
        columns: (auto, auto, auto, auto, 1fr),
        column-gutter: (3pt, 2pt, 2pt, 4pt),
        row-gutter: 1.7pt,
        ..day.windows.enumerate().map(((i, w)) => {
          let boat = w.kind == "boat"
          let ink = if boat { sea } else { night }
          let weight = if boat { "bold" } else { "regular" }
          let label = if day.labelled {
            text(size: 6.5pt, fill: if boat { ink } else { muted }, weight: weight, w.label)
          } else { [] }

          if w.all_day {
            (label,
             grid.cell(colspan: 3, text(fill: ink, weight: weight)[ouverte en continu]),
             align(right, {
               if w.at("warn", default: false) { warn() }
               if i == 0 { doubt }
             }))
          } else {(
            label,
            if w.open == none { text(fill: muted)[…] } else {
              text(fill: ink, weight: weight, w.open); tz(w.open_utc)
            },
            text(fill: muted, sym.arrow.r),
            {
              if w.close == none { text(fill: muted)[…] } else {
                text(fill: ink, weight: weight, w.close)
                tz(w.close_utc)
                if w.close_day > 0 {
                  h(1.5pt)
                  text(size: 6pt, fill: muted, baseline: -2.5pt)[#sym.plus#w.close_day\u{2009}j]
                }
              }
            },
            align(right, {
              // avec deux seuils la place manque : les deux heures suffisent
              if not day.labelled and w.duration != none {
                text(size: 7pt, fill: muted, w.duration)
              }
              if w.at("warn", default: false) { h(2pt); warn() }
              if i == 0 { doubt }
            }),
          )}
        }).flatten()
      )
    }

    v(2.5pt)
    line(length: 100%, stroke: 0.4pt + rule)
    v(2.5pt)
    text(size: 7.5pt, fill: muted)[
      #sym.arrow.tr #hour(day.sunrise)#tz(day.sunrise_utc)
      #h(5pt) #sym.arrow.br #hour(day.sunset)#tz(day.sunset_utc)
      #h(1fr) #moon-block(day) #h(1pt)
    ]
  })
}

#let date-head(d) = if d == "pad" { [] } else {
  align(center, text(size: 9.5pt, weight: "bold", fill: ink, d.label))
}

// Un tableau : les ports en lignes, un paquet de jours en colonnes.
#let tide-table(dates, ports, cols) = {
  let n = dates.len()  // colonnes réellement remplies (la dernière tranche peut être courte)
  let pad = ("pad",) * (cols - n)
  let dates = dates + pad
  table(
    columns: (auto, ..(1fr,) * cols),
    inset: (x: 6pt, y: 5pt),
    align: horizon,
    stroke: (x, y) => (
      left: if x == 0 or x > n { none } else { 0.4pt + rule },
      right: none,
      top: if y == 0 or x > n { none } else { 0.4pt + rule },
      bottom: none,
    ),
    fill: (x, y) => if x > n { none }
      else if y == 0 { band }
      else if calc.even(y) { rgb("#f8fafc") },

    table.header(
      [],
      ..dates.map(date-head)
    ),
    ..ports.map(p => (
      if p.kind == "gate" {
        table.cell(align: top + left, block(width: 5.6em, breakable: false, {
          align(center, gate-icon())
          v(4pt)
          text(size: 8.5pt, weight: "bold", fill: ink, link(p.url, p.label))
        }))
      } else {
        block(width: 5.6em, breakable: false,
          text(size: 8.5pt, weight: "bold", fill: ink, link(p.url, p.label)))
      },
      ..(p.days + pad).map(if p.kind == "gate" { gate-cell } else { day-cell }),
    )).flatten()
  )
}

#set document(title: data.title + " — marées", author: "nav.py")
#set page(
  paper: data.paper,
  flipped: data.flipped,
  margin: (x: 12mm, y: 13mm),
  footer: context text(size: 7.5pt, fill: muted)[
    Heures locales, décalage avec UTC en exposant.
    Source : #link(data.source.url, data.source.name).
    #if data.at("gate_note", default: none) != none [ #data.gate_note ]
    Établi le #data.generated.
    #h(1fr)
    #counter(page).display("1/1", both: true)
  ],
)
#set text(font: ("Helvetica Neue", "Helvetica", "Arial"), size: 9pt, fill: ink, lang: "fr")
#show link: it => it

#block(below: 10pt, {
  text(size: 17pt, weight: "bold", data.title)
  h(8pt)
  text(size: 10pt, fill: muted, data.period)
})

// Découpage en paquets de `columns` jours.
#let chunks = range(0, data.dates.len(), step: data.columns).map(i => (
  dates: data.dates.slice(i, calc.min(i + data.columns, data.dates.len())),
  ports: data.ports.map(p => (
    label: p.label,
    url: p.url,
    kind: p.at("kind", default: "tides"),
    days: p.days.slice(i, calc.min(i + data.columns, data.dates.len())),
  )),
))

#for (i, c) in chunks.enumerate() {
  if i > 0 { v(8pt) }
  tide-table(c.dates, c.ports, data.columns)
}
