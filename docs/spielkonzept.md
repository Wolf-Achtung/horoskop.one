# Spielkonzept: Das Monatsbrett (Arbeitstitel)

> Entwurf v1 — zur Diskussion, bevor Code entsteht. Basiert auf
> `marktrecherche-2026-08.md` und der vorhandenen Symbol-Engine in
> `main.py` (I-Ging, Tarot, Numerologie, Mondphasen, Ephemeriden).
> Entscheidung: Das Brett wird die neue Startseite; die Readings werden
> Teil des Spiels.

## Elevator Pitch

Ein Senet-Brett mit 30 Feldern ist dein Monat. Jeden Tag wirft das
Orakel für dich — du entscheidest, welchen Lebensbereich du ziehst.
Aus Zug, Tagesfeld und deinem Geburtsprofil entsteht eine kurze,
persönliche Erzählung. Am Ende des Mondmonats haben deine Steine eine
Geschichte geschrieben — und ein neues Brett beginnt.

**Formel:** Wordle-Verknappung × Senet-Symbolik × Co-Star-Personalisierung
— aber als Journey statt Loop, und sanft statt streak-getrieben.

## 1. Der Zyklus: Mondmonat statt Kalendermonat

Das Brett läuft von **Neumond zu Neumond** (29–30 Tage). Gründe:

- **Alle spielen synchron dasselbe Brett** — der Neumond ist ein
  globales, natürliches Startereignis (Wordle-Effekt: gemeinsamer
  Gesprächsgegenstand, "Brett 2026-09" ist für alle dasselbe).
- Die Mondphase ist bereits in der Engine (`moon_phase_fraction`) und
  gibt dem Brett einen eingebauten Spannungsbogen: zunehmend = Aufbau
  (Felder 1–14), **Vollmond ≈ Feld 15 = Senets "Haus der Wiedergeburt"**
  (die Deckung ist historisch belegbar elegant), abnehmend = Ernte &
  Loslassen (16–30).
- Monatsende = automatischer Neustart → keine Endlos-Streak, kein
  Schuldgefühl beim Wiedereinstieg (Finch-Prinzip aus der Recherche).

## 2. Die Steine: 5 Lebensbereiche

Jede Spielerin führt **5 Steine**, die den Lebensbereichen der
bestehenden Readings entsprechen (nahtlose Integration der heutigen
Sektionen):

| Stein | Bereich | heutige Reading-Sektion |
|---|---|---|
| ☉ | Fokus | Fokus |
| ⚒ | Werk (Beruf) | Beruf |
| ♥ | Liebe | Liebe |
| ⚡ | Kraft (Energie) | Energie |
| ☽ | Geist (Intuition) | neu — speist sich aus I-Ging/Tarot |

Ziel wie im historischen Senet: Steine über Feld 30 hinaus **„ins
Binsengefilde" (Aaru) auszuspielen**. Welche Bereiche „ankommen" und
welche zurückbleiben, ist der Stoff des Monatsrückblicks.

## 3. Der Tagesloop (2–3 Minuten)

**Schritt 1 — Die Tageslage (global, für alle gleich).**
Jeder Tag hat ein „Himmelsfeld": abgeleitet aus Mondphase +
Tages-Hexagramm (I-Ging, vorhanden) + Ganzhi-Tageszeichen (60er-Zyklus,
neu, ~15 Zeilen — die Liubo-Referenz). Beispiel: *„Tag 17 · abnehmender
Mond · Hexagramm 48 Der Brunnen · Wasser-Hahn."* Für alle Spieler
identisch → teilbar, besprechbar, presse-/social-tauglich.

**Schritt 2 — Der Wurf (persönlich, deterministisch).**
Das Orakel wirft die vier Senet-Wurfstäbe für dich: Wurfweite 1–5,
deterministisch aus Geburtsprofil + Datum (`_det_hash`-Muster, wie beim
Tarot-Zug). Kein Zufallsknopf — das Orakel „hat schon geworfen", man
kommt, um nachzusehen. Reproduzierbar und cache-freundlich.

**Schritt 3 — Der Zug (die einzige Entscheidung).**
Du wählst, **welcher Stein** die Wurfweite zieht. Das ist die
Kern-Agency: „Welchen Lebensbereich bewege ich heute?" Regelrahmen
(bewusst minimal für v1):

- Ein Zug pro Tag. Der Zug ist endgültig.
- Steht auf dem Zielfeld bereits ein eigener Stein, ist der Zug für
  diesen Stein nicht erlaubt (wie Senet).
- Senets Sonderfelder gelten (siehe unten).

**Schritt 4 — Die Mikro-Lesung.**
Aus (gewählter Bereich × Zielfeld × Tageslage × Geburtsprofil) erzeugt
die vorhandene LLM-Pipeline 2–4 Sätze plus einen konkreten Tagesimpuls —
in der gewohnten Ton-Auswahl (mystisch/Coach/skeptisch). Das klassische
Deep-Reading bleibt als „große Lesung" erreichbar und wird an
Schlüsselfelder gebunden (siehe Monetarisierung).

**Schritt 5 — Das Share-Snippet (spoilerfrei).**
Wie Wordles Emoji-Raster: Brettstand als Glyphenzeile + Tagesfeld-Symbol,
ohne persönlichen Text. Beispiel:
`Brett 2026-09 · Tag 17 🌗 ䷯ — ☉▓▓▓░ ♥▓▓░░ ⚒▓▓▓▓` — neugierig machend,
nichts Intimes preisgebend. Das ist der organische Akquise-Kanal, der
ohne Push funktioniert.

## 4. Senet-Sonderfelder (sanft interpretiert)

| Feld | Senet-Name | Spielwirkung | Deutungsanker |
|---|---|---|---|
| 15 | Haus der Wiedergeburt | sicherer Hafen; Rückkehrpunkt | Vollmond, Neuausrichtung |
| 26 | Schönes Haus | Bonus-Mikrolesung („Segen") | Ernte, Dankbarkeit |
| 27 | Haus des Wassers | Stein kehrt zu Feld 15 zurück — **erzählt als Erneuerung, nie als Strafe** | Loslassen, Umweg |
| 28 | Haus der drei Wahrheiten | Auszug nur bei Wurf 3 | Wahrhaftigkeit |
| 29 | Haus des Re-Atum | Auszug nur bei Wurf 2 | Schwelle |
| 30 | Horizont | Auszug bei jedem Wurf | Ankunft |

## 5. Ruhetage statt Streaks (die wichtigste Designregel)

- **Kein Streak-Zähler, kein Verlust, keine Schuld-Notification.**
- Verpasste Tage: bis zu 2 Züge bleiben „nachholbar" (das Orakel hat ja
  geworfen). Ab dem 3. Tag zieht das Orakel selbst — die Geschichte geht
  weiter, das Brett veraltet nie.
- **Die Belohnung fürs tägliche Kommen ist Kontrolle:** Wer da ist,
  wählt den Stein selbst; wer fehlt, dessen Geschichte schreibt das
  Schicksal. Das ist thematisch stimmig (Orakel!) und ersetzt
  FOMO-Bestrafung durch Agency-Anreiz.
- Monatswechsel = Generalamnestie. Jedes Brett beginnt bei null.

## 6. Journey statt Loop: die Monatsgeschichte

Jede Mikro-Lesung wird als Kapitel gespeichert. Daraus entsteht:

- **Wochenbild** (frei): 1 Absatz, was sich abzeichnet.
- **Monatsrückblick** (Premium): die erzählte Geschichte des Bretts —
  welche Steine kamen ins Binsengefilde, welche blieben im Wasser, was
  bedeutet das fürs nächste Brett. Das adressiert die Co-Star-Kritik
  „Loop statt Journey" frontal und ist das natürliche Abo-Produkt.

## 7. Monetarisierung (Skizze, nicht Teil von Phase 1)

- **Frei:** Tageszug, Tageslage, Kurzimpuls, Share-Snippet, Wochenbild.
- **Premium (Abo):** volle Mikro-Lesungen in allen Tonlagen,
  Monatsrückblick/-geschichte, Deep-Readings an Sonderfeldern,
  Geburtszeit-genaue Deutung (Aszendent/Häuser — Engine vorhanden).
- Paywall-Test früh (Hard vs. Soft; RevenueCat-Spread 10,7% vs. 2,1%).

## 8. Später (bewusst NICHT in v1)

- **Der unsichtbare Gegner:** die „Ba"-Seele — ein deterministischer
  Schattenspieler aus demselben Geburtsprofil (historisch belegtes
  Senet-Motiv: Spiel gegen die eigene Seele). Erst wenn der Solo-Loop
  trägt.
- Gemeinsame Bretter (Familie/Freunde), Vergleichsansichten.
- Native Wrapper (Capacitor) für App Store / Play Store — nach
  validierter Retention (Messlatte: ≥5% Homescreen-Installs, ≥15%
  D7-Retention im PWA-Test).

## Offene Entscheidungen

1. **Domain fürs Go-Live:** Brett als neue Startseite von
   `www.horoskop.one` (Entscheidung steht) — aber Beta-Phase unter
   eigenem Pfad/Subdomain (`/brett` bzw. `play.`) bis zur Reife?
   *Empfehlung: hinter `/brett` bauen, Umschalten der Startseite ist
   dann ein Einzeiler.*
2. **Neue Marke/Domain:** Kandidatenrichtungen aus der Recherche
   (Aaru/Sechet, Lunum, Thirty …) — Entscheidung kann bis nach dem
   DE-Markttest warten.
3. **Onboarding-Minimum:** nur Geburtsdatum+Ort (wie heute) oder
   zusätzlich optionale Geburtszeit im Spiel-Onboarding?
