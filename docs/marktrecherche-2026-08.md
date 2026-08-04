# Marktrecherche: Kalendergebundenes Orakel-Brettspiel (August 2026)

> Recherchiert im August 2026 (web-basiert, mit Quellen). Grundlage für das
> Spielkonzept in `spielkonzept.md`. Zahlen mit Einzelquelle sind markiert.

## 1. Konkurrenz: Senet / Ancient Games

Es existieren mehrere Senet-Apps — alle reine Brettspiel-Nachbauten:
"Senet – An Ancient Egyptian Game" (App Store / Google Play), "Egyptian
Senet" (preisgekrönt 2012–2014, seither wenig Aktivität), eine
Steam-Version, dazu eine "Ancient Games"-Sammlung (Senet, Ur, XII Scripta,
Puluc). Royal Game of Ur: Kleinst-Apps (Beispiel: ~1.600 Downloads, 3,86★).
Patolli: einzelne Hobby-Apps. **Für Liubo existiert keine Mobile-App.**
Monetarisierung durchweg Einmalkauf/Werbung, nirgends Abo, nirgends
nennenswerte Downloadzahlen.

Die divinatorische Dimension von Senet (30 Felder als Lebensweg,
Orakelnutzung) ist historisch dokumentiert (BoardGameGeek-Analyse der
Feldbedeutungen; Sacred Scarab Institute), aber **keine gefundene App
setzt die Kalender-/Orakel-Verknüpfung um** — nur ein Tarot-Deck "Ancient
Egyptian Senet" existiert.

**Einschätzung:** Die Nische ist faktisch unbesetzt — echter White Space.
Zugleich zeigt die Winzigkeit aller Ancient-Games-Apps: "Senet" allein
zieht keine Nachfrage. Die Zielgruppe muss aus dem Astrologie-/Ritual-Markt
kommen; Senet ist Mechanik-Lieferant, nicht Positionierung.

## 2. Co-Star & Astrologie-App-Mechaniken

Belastbare Zahlen (Sensor-Tower-Schätzungen, 2025/26):

| App | Downloads/Monat | Umsatz/Monat | Bemerkung |
|---|---|---|---|
| Co-Star | ~100k | ~$400k | meistgeladene US-Astro-App; virale, absichtlich schroffe Push-Notifications |
| Nebula | ~90k | ~$300k | $7,99/Woche bzw. $49,99/Jahr; "Wallet-Draining"-Beschwerden |
| The Pattern | ~30k | ~$300k | sehr hohe Monetarisierung pro Nutzer |
| CHANI | ~2 Mio. gesamt | ~$14 Mio./Jahr *(Einzelquelle: Inc.)* | $11,99–14,99/Monat; Loop über Wochenhoroskope + Newsletter |

Sanctuary: kostenlose Tageshoroskope + Live-Reader-Chats ab ~$10.
Marktgrößen-Claims ($3,9–4,75 Mrd., zweistelliges Wachstum) stammen aus
Market-Research-PR und streuen extrem ($2–25 Mrd.) — Richtung ja,
Planungsgrundlage nein. "30 Mio. Co-Star-Nutzer" ist unverifizierter
PR-Claim.

Conversion-Benchmarks (RevenueCat, 115k Apps): Trial-to-Paid median
~10,7% bei Hard Paywall vs. 2,1% Freemium; Hard Paywall liefert ~8×
Revenue/Install ($3,09 vs. $0,38 an Tag 60). Kategorie Social/Lifestyle
hat unterdurchschnittliche Abo-Retention.

Der funktionierende Loop ist überall identisch: **1 tägliche, teilbare,
persönlichkeitsbezogene Push + sozialer Vergleich + Abo für Tiefe.**
Hauptkritik an Co-Star: "Loop statt Journey" — nach Wochen alles gesehen.

**Ein deutschsprachiges Co-Star-Pendant existiert nicht** (DE-Apps:
altmodisch oder Profi-Tools: AstroWorx, AstroStar u. ä.).

## 3. Web-Push & PWA

- Web-Push-Opt-in langfristig ~5–8% der Besucher (bis 10–15% bei sehr
  gutem Prompt-Timing). Native Apps: ~56% (iOS) / ~67% (Android) Opt-in.
  CTR ~2–3%.
- iOS-PWA-Push (seit 16.4) nur nach Add-to-Homescreen **plus** Opt-in;
  Berichte über instabile Subscriptions bis iOS 18. Zustellrate nativ
  95%+ vs. grob ~33% Web-Push *(Einzelquelle: MobiLoud)*.
- **Kein prominentes Erfolgsbeispiel einer push-zentrierten Consumer-PWA
  auf iOS auffindbar** — das Fehlen ist selbst ein Datenpunkt.
- Doppel-Filter (Homescreen-Install → Push-Opt-in) drückt die erreichbare
  tägliche Push-Reichweite einer reinen iOS-PWA realistisch unter 5% der
  Besucher.

**Konsequenz:** Ein Produkt, dessen Kernmechanik die tägliche Push ist,
darf auf iOS nicht PWA-only sein. Wordle zeigt den Ausweg: tägliche
Rituale funktionieren ohne Push, wenn der soziale Loop stark genug ist.

## 4. Habit-/Daily-Game-Mechaniken

- **Wordle:** ~10–14 Mio. tägliche Spieler; 5,3 Mrd. Plays 2024; ein
  einziges schweres Rätsel beendete 5,6 Mio. aktive Streaks an einem Tag.
  Erfolgsfaktoren: künstliche Verknappung (1 Rätsel/Tag), **dasselbe
  Rätsel für alle** (Gesprächsstoff), spoilerfreies Share-Format.
- **Duolingo:** 52,7 Mio. DAU (Ende 2025); >50% der täglichen Lerner mit
  ≥7-Tage-Streak; Streak-Freeze als "Versicherung" senkt Churn messbar
  ("47%→28%" ist Einzelquellen-Claim).
- **Abgenutzt/riskant:** dokumentierte "Streak Anxiety" — Nutzung wird
  Pflicht, Streak-Bruch führt zu Komplett-Abbruch; Guilt-Notifications
  (Duo-Owl, Snapstreaks) zunehmend als manipulativ kritisiert
  (arXiv-Studie zu Gamification-Missbrauch).
- **Gegenmodell Finch:** schamfreie Progression ohne Bestrafung — sehr
  beliebt in Self-Care; passt zur spirituellen Zielgruppe.

## 5. Naming / Domain

Besetzt: Co-Star, The Pattern, Sanctuary, Nebula, CHANI, Moonly,
Stellium, **Labyrinthos/Golden Thread** (dort existiert bereits ein
Daily-Tarot-Journaling-Loop — nächster echter Wettbewerber). TLDs 2026:
`.com` Vertrauens-Goldstandard; `.app` mobil glaubwürdig
(HTTPS-erzwungen); `.io` etabliert; `.one` Nische, als Bestandsmarke
nutzbar; `.game` im Gaming üblich.

Kriterien: ≤3 Silben, DE+EN aussprechbar, evoziert Ritual/Zyklus/Weg,
"verb-fähig" ("Hast du heute … gezogen?"). Namensrichtungen (ohne
Verfügbarkeitsprüfung): Senet Daily · Thirty/Pfad-Metaphern ·
Orakl/Oraklo · Lunum/Mondlauf · OneMove/Tageszug · **Aaru/Sechet**
(Binsengefilde = Ziel des Senet-Bretts; poetisch, unverbraucht) ·
Kismet Daily · Übergangsweise `play.horoskop.one`.

## Empfehlung

**Go-Signale:** (1) Kalender-Orakel-Senet nachweislich unbesetzt;
(2) Astrologie-Apps monetarisieren real ($300–400k/Monat je Top-App);
(3) Wordle/Duolingo belegen Retention durch Ein-Zug-pro-Tag-Verknappung;
(4) kein deutschsprachiges Co-Star-Pendant.

**Warnsignale:** Ancient-Games-Apps sind kommerziell tot (Senet nur als
Verpackung nutzen); Social/Lifestyle hat schwächste Abo-Retention;
tägliche Push kollidiert frontal mit iOS-PWA-Realität.
**Abbruchkriterium für den Markttest:** <5% Homescreen-Installs oder
<15% D7-Retention → Konzept überarbeiten statt skalieren.

**Plattformstrategie: hybrid, zweistufig.** Stufe 1: PWA-first für den
DE-Test (Bestands-Traffic, keine Store-Hürde, virale Links; Web-Push für
Android, **E-Mail als zweiter Ritualkanal**). Stufe 2: bei validierter
Retention native Wrapper (Capacitor o. ä.) für iOS+Android (Push-Opt-in
56–67%, Store-Auffindbarkeit, bessere Abo-Infrastruktur).

**Drei Design-Implikationen:**
1. Der Tageszug muss ohne Push funktionieren (Wordle-Prinzip: gleiche
   Tageslage für alle + persönlicher Zug + spoilerfreies Share-Snippet).
2. Sanfte Zyklus- statt harter Streak-Mechanik (Monatsbrett = Neustart;
   Forgiveness statt Guilt — Finch-Modell).
3. Journey statt Loop: fortlaufende, personalisierte Monatsgeschichte;
   narrative Tiefe + Monatsrückblick = das Abo-Produkt.
