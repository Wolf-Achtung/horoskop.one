# 💀 HORRORSKOPE.ONE

**Satirisches Horror-Horoskop-Projekt** — Zombies, Vampire, Aliens und praktische Überlebenstipps basierend auf deinen Geburtsdaten!

## 🧟 Was ist das?

HORRORSKOPE.ONE ist ein humorvolles Projekt, das traditionelle Astrologie mit satirischem Horror kombiniert. Basierend auf Geburtsdatum, Geburtsort und optional Geburtszeit generiert die Anwendung übertriebene "Gefahren-Vorhersagen" (Zombies, Vampire, Aliens, kosmische Schrecken) — immer mit einem Augenzwinkern und praktischen "Überlebenstipps".

⚠️ **WICHTIG:** Dies ist reine **SATIRE und UNTERHALTUNG**! Alle Gefahren sind FIKTIV.

## 🔮 Features

- **Horror-Gefahren-Vorhersagen:** Zombies, Vampire, Aliens, Dämonen, verfluchte Objekte
- **Astrologische Basis:** Sternzeichen, Mondphasen, Aszendent, Häuser, I-Ging, Numerologie
- **KI-generierter Content:** GPT-4o-mini erstellt satirische Horror-Szenarien
- **Überlebenstipps:** Praktische (und absurde) Ratschläge zur Gefahren-Abwehr
- **Vier Kategorien:**
  - 🧟 Drohende Gefahren
  - 🛡️ Überlebensstrategien
  - 💀 Beziehungen im Chaos
  - ✨ Schutzrituale

## 🛠️ Technologie-Stack

### Backend
- **Python 3.12** + FastAPI
- **OpenAI GPT-4o-mini** für Horror-Content-Generierung
- **pyswisseph** für astrologische Berechnungen (optional)
- **Nominatim** für Geocoding

### Frontend
- **TypeScript** + esbuild
- **Vanilla DOM** (kein Framework)
- **Canvas API** für Zodiac-Wheel und Share-Cards
- **Dark Horror Theme** (CSS mit roten Akzenten)

### Deployment
- **Docker** Multi-Stage Build
- **Railway.app** / Nixpacks
- **Uvicorn** ASGI Server

## 📦 Installation & Setup

### Lokale Entwicklung

1. **Repository klonen:**
```bash
git clone https://github.com/Wolf-Achtung/horoskop.one.git
cd horoskop.one
```

2. **Python Dependencies installieren:**
```bash
pip install -r requirements.txt
```

3. **Environment Variables setzen:**
```bash
export OPENAI_API_KEY="your-openai-api-key"
export OPENAI_MODEL="gpt-4o-mini"  # optional
```

4. **Frontend bauen:**
```bash
npm install
npm run build
```

5. **Server starten:**
```bash
python main.py
# oder
uvicorn main:app --host 0.0.0.0 --port 8080
```

6. **Öffnen:** http://localhost:8080

### Docker

```bash
docker build -t horrorskope .
docker run -p 8080:8080 -e OPENAI_API_KEY="your-key" horrorskope
```

### Railway Deployment

1. Dieses Repository als Railway-Projekt deployen
2. Environment Variables setzen:
   - `OPENAI_API_KEY` (required)
   - `OPENAI_MODEL` (optional, default: gpt-4o-mini)
   - `CORS_ALLOW_ORIGINS` (optional)
   - `SWE_URL` (optional, für separaten Swiss Ephemeris Worker)
   - `HOUSE_SYSTEM` (optional, default: P für Placidus)
3. Start über `Procfile`: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## 🎨 Projekt-Struktur

```
horoskop.one/
├── main.py                 # FastAPI Backend + Horrorskope-Logik
├── requirements.txt        # Python Dependencies
├── Dockerfile             # Multi-Stage Build
├── Procfile               # Railway Deployment
├── package.json           # Node.js Build Config
├── src/                   # TypeScript Frontend
│   ├── main.ts            # Entry Point
│   ├── readingApi.ts      # API Client
│   ├── geocode.ts         # Nominatim Autocomplete
│   ├── zodiac.ts          # Canvas Rendering
│   └── sharecard.ts       # PNG Generation
├── public/                # Static Assets + HTML
│   ├── index.html         # Main Page
│   ├── styles.css         # Horror Theme CSS
│   ├── methoden.html      # Methodology Page
│   ├── impressum.html     # Imprint
│   ├── datenschutz.html   # Privacy Policy
│   └── assets/            # SVG, JSON, Images
├── swe_worker/            # Optional Swiss Ephemeris Worker
│   ├── swe_worker.py
│   └── requirements.txt
└── scripts/               # Build Scripts
    └── build.mjs          # esbuild Configuration
```

## 🧪 API Endpoints

### `POST /reading`
Generiert ein Horrorskope basierend auf Geburtsdaten.

**Request:**
```json
{
  "birthDate": "12.08.1980",
  "birthPlace": "Berlin",
  "birthTime": "14:30",
  "period": "week",
  "tone": "balanced"
}
```

**Response:**
```json
{
  "meta": {
    "period": "week",
    "birthDate": "12.08.1980",
    "birthPlace": "Berlin",
    "geo": {"lat": 52.52, "lon": 13.405, "tz": "Europe/Berlin"},
    "mini": {
      "sunSignApprox": "Löwe",
      "moonPhase": "Vollmond",
      "chinese": "Affe",
      "lifePath": 7
    }
  },
  "sections": [
    {
      "title": "🧟 Drohende Gefahren",
      "text": "Die Sterne warnen vor einer Zombie-Invasion...",
      "chips": ["Sternzeichen Löwe", "Mondphase: Vollmond"]
    },
    {
      "title": "🛡️ Überlebensstrategien",
      "text": "Deine beste Verteidigung...",
      "chips": ["Lebenszahl 7", "Ort: Berlin"]
    },
    {
      "title": "💀 Beziehungen im Chaos",
      "text": "Achte auf Vampire in deinem sozialen Umfeld...",
      "chips": ["Chinesisch: Affe"]
    },
    {
      "title": "✨ Schutzrituale",
      "text": "Trage Knoblauch und meide dunkle Gassen...",
      "chips": ["Baum: Eiche"]
    }
  ],
  "disclaimer": "⚠️ WICHTIG: Dies ist reine SATIRE und UNTERHALTUNG!"
}
```

### `GET /health`
Service Health Check

**Response:**
```json
{
  "ok": true,
  "model": "gpt-4o-mini"
}
```

## 🎭 Konzept & Philosophie

**Humor vor Horror, Satire vor Schrecken, Lachen vor Angst.**

Das Leben ist schon gruselig genug — warum nicht darüber lachen? HORRORSKOPE.ONE nutzt astrologische Systeme als kreative Grundlage für absurde Horror-Szenarien, die immer mit einem Augenzwinkern präsentiert werden.

## ⚠️ Wichtige Hinweise

- **KEINE echten Gefahren:** Alle Vorhersagen sind FIKTIV
- **Reine Unterhaltung:** Nicht ernst nehmen!
- **Keine Haftung:** Für Begegnungen mit tatsächlichen Zombies übernehmen wir keine Verantwortung 😄
- **Bei echten Krisen:** 112 (EU) oder lokale Beratungsstellen

## 🔧 Entwicklung

### Frontend Build
```bash
npm run build    # Production Build
npm run dev      # Development Build
```

### Python Tests
```bash
pytest  # (wenn Tests vorhanden)
```

### Code-Qualität
- **Python:** FastAPI + Pydantic für Type Safety
- **TypeScript:** Strict Mode aktiviert
- **Security:** CSP Headers, SRI Integrity Hashes
- **Privacy:** Keine dauerhafte Datenspeicherung

## 📝 Changelog

### v6.0 - Horror Edition
- 🎃 Transformation von Horoskop zu HORRORSKOPE
- 🧟 Neue Gefahren-Kategorien (Zombies, Vampire, Aliens)
- 💀 Satirische Horror-Content-Generierung
- 🛡️ Praktische Überlebenstipps
- 🎨 Dark Horror Theme (rote Akzente)
- ✨ Alle HTML-Seiten auf Horror-Theme umgestellt

### v5.4 - Longform Edition (Original)
- Ursprüngliches Horoskop-Projekt
- Astrologische Berechnungen
- OpenAI Integration

## 📧 Kontakt & Support

Bei Fragen, Bugs oder Feature-Requests:
- **Issues:** https://github.com/Wolf-Achtung/horoskop.one/issues
- **E-Mail:** [Support-Adresse einfügen]

## 📜 Lizenz

[Lizenz hier einfügen]

## 🙏 Credits & Danksagungen

- **OpenAI GPT-4o-mini** für kreative Horror-Text-Generierung
- **OpenStreetMap Nominatim** für Geocoding
- **pyswisseph** für präzise astrologische Berechnungen
- Alle Horror-Film-Fans und Satire-Liebhaber da draußen! 🎬

---

**Made with 💀 and schwarzem Humor**

*Keine Zombies wurden bei der Entwicklung dieser Software verletzt.*
*Vampire mochten den Dark Mode.*
*Aliens finden die Geocoding-Präzision beeindruckend.*
