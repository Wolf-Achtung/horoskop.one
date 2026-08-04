# Tonalität & Produktstimme: „Wie eine gute Freundin"

> Analyse und Umsetzung des Tonalitäts-Briefings (August 2026).
> Kernsatz: *„Wir wollen die Art und Weise reflektieren, wie wir Menschen
> im wirklichen Leben miteinander sprechen."* Referenzbeispiele:
> „Schütze heute deine Grenzen." · „Erwarte realistisch." ·
> „Lass dein Handy so lange wie möglich aus."

## 1. Analyse: Was das Briefing für uns bedeutet

Das Briefing beschreibt das Erfolgsrezept der Co-Star-Generation in fünf
Zutaten — so stehen wir dazu:

| Zutat | Bedeutung | Stand bei uns |
|---|---|---|
| **Stimme** — Rat wie von einer Freundin, echt, alltagsnah | Der wichtigste Faktor: Menschen bleiben wegen des Tons, nicht wegen der Methode | **War unsere größte Lücke → jetzt umgesetzt** (s. §2) |
| **Der eine konkrete Satz** — klein, machbar, heute | Die merkbare, teilbare Essenz jedes Tages | **Umgesetzt**: „Satz für heute" (s. §2) |
| **Hintergrund-Geschichten** — woher kommt das, wer nutzt es | Neugier befriedigen, Vertrauen aufbauen | ✓ vorhanden: „Was bedeutet das alles?"-Karte + Methoden-Lexikon |
| **Sich & andere verstehen** — Sternzeichen als „Stenografie" für Persönlichkeit, Kompatibilität | Der soziale Kern (Zielgruppe: Frauen in den 20ern, Großstadt) | ✓ v1 vorhanden: Partner-Resonanz, Sternzwillinge — ausbaubar (s. §3) |
| **Kollektiv & Ritual** — alle im selben Rhythmus, feste Tageszeit | Bindung ohne Druck | ✓ halbe Miete: synchrones Mondmonats-Brett; fehlend: Push/fester Zeitpunkt (s. §3) |

**Bewusste Abgrenzung zu Co-Star:** Deren Ton kippt oft ins Brutal-Kryptische
(„Erwarte nichts von niemandem") — polarisiert, macht aber auch Angst.
Unsere Stimme bleibt **warm und direkt zugleich**: die Klarheit der
Freundin, nicht die Kälte des Orakels.

**Entscheidung Du/Sie:** Die Beispielsätze im Briefing stehen in der
Sie-Form (Zeitungszitat) — für die Zielgruppe (20er/30er, mobil,
Harry-Potter-Generation) ist die **Du-Form** die richtige; die gesamte
Seite spricht bereits Du. Die Beispiele wurden entsprechend übertragen.

## 2. Umgesetzt (August 2026)

1. **Produktstimme im System-Prompt** (`_LLM_DEFAULT_SYSTEM`): Freundes-Ton,
   Du-Form, kurze Sätze, keine Astro-Floskeln — inklusive der drei
   Referenzbeispiele als Stil-Anker. Gilt für Brett-Deutungen,
   Partner-Resonanz, klassische Readings und `/compare`; die tiefen
   Readings bekommen dieselbe Stimm-Vorgabe in ihren System-Prompt.
   Die Ton-Regler (mystisch/coach/skeptisch) färben nur noch darüber.
2. **„Satz für heute"**: Jede Zugdeutung endet per Prompt mit einem
   kleinen, bis heute Abend machbaren Impuls. Das Frontend hebt diesen
   letzten Satz heraus — als goldene Impuls-Karte nach dem Zug
   („Dein Satz für heute"), als markierte Zeile in jedem Kapitel der
   Monatsgeschichte und im Share-Text („Brettstand teilen" trägt jetzt
   den Satz mit hinaus — Teilbarkeit!).
3. Die Resonanz-Lesung schließt analog mit „euer Satz für heute".

## 3. Vorschläge: Die nächsten Hebel (aus Briefing + Konkurrenzanalyse)

### 3.1 Das Morgen-Ritual (Lehre aus „Mein Horoskop Pro") — Priorität A
Eine tägliche Nachricht zur festen, selbst gewählten Uhrzeit ist der
stärkste Bindungsmechanismus der Konkurrenz. Weg für uns: **PWA**
(Manifest + Installierbarkeit, Phase 1b) → **Web-Push** (Phase 3).
Inhalt der Push ist ab jetzt klar: **der Satz für heute.** Bis Push da
ist: „Satz für heute" prominent halten und teilen lassen (erledigt).

### 3.2 Persönlichkeits-„Stenografie" ausbauen — Priorität A
Das Briefing betont: Sternzeichen sind Kurzschrift für „das bin ich".
Wir zeigen bisher nur die Tageslage. Vorschlag: ein kompaktes
**„Dein Profil"** auf der Spielseite — Sternzeichen, Lebenszahl,
chinesisches Jahreszeichen mit je einem Satz Charakter-Deutung (statisch,
0 Kosten) + Sternzwillinge. Das ist die Identitäts-Karte, über die man
spricht („typisch Löwe mit Lebenszahl 7").

### 3.3 Resonanz → Kompatibilitäts-Profil (Dating-Winkel) — Priorität B
Die Resonanz liest bisher nur den Tag. Ausbaustufe: ein dauerhafter
**Resonanz-Überblick** pro Paar (Sonnenzeichen-Dynamik, Zahlenverhältnis,
Zeichen-Harmonie als kurze statische Deutungen) + die LLM-Tageslesung
obendrauf. Mehrere Personen speicherbar („Deine Menschen") — das bedient
„verstehen, wie ich mit all diesen Menschen interagiere" ohne Dating-
Plattform-Anspruch und ohne Account (LocalStorage).

### 3.4 Wochen-/Monatsbogen (Lehre aus „iHoroskop") — Priorität B
Zusatzrhythmen zum Tageszug: die **Wochenlesung am Sonntag** (Rückblick
auf die gespielten Züge + Bogen für die Woche) und die **Monatsgeschichte
zum Neumond** (bereits im Spielkonzept §6 als Premium-Kandidat).

### 3.5 Was wir NICHT übernehmen
- **Uhrzeit-/Ortszwang wie Co-Star**: Unser „ohne Geburtszeit"-Prinzip
  bleibt — es ist ein bewusster Zugänglichkeits-Vorteil.
- **Täglicher Astro-Lehrstoff wie Time Nomad**: Tiefe liegt bei uns im
  Methoden-Lexikon und Feld-Album — Lernstoff darf gezogen werden,
  wird aber nie gepusht.
- **Co-Stars Härte**: s. o. — warm und direkt, nie kalt.

## 4. Empfohlene Reihenfolge

| # | Baustein | Wirkung | Aufwand | Voraussetzung |
|---|---|---|---|---|
| 1 | Stimme + Satz für heute | Ton = Produkt | S | ✓ erledigt |
| 2 | Profil-Karte („Stenografie") | Identität/Gespräch | S | keine |
| 3 | PWA-Manifest (installierbar) | Ritual-Grundstein | S–M | keine |
| 4 | Resonanz-Ausbau („Deine Menschen") | sozialer Kern | M | keine |
| 5 | Wochenlesung Sonntag | Rhythmus | M | keine |
| 6 | Web-Push „Satz für heute" | Ritual komplett | M–L | PWA + Phase 3 |
