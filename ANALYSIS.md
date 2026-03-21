# horoskop.one – Projektanalyse & Validierung

**Datum:** 2026-03-21
**Version:** 1.0.2 (horoskop.one-gold)

---

## 1. Projektübersicht

**horoskop.one** ist eine deutschsprachige Astrologie-/Horoskop-Webanwendung mit folgender Architektur:

```
Frontend (TypeScript + React CDN)
  │  POST /reading
  ▼
Main API (Python/FastAPI + OpenAI GPT)
  │  POST /swe (optional)
  ▼
SWE Worker (Python/FastAPI + pyswisseph)
```

### Technologie-Stack
| Schicht | Technologie |
|---------|------------|
| Frontend Build | esbuild (TypeScript → IIFE Bundle) |
| Frontend UI | Vanilla JS + React 18 (CDN) + Babel (CDN) |
| Backend API | Python 3.11/3.12, FastAPI, Uvicorn |
| AI-Engine | OpenAI GPT (gpt-4o-mini default) |
| Ephemeris | pyswisseph (Swiss Ephemeris) |
| Geocoding | OpenStreetMap Nominatim |
| Deployment | Railway.app + Docker |

### Dateien (ohne .git)
- **Backend:** `main.py`, `requirements.txt`, `Dockerfile`, `Procfile`
- **Frontend (src/):** `main.ts`, `readingApi.ts`, `sharecard.ts`, `zodiac.ts`, `geocode.ts`
- **Frontend (CDN):** `components/horoskop.cdn.jsx`, `components/enhancements-v14..v16.{js,css}`
- **Public:** `index.html`, `styles.css`, statische Seiten, SVG-Assets
- **SWE Worker:** `swe_worker/swe_worker.py` (separater Microservice)

---

## 2. Build-Validierung

### Frontend Build: OK
```
npm run build → dist/assets/main.js (8.3kb) ✓
```

### Python Syntax: OK
```
ast.parse(main.py) → Syntax OK ✓
```

### npm Audit: 1 moderate Vulnerability
- **esbuild <=0.24.2** – Dev-Server kann von externen Websites gelesen werden
  - Betrifft nur Entwicklung, nicht Produktion
  - Fix: `npm audit fix --force` (→ esbuild 0.27.x)

---

## 3. Kritische Bugs

### BUG-1: `parse_birth_time()` fehlt komplett (KRITISCH)
**Datei:** `main.py:217`
**Problem:** Die Funktion `parse_birth_time()` wird aufgerufen, existiert aber nicht.

```python
# Zeile 217 – Aufruf:
btime = parse_birth_time(req.birthTime)  # NameError!

# Zeilen 50-52 – Toter Code nach return None:
    return None
    h, mi = int(m.group(1)), int(m.group(2))          # Unerreichbar
    return dt.time(max(0, min(23, h)), max(0, min(59, mi)))  # Unerreichbar
```

**Auswirkung:** Jeder Aufruf von `POST /reading` schlägt mit `NameError: name 'parse_birth_time' is not defined` fehl, wenn `birthTime` übergeben wird.

**Fix-Vorschlag:**
```python
def parse_birth_time(time_str: str) -> Optional[dt.time]:
    s = (time_str or '').strip()
    m = re.match(r'^(\d{1,2}):(\d{2})$', s)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return dt.time(max(0, min(23, h)), max(0, min(59, mi)))
```

### BUG-2: Doppelte `__mountMixer`-Funktion (MITTEL)
**Datei:** `index.html:237-243`
**Problem:** `__mountMixer` ist doppelt verschachtelt definiert, was zu unerwartetem Verhalten führen kann:
```javascript
function __mountMixer(){ if(window.KosmischerMixer){ function __mountMixer(){
  // innere Definition überschattet äußere
```

### BUG-3: CSP blockiert CDN-Scripts (MITTEL)
**Datei:** `_headers:2` vs. `index.html:154-157`
**Problem:** Die Content-Security-Policy erlaubt nur `script-src 'self'`, aber `index.html` lädt React, ReactDOM und Babel von `unpkg.com`. Diese Scripts werden im Browser blockiert.

**Betroffene URLs:**
- `https://unpkg.com/react@18/umd/react.production.min.js`
- `https://unpkg.com/react-dom@18/umd/react-dom.production.min.js`
- `https://unpkg.com/@babel/standalone/babel.min.js`

**Fix:** Entweder CSP erweitern um `https://unpkg.com` oder Scripts lokal bundlen.

---

## 4. Sicherheitsanalyse

### Positiv
- CSP-Headers vorhanden (wenn auch inkonsistent mit dem Code)
- `X-Frame-Options: DENY` – Clickjacking-Schutz
- `X-Content-Type-Options: nosniff` – MIME-Sniffing-Schutz
- `Referrer-Policy: no-referrer` – Datenschutz
- CORS konfigurierbar über Env-Var `CORS_ALLOW_ORIGINS`
- Backend-Eingabevalidierung via Pydantic
- Keine sensiblen Daten im Frontend-Code

### Verbesserungsbedarf
| Thema | Status | Priorität |
|-------|--------|-----------|
| CSP vs. CDN-Scripts inkonsistent | Mismatch | HOCH |
| CORS default `*` (wenn keine Env-Var) | Offen | MITTEL |
| OpenAI API-Key nur in Env-Var | OK | – |
| Keine Rate-Limiting am Backend | Fehlt | MITTEL |
| Keine CSRF-Schutz (API-only, kein Session) | Akzeptabel | NIEDRIG |
| `bare except` in main.py (Zeile 121, 127) | Code-Smell | NIEDRIG |

---

## 5. Code-Qualität

### Duplikate
| Datei A | Datei B | Status |
|---------|---------|--------|
| `/horoskop.cdn.jsx` | `/components/horoskop.cdn.jsx` | Identisch – eine entfernen |
| `enhancements-v15.css` | `enhancements-v16.css` | Fast identisch |
| `enhancements-v14.js` | `enhancements-v15.js` | Überlappend |
| `/index.html` | `/public/index.html` | Verschiedene Versionen! |
| `/datenschutz.html` | `/public/datenschutz.html` | Verschiedene Versionen |
| `/impressum.html` | `/public/impressum.html` | Verschiedene Versionen |
| `/methoden.html` | `/public/methoden.html` | Verschiedene Versionen |

**Problem:** Root-HTML-Dateien und `public/`-HTML-Dateien sind unterschiedliche Versionen. `public/` wird vom Build-System genutzt, Root-Dateien sind vermutlich veraltet.

### Code-Smells
- **`main.py`:** Alles in einer Datei (339 Zeilen) – Astrologie-Logik, API, AI-Prompts
- **`bare except:`** an mehreren Stellen statt spezifischer Exceptions
- **Toter Code** nach `return None` (Zeile 51-52)
- **Inline-Styles** in `index.html` (> 400 Zeilen HTML + JS + CSS vermischt)
- **Keine Tests** vorhanden (weder Python noch JavaScript)

### Architektur-Stärken
- Klare Frontend-Modul-Trennung (src/): main, api, sharecard, geocode, zodiac
- Progressive Enhancement (v14 → v15 → v16) – guter Ansatz
- Saubere Pydantic-Modelle für Request/Response
- Swiss-Ephemeris als optionaler separater Worker
- Reproduzierbare Ergebnisse durch Seed-Mechanismus

---

## 6. Rechtliche Risiken (DSGVO/TMG)

### DRINGEND: Impressum unvollständig
**Datei:** `public/impressum.html`
Enthält nur Platzhalter: `[Dein Name/Firma] · [Adresse] · [Kontakt]`
**Pflicht nach § 5 TMG/DDG** für geschäftsmäßige Websites.

### DRINGEND: Datenschutzerklärung unzureichend
**Datei:** `public/datenschutz.html`
Fehlende Pflichtangaben:
- Verantwortlicher (Name, Adresse)
- Zweck und Rechtsgrundlage der Datenverarbeitung
- Weitergabe an Dritte (OpenAI API verarbeitet Geburtsdaten!)
- Nominatim/OpenStreetMap Nutzung (IP-Logging)
- Speicherdauer
- Betroffenenrechte (Auskunft, Löschung, etc.)
- Widerrufsrecht

---

## 7. Performance & UX

### Positiv
- Frontend-Bundle nur 8.3kb (minified)
- Starfield-Canvas mit requestAnimationFrame
- Debouncing bei Autocomplete (400ms)
- Rate-Limiting für Nominatim (1 req/s)

### Verbesserungsbedarf
- Babel wird im Browser kompiliert (CDN) – langsam, sollte prebuild sein
- 4 Google-Font-Requests beim Laden
- MutationObserver auf `documentElement` mit `subtree: true` (Performance)
- Kein Service Worker / Offline-Support
- Keine Ladezeit-Optimierung (keine lazy loading)

---

## 8. Zusammenfassung

### Status-Ampel

| Bereich | Status |
|---------|--------|
| Build | OK |
| Laufzeitfehler | KRITISCH (parse_birth_time fehlt) |
| Sicherheit | MITTEL (CSP-Mismatch, CORS *) |
| Rechtliches | KRITISCH (Impressum/Datenschutz) |
| Code-Qualität | MITTEL (Duplikate, keine Tests) |
| Performance | GUT |
| Architektur | GUT |
| UX/Design | SEHR GUT |

### Top-5 Handlungsempfehlungen

1. **`parse_birth_time()` implementieren** – Backend ist ohne diese Funktion nicht funktionsfähig
2. **Impressum & Datenschutz vervollständigen** – Rechtspflicht
3. **CSP-Headers mit CDN-Scripts abstimmen** oder Scripts lokal bundlen
4. **Duplikate bereinigen** – Root-HTML vs. public/ klären
5. **Tests hinzufügen** – Mindestens für Backend-Logik (Zodiac, Mondphase, etc.)
