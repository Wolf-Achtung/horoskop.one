# Bild-Generierungs-Briefing: Die Mondlese — Materialwelt „Knochen, Kalk & Rost"

> Briefing für die Erzeugung fotorealistischer Design-Assets in einer
> Bild-KI (Claude-Bildfunktion, Midjourney, Firefly, DALL·E …).
> Ziel: echte, natürliche Materialien statt CSS-Imitat — Knochen,
> Geflecht, Rost, Kalk, Pigment. Richtung v2 nach Feedback: **heller
> Naturgrund**, kein dunkler einfarbiger Hintergrund.

## 0. Die eine Regel für ALLE Bilder

Damit die Assets zusammen wie EINE Fotostrecke wirken, gilt für jeden
Prompt derselbe Schluss-Baustein (anhängen, nie weglassen):

```
flat lay, photographed directly from above, soft diffuse natural daylight
from the upper left, warm neutral tones, extremely high detail macro
photography, no text, no watermark, no hands, no props other than described
```

- **Eine Lichtrichtung für alles**: weiches Tageslicht von links oben.
- **Eine Kamera für alles**: senkrecht von oben (flat lay).
- **Keine Menschen, kein Text** im Bild.
- Wenn das Tool Referenzbilder/Seeds unterstützt: das erste gelungene
  Bild als Stil-Referenz für alle weiteren verwenden.

## 1. Der Grund (Seitenhintergrund) — 2 Varianten generieren

**A · Gekalkte Wand / Kalkputz** (Favorit: hell, lebendig, nicht einfarbig)
```
seamless tileable texture of an old lime-washed plaster wall, warm
ivory-white with subtle natural irregularities, fine hairline cracks,
faint traces of earlier ochre pigment shimmering through, matte mineral
surface
```

**B · Geschliffene Knochenplatte / Bein**
```
seamless tileable texture of polished ancient bone surface, warm
ivory-cream color, fine organic grain and pores, subtle age patina,
matte sheen
```

- Format: JPG/WebP, **quadratisch 2048×2048**, muss **kachelbar
  (seamless)** sein — im Prompt steht es, trotzdem prüfen: Bild in einem
  Editor nebeneinanderlegen, Kanten dürfen nicht sichtbar sein.
- Hell! Der Grund trägt dunkle Tusche/Kohle-Schrift, nicht umgekehrt.

## 2. Die vier Wurfstäbe (das Herzstück des Rituals)

```
four ancient Egyptian senet throwing sticks carved from bone and dark
wood, each stick flat on one side (pale bone) and rounded on the other
(dark stained wood), slightly different lengths, weathered and polished
from decades of use, arranged loosely parallel with small gaps,
isolated on plain white background for cutout
```

- **Freisteller**: PNG mit transparentem Hintergrund (oder weißer Grund,
  ich stelle frei). Zusätzlich eine zweite Version „in der Luft /
  fallend" für die Wurf-Animation:
```
the same four bone and wood throwing sticks tumbling mid-air, frozen
motion, slight rotation each, isolated on plain white background
```

## 3. Die fünf Steine (Spielsteine = echte Pigmentsteine)

Ein Prompt, fünfmal mit anderem Pigment (Ocker/Fokus, Graphit/Werk,
Rost/Liebe, Moos/Kraft, Umbra/Geist):

```
a single small smooth river pebble, hand-painted with natural {ochre
yellow / graphite grey-blue / rust red-brown / moss green / muted violet
umber} mineral pigment, pigment slightly worn at the edges revealing pale
stone beneath, a tiny archaic symbol scratched into the pigment,
isolated on plain white background for cutout
```

- 5 × PNG-Freisteller, je ~800×800. Die geritzten Symbole ersetze ich
  digital durch unsere Glyphen (☉ ⚒ ♥ ⚡ ☽) — im Bild reicht „irgendein
  geritztes Zeichen".

## 4. Geflecht (Kartenrahmen & Trennelemente)

```
seamless tileable texture strip of fine hand-woven willow wicker,
natural pale reed color with darker binding threads, tight archaic
weaving pattern, slightly irregular handmade quality
```

- 1 × Kachel 2048×512 (Streifen). Wird zur Randleiste der Karten und
  zum Trenner zwischen Abschnitten.

## 5. Rost (der warme Metall-Akzent)

```
seamless tileable texture of heavily rusted iron sheet, deep red-brown
and burnt orange oxidation, flaking layered patina, matte
```

- 1 × 1024×1024. Einsatz sparsam: Button-Füllung im Hover, die
  Ereignis-Banner (Sternschnuppe/Rückenwind), kleine Akzentflächen.

## 6. Knochen-Objekte (Schmuckstücke, sparsam)

**Orakelknochen** (Bezug zu Zhouyi/Orakelknochenschrift):
```
a single ancient oracle bone fragment, flat piece of ox scapula with
fine archaic characters scratched and burnt into its surface, ivory
aged color with hairline cracks, isolated on plain white background
```

**Kleiner Astragal / Würfelknochen** (historischer Spielwürfel):
```
a single small polished astragalus knuckle bone, used for millennia as
a gaming die, warm ivory with age patina, isolated on plain white
background
```

- Je 1 × PNG-Freisteller. Einsatz: Zierelemente im Kopf/Fuß, Album.

## 7. Mondphasen (8 Stück, als Kohle-/Pigmentzeichnung)

```
hand-drawn moon phase symbol, {new moon / waxing crescent / first
quarter / waxing gibbous / full moon / waning gibbous / last quarter /
waning crescent}, drawn with charcoal and white chalk on parchment,
archaic astronomical manuscript style, single symbol centered,
isolated on plain white background
```

- 8 × PNG ~400×400. Ersetzen die Emoji-Monde 🌑–🌘.

## 8. Optional (spätere Runden)

- **30 Feldkarten-Vignetten** fürs Album (je Haus ein kleines
  Kohle-Piktogramm auf Kalk) — eigenes Briefing, wenn Runde 1 steht.
- **OG-/Share-Bild**: das Brett als Stillleben (Stäbe, Steine, Knochen
  auf Kalkgrund arrangiert) im Querformat 1200×630.

## Ablage & Integration

1. Dateien sammeln als: `grund-kalk.jpg`, `grund-knochen.jpg`,
   `staebe-liegend.png`, `staebe-fallend.png`, `stein-ocker.png` …,
   `geflecht.jpg`, `rost.jpg`, `orakelknochen.png`, `astragal.png`,
   `mond-1.png` … `mond-8.png`.
2. Ins Repo unter `public/assets/material/` legen (oder mir schicken —
   ich lege sie ab, optimiere Größe/Format zu WebP und baue sie ins
   Theme ein).
3. Ich setze darauf das Theme „Naturgrund" um: heller Kalk/Knochen-Grund
   mit echter Textur, Tusche-/Kohle-Typografie, Geflecht-Ränder,
   Rost-Akzente, Pigmentstein-Freisteller auf dem Brett — testbar unter
   `?theme=natur`, bevor es Standard der Mondlese wird.

## Qualitätscheck je Bild (kurz)

- [ ] Licht von links oben? Senkrecht von oben fotografiert?
- [ ] Keine Schrift/Wasserzeichen/Hände im Bild?
- [ ] Kacheln wirklich nahtlos (bei Texturen)?
- [ ] Farbtemperatur warm-neutral, passt neben die anderen Bilder?
- [ ] Freisteller: Kanten sauber, kein harter Schlagschatten?
