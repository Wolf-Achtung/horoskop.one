# Architektur Phase 1: Spielbarer PWA-Prototyp

> Ziel: das Spielkonzept (`spielkonzept.md`) erlebbar machen und die
> Kernfrage beantworten — *kommt man morgen wieder?* — mit minimalem
> Infrastruktur-Invest. Kein Account-System, keine Datenbank, kein Push
> in dieser Phase.

## Leitprinzip

Alles Orakelhafte ist **deterministisch und zustandslos** (Server),
alles Persönliche ist **lokal** (Browser). Dadurch bleibt der Server so
einfach wie heute; der einzige echte Zustand — welche Steine wo stehen —
liegt in Phase 1 im LocalStorage und wandert erst in Phase 2 nach
Postgres.

## Backend (main.py — Erweiterung, kein Umbau)

Neue Endpoints, gleiche Architektur (FastAPI, deterministisch, cachebar):

- `GET /board/today` — **global, für alle identisch**, aggressiv
  cachebar (ein Eintrag pro Tag): Brett-ID (Neumond-Zyklus, z. B.
  `2026-09`), Tag-im-Brett (1–30), Mondphase, Tages-Hexagramm,
  Ganzhi-Tageszeichen, Feldereignis des Tages.
- `POST /board/throw` — persönlicher Wurf: Geburtsdaten → Wurfweite 1–5
  (deterministisch via `_det_hash(bdate, board_id, day)`), plus die für
  jeden der 5 Steine legalen Züge (Server validiert die Senet-Regeln,
  damit der Client nicht schummeln kann; der Client schickt dazu seine
  aktuellen Steinpositionen mit).
- `POST /board/move` — gewählter Stein + Positionen → validierter neuer
  Brettstand + **Mikro-Lesung** (bestehende LLM-Pipeline mit neuem,
  kurzem Prompt-Typ `board_day`; Cache-Key wie bisher inputbasiert).

Neue reine Funktionen (Muster wie vorhanden, alle testbar):
`ganzhi_day(date)` (60er-Zyklus), `lunar_board(date)` → (board_id,
day_index) aus `moon_phase_fraction`, `FIELD_EVENTS[30]`-Tabelle,
`legal_moves(positions, throw)` (Senet-Regeln inkl. Sonderfelder).

## Frontend (neuer Einstieg, Mobile-First)

- Neue Route **`/brett`** (Beta). Die heutige Startseite bleibt
  unangetastet, bis das Brett reif ist — der Wechsel ist dann ein
  Umbenennen im `dist`-Layout.
- Brett als **SVG** (3×10 Boustrophedon-Pfad), ab 360 px Breite;
  Interaktion: Tap auf Stein → Vorschau des Zielfelds → Bestätigen.
  Kein Framework-Wechsel nötig: gleiche esbuild/TS-Toolchain, neues
  Entry `src/board.ts`.
- LocalStorage-Schema v1:
  `{boardId, positions{5}, history[], lastMoveDay, profile{birthDate,birthPlace,coords?}}`
  — Profil wird aus dem bestehenden Formular übernommen.
- Share-Snippet: Canvas/Clipboard-Text, kein Server nötig.

## PWA-Minimum (Phase 1)

- `manifest.webmanifest` (Name, Icons, `display: standalone`,
  Theme-Farben) + Service Worker nur fürs App-Shell-Caching (offline
  öffnen, gestern lesen). **Noch kein Push** — erst Phase 3, dann Web-Push
  (Android) + E-Mail-Kanal, gemäß Recherche.
- Add-to-Homescreen-Hinweis dezent nach dem 2. gespielten Tag (nicht
  beim Erstbesuch — Opt-in-Timing laut Benchmarks entscheidend).

## Rechtliches (Pflicht in Phase 1)

`datenschutz.html` ergänzen: LocalStorage-Nutzung (Spielstand lokal im
Browser, kein Server-Konto), sonst unverändert — der Server erhält
weiterhin nur die schon heute übermittelten Geburtsdaten pro Anfrage.

## Messung (bewusst minimal)

Kein Tracking-SDK. Zwei serverseitige Zähler genügen für die
Go/No-Go-Frage: eindeutige `board/move`-Aufrufe pro Tag (D1/D7-Retention
approximierbar über anonymisierte, gehashte Profil-IDs im Log) und
Anteil `standalone`-Display-Mode (Homescreen-Installs, vom Client als
Header mitgesendet). Abbruchkriterium aus der Recherche: <5%
Homescreen-Installs oder <15% D7 → Konzept überarbeiten.

## Phasen-Ausblick

| Phase | Inhalt | Voraussetzung |
|---|---|---|
| 2 | Postgres, anonyme Identität (Magic Link optional), Spielstand serverseitig | Prototyp trägt |
| 3 | Web-Push (VAPID) + E-Mail-Ritualkanal, volle PWA | Phase 2 |
| 4 | „Ba"-Gegner, gemeinsame Bretter | stabile Retention |
| 5 | Native Wrapper (Capacitor), Stores, Abo-Infrastruktur | validierter Markttest |
