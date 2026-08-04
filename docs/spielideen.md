# Spielideen: Vom Klick zum Erlebnis

> Ideenkatalog v1 (August 2026) — Antwort auf das Playtest-Feedback „bislang
> ist es eigentlich nur ein Klick". Priorisiert nach Wirkung auf den
> Kern-Loop, Aufwand und technischen Voraussetzungen. Grundlage:
> `spielkonzept.md` + `marktrecherche-2026-08.md`.

## Das Diagnose-Raster

Ein guter Tagesloop braucht vier Zutaten — aktuell haben wir nur die dritte:

1. **Spannung VOR dem Zug** (etwas erwarten, etwas riskieren) → fehlt
2. **Überraschung IM Zug** (variabler Ausgang, seltene Momente) → fehlt
3. **Bedeutung NACH dem Zug** (die Deutung) → vorhanden ✓
4. **Bindung ÜBER Tage** (etwas wächst, jemand geht mit) → schwach

Die Ideen unten sind danach sortiert, welche Lücke sie schließen.

---

## Stufe 1 — Quick Wins (kein Account, keine DB, LocalStorage reicht)

### 1. Die Orakelfrage („Gespür") — Spannung vor dem Wurf ⭐ ✓ umgesetzt 08/2026
Bevor die Wurfstäbe fliegen, tippt man eine Vorahnung: **„Fällt der Wurf
kurz (1–2) oder weit (3–5)?"** Nach der Animation: „Dein Gespür lag
richtig!" — ein rein kosmetischer **Gespür-Wert** (z. B. „7 von 12 Tagen
gespürt") wächst mit, ohne Streak-Druck (Monatsreset). Verwandelt den
einen Klick in *Einsatz → Enthüllung → Belohnung* — die klassische
Spannungskurve, die Wordle trägt. Deterministisch, 0 LLM-Kosten.
**Aufwand: klein (nur Frontend + LocalStorage).**

### 2. Promi-Sternzwillinge — deine Idee, und sie ist gut ⭐ ✓ umgesetzt 08/2026
> Kuratierte Tabelle: `public/assets/sternzwillinge.json` (936 Einträge,
> alle 366 Kalendertage, per Web-Recherche belegt).
Beim Onboarding und im Profil: **„Dein Sternzwilling: [Promi] hat am
selben Tag Geburtstag"** (kuratierte statische Tabelle, ~2–3 pro
Kalendertag, DACH-relevant gemischt mit international). Täglicher
Flavor: „Heute steht auch [Zwilling]s Stein auf dem Sieb-Feld." 
**Wichtig (Persönlichkeitsrecht):** nur belegbare Fakten (Geburtstag)
plus geteilte *Tageslage* — nie erfundene Aussagen über die reale Person
(„X wird heute…" ist tabu; „X hat dieselbe Tageslage wie du" ist okay).
Bonus-Variante „Jahrgangszwilling" (Tag+Jahr) für den Wow-Effekt, wo die
Tabelle es hergibt. Teilbar („Ich bin Sternzwilling von …!").
**Aufwand: klein–mittel (Datentabelle kuratieren + Anzeige).**

### 3. Ereignisfelder & seltene Momente — Überraschung im Zug ✓ umgesetzt 08/2026
> v1 mit zwei Ereignissen: ✨ Sternschnuppe (Doppelwurf mit Wahl) und
> 🌬 Rückenwind (+1 Feld); deterministisch ~2 Tage/Monat pro Person.
Nicht jeder Tag ist gleich: deterministisch (aus Datum + Profil) fallen
selten **besondere Momente** — „✨ Sternschnuppe: Das Orakel wirft heute
zweimal, wähle den Wurf", „🌬 Rückenwind: dein Stein zieht ein Feld
weiter", „🪞 Spiegeltag: wähle zwei Steine". Selten genug (1–2×/Monat),
dass sie sich wie Geschenke anfühlen; deterministisch, also fair und
cache-freundlich. Variable Belohnung ohne Glücksspiel-Mechanik.
**Aufwand: mittel (Regeln + Backend + UI).**

### 4. Das Feld-Album — Sammeln über Monate ✓ umgesetzt 08/2026
Jedes Feld, das ein eigener Stein je betreten hat, schaltet seine
**Feldkarte** frei (Name, Deutung, Symbol — später Midjourney-Artwork).
Ein Album „17 von 30 Häusern entdeckt" überdauert die Monatsbretter und
gibt Langzeitbindung ohne Streaks. Seltene Karten: die Auszugshäuser
28–30 und das Wasser. Vorstufe für spätere Premium-Artworks.
**Aufwand: klein (LocalStorage-Set + Albumseite), Artwork später.**

### 5. Partner-Resonanz — dein „Partner-Check" ✓ umgesetzt 08/2026
Zweites Geburtsdatum eingeben → **Resonanz-Lesung**: Sonnenzeichen-Paar,
Lebenszahlen-Verhältnis, chinesische Zeichen-Harmonie, gemeinsamer
LLM-Text („Löwe trifft Waage, 11 trifft 4 …"). Als eigene Karte im Spiel
(„Resonanz des Tages: Wie läuft euer gemeinsamer Tag?"). Klassiker der
Astro-Unterhaltung, hohe Teilbarkeit, rein deterministische Inputs.
**Aufwand: mittel (Formular + Prompt-Typ; keine DB nötig).**

---

## Stufe 2 — Braucht Infrastruktur (Postgres/Zähler, Phase 2+)

### 6. „Heute haben 68 % die Liebe gezogen" — die Gemeinschaft sichtbar machen
Anonyme Tageszähler (welcher Stein wurde weltweit gewählt, Verteilung
der Würfe) → nach dem eigenen Zug: „Du bist mit 23 % der Spielenden im
Geist gezogen — ein seltener Tag." Wordles Kernmagie: *alle spielen
dasselbe Rätsel*. Minimal: zwei Redis-/Postgres-Zähler pro Tag.

### 7. Tages-Duell per Link
Nach dem Zug: „Fordere jemanden heraus" → Link enthält deinen
(signierten) Tageszug; wer ihn öffnet, spielt seinen eigenen Zug und
sieht den Vergleich („Dein Werk auf Feld 12, ihr Fokus auf Feld 15 —
das Orakel sagt zu eurem Tag: …"). Viraler Loop ohne Accounts.

### 8. Der Ba-Gegner (aus dem Spielkonzept, Phase 4)
Die eigene „Seele" als deterministischer Schattenspieler auf demselben
Brett — täglicher Stand („Dein Ba liegt 3 Felder voraus — er hat die
Liebe vorgezogen, du das Werk"). Historisch belegtes Senet-Motiv, gibt
dem Solo-Spiel einen stillen Rivalen.

### 9. Vollmond- & Neumond-Events
Feste Gemeinschaftsmomente: Am Vollmond (Feld 15) gibt es für alle die
„Große Lesung", am Neumond die erzählte **Monatsgeschichte** (Premium,
siehe Spielkonzept §6) plus Album-Bilanz. Events = Kalender-Marketing.

### 10. Frage ans Orakel
1×/Tag optional eine eigene kurze Frage stellen, die das Orakel in die
Zugdeutung einwebt. Höchste persönliche Bindung; LLM-Kosten pro Nutzung
→ natürlicher Premium-Kandidat.

---

## Empfohlene Reihenfolge

| # | Idee | Schließt Lücke | Aufwand | Voraussetzung |
|---|---|---|---|---|
| 1 | Orakelfrage/Gespür | Spannung vorher | S | keine |
| 2 | Promi-Sternzwillinge | Bindung/Teilen | S–M | Datentabelle |
| 3 | Feld-Album | Langzeitbindung | S | keine |
| 4 | Ereignisfelder | Überraschung | M | keine |
| 5 | Partner-Resonanz | Teilen/Neue Nutzer | M | keine |
| 6 | Gemeinschafts-Prozente | Wordle-Effekt | M | Phase 2 (DB) |
| 7 | Tages-Duell | Viralität | M | Phase 2 |
| 8 | Ba-Gegner | Rivalität | M–L | Loop validiert |
| 9 | Mond-Events | Ritual-Höhepunkte | M | Monatsrückblick |
| 10 | Frage ans Orakel | Tiefe/Premium | M | Premium-Modell |

**Vorschlag für „Spielspaß-Sprint 1":** Ideen 1 + 2 + 3 gemeinsam — sie
verwandeln den Tagesloop von *ein Klick* in *Vorahnung → Wurf-Ritual →
Zugwahl → Deutung → Albumfortschritt*, plus den Sternzwilling als
Gesprächsstoff. Alles ohne Account, ohne DB, ohne laufende Kosten.
