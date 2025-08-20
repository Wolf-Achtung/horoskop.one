# main.py — horoskop.one API (Option C: decoupled SWE) — v5.5
# Python 3.12+  |  FastAPI + OpenAI | Railway/Nixpacks
# SWE (Swiss Ephemeris) wird NICHT lokal installiert, sondern optional via SWE_URL aufgerufen.

import os
import re
import json
import datetime as dt
from typing import Optional, Dict, Any, List

import httpx
from fastapi import FastAPI, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from timezonefinder import TimezoneFinder
from zoneinfo import ZoneInfo

# --- OpenAI Client (modernes SDK) ---
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

app = FastAPI(title="horoskop.one API", version="v5.5 (Option C)")

# ---------- CORS ----------
raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
if not origins:
    origins = ["*"]  # Im Prod lieber Domains setzen

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)

# ---------- Utils ----------
tf = TimezoneFinder()
SWE_URL = os.getenv("SWE_URL")  # z. B. https://swe-worker-production.up.railway.app/swe


def parse_birth_date(date_str: str) -> Optional[dt.date]:
    s = (date_str or "").strip()
    # Accept "DD.MM.YYYY" and "YYYY-MM-DD"
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return dt.date(y, mth, d)
    m2 = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m2:
        y, mth, d = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        return dt.date(y, mth, d)
    return None

def parse_birth_time(time_str: Optional[str]) -> Optional[dt.time]:
    if not time_str:
        return None
    m = re.match(r"(\d{1,2}):(\d{2})", time_str.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return dt.time(max(0, min(23, h)), max(0, min(59, mi)))



def normalize_daypart(val: Optional[str]) -> Optional[str]:
    """Map UI tokens to expected German tokens."""
    if not val:
        return None
    t = (val or "").strip().lower()
    # English UI tokens
    if t in ("morning",): return "morgens"
    if t in ("noon","midday","mid-day","mid day"): return "mittags"
    if t in ("evening",): return "abends"
    if t in ("night","late"): return "nachts"
    # German already
    if t in ("morgens","mittags","abends","nachts","unbekannt"): return t
    # Fallback
    return None

def daypart_from_time(t: Optional[dt.time]) -> str:
    if not t:
        return "unbekannt"
    h = t.hour
    if 5 <= h < 11:   return "morgens"
    if 11 <= h < 15:  return "mittags"
    if 15 <= h < 20:  return "abends"
    return "nachts"

def zodiac_from_date(d: dt.date) -> str:
    edges = [
        ("Steinbock", 1, 19), ("Wassermann", 2, 18), ("Fische", 3, 20),
        ("Widder", 4, 19), ("Stier", 5, 20), ("Zwillinge", 6, 20),
        ("Krebs", 7, 22), ("Löwe", 8, 22), ("Jungfrau", 9, 22),
        ("Waage", 10, 22), ("Skorpion", 11, 21), ("Schütze", 12, 21),
        ("Steinbock", 12, 31),
    ]
    m, dd = d.month, d.day
    for name, mm, lim in edges:
        if (m < mm) or (m == mm and dd <= lim):
            return name
    return "Steinbock"

def chinese_animal(year: int) -> str:
    animals = ["Ratte","Büffel","Tiger","Hase","Drache","Schlange","Pferd",
               "Ziege","Affe","Hahn","Hund","Schwein"]
    idx = ((year - 1900) % 12 + 12) % 12
    return animals[idx]

def life_path_number(d: dt.date) -> int:
    s = f"{d.year:04d}{d.month:02d}{d.day:02d}"
    n = sum(int(c) for c in s)
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(c) for c in str(n))
    return n

def moon_phase_fraction(day: dt.date) -> float:
    # einfache Approximation (0 neu, 0.5 voll)
    ref = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)
    current = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc)
    synodic = 29.53058867
    days = (current - ref).total_seconds() / 86400.0
    return ((days % synodic) / synodic)

def moon_phase_name(frac: float) -> str:
    if frac < 0.03 or frac > 0.97: return "Neumond"
    if 0.03 <= frac < 0.25: return "zunehmende Sichel"
    if 0.25 <= frac < 0.27: return "erstes Viertel"
    if 0.27 <= frac < 0.47: return "zunehmender Mond"
    if 0.47 <= frac < 0.53: return "Vollmond"
    if 0.53 <= frac < 0.73: return "abnehmender Mond"
    if 0.73 <= frac < 0.75: return "letztes Viertel"
    return "abnehmende Sichel"

def season_from_date_hemisphere(d: dt.date, lat: Optional[float]) -> str:
    north = (lat is None) or (lat >= 0)
    m = d.month
    if north:
        return ["Winter","Winter","Frühling","Frühling","Frühling",
                "Sommer","Sommer","Sommer","Herbst","Herbst","Herbst","Winter"][m-1]
    else:
        return ["Sommer","Sommer","Herbst","Herbst","Herbst",
                "Winter","Winter","Winter","Frühling","Frühling","Frühling","Sommer"][m-1]

async def geocode(place: str) -> Optional[Dict[str, float]]:
    if not place:
        return None
    url = "https://nominatim.openstreetmap.org/search"
    params = {"format":"json","limit":"1","q": place}
    headers = {"User-Agent":"horoskop.one/1.0 (contact: support@horoskop.one)"}
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(url, params=params, headers=headers)
        if r.status_code != 200:
            return None
        data = r.json() or []
        if not data:
            return None
        try:
            return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
        except Exception:
            return None

def find_timezone(lat: Optional[float], lon: Optional[float]) -> str:
    if lat is None or lon is None:
        return "Europe/Berlin"
    try:
        tz = tf.timezone_at(lat=lat, lng=lon)
        return tz or "Europe/Berlin"
    except Exception:
        return "Europe/Berlin"

# ---------- SWE Remote ----------
async def swe_compute_remote(bdate: dt.date, btime: Optional[dt.time], lat: Optional[float], lon: Optional[float], tzname: str) -> Optional[Dict[str, Any]]:
    if not (SWE_URL and btime and lat is not None and lon is not None and tzname):
        return None
    payload = {
        "birthDate": bdate.isoformat(),
        "birthTime": btime.strftime("%H:%M"),
        "lat": lat,
        "lon": lon,
        "tzname": tzname,
        "houseSystem": os.getenv("HOUSE_SYSTEM", "P")
    }
    try:
        async with httpx.AsyncClient(timeout=8) as cli:
            r = await cli.post(SWE_URL, json=payload)
            if r.status_code == 200:
                return r.json()
    except Exception:
        return None
    return None

# ---------- OpenAI helper & JSON parser ----------
def oa_text(prompt: str, seed: Optional[int] = None, temperature: float = 0.8) -> str:
    kwargs = dict(
        model=MODEL,
        temperature=temperature,
        messages=[
            {"role":"system","content":"Du bist ein präziser, poetischer, freundlicher Schreibassistent."},
            {"role":"user","content":prompt},
        ],
    )
    if seed is not None:
        kwargs["seed"] = seed
    cr = client.chat.completions.create(**kwargs)
    return cr.choices[0].message.content

def try_load_json(maybe: str) -> Any:
    m = re.search(r"```json([\s\S]*?)```", maybe)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    m = re.search(r"\{[\s\S]*\}$", maybe.strip())
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    try:
        return json.loads(maybe)
    except Exception:
        return {"raw": maybe}


def ensure_numeric_mixer(mix: Optional[Dict[str, float]]):
    if not mix: 
        return None
    out = {}
    for k, v in mix.items():
        try:
            out[str(k)] = float(v)
        except Exception:
            continue
    return out or None
# ---------- Schemas ----------
class ReadingRequest(BaseModel):
    birthDate: str
    birthPlace: str
    birthTime: Optional[str] = None
    approxDaypart: Optional[str] = None        # morgens/mittags/abends/nachts/unbekannt
    period: str = Field("day", description="day|week|month")
    tone: str = "mystic_deep"
    seed: Optional[int] = None
    mixer: Optional[Dict[str, float]] = None

class Section(BaseModel):
    title: str
    text: str
    chips: List[str] = Field(default_factory=list)

class ReadingResponse(BaseModel):
    meta: Dict[str, Any]
    sections: List[Section]
    chips: List[str] = Field(default_factory=list)
    disclaimer: str

# ---------- Routes ----------
@app.get("/health")
def health():
    return {"ok": True, "model": MODEL, "swe_url": bool(SWE_URL)}

@app.post("/reading", response_model=ReadingResponse)
async def reading(req: ReadingRequest = Body(...)):
    # --- Basic parsing ---
    bdate = parse_birth_date(req.birthDate) or dt.date.today()
    btime = parse_birth_time(req.birthTime)
    dpart = (normalize_daypart(req.approxDaypart) or daypart_from_time(btime)).lower()

    # --- Geocoding / Timezone ---
    geo = await geocode(req.birthPlace)
    lat = geo["lat"] if geo else None
    lon = geo["lon"] if geo else None
    tzname = find_timezone(lat, lon)

    # --- Facts ---
    hemisphere = "Nord" if (lat is None or lat >= 0) else "Süd"
    season = season_from_date_hemisphere(bdate, lat)
    sun_sign = zodiac_from_date(bdate)
    cn_animal = chinese_animal(bdate.year)
    lifepath = life_path_number(bdate)
    mf = moon_phase_fraction(bdate)
    moon = moon_phase_name(mf)

    # --- SWE Remote (optional) ---
    swe_data = await swe_compute_remote(bdate, btime, lat, lon, tzname)

    mixer = ensure_numeric_mixer(req.mixer) or {}
    mixer_list = [f"{k}:{v}%" for k, v in mixer.items()]
    why_chips = [
        f"Sternzeichen {sun_sign}",
        f"Ort {req.birthPlace or 'unbekannt'}",
        f"Saison: {season} ({hemisphere}-Halbkugel)",
        f"Mondphase: {moon}",
    ]
    if swe_data:
        why_chips.append(f"Aszendent {swe_data['ascendant']['sign']}")
        if swe_data.get("sunHouse"):
            why_chips.append(f"Sonnenhaus {swe_data['sunHouse']}")
        if swe_data.get("moonHouse"):
            why_chips.append(f"Mondhaus {swe_data['moonHouse']}")

    # --- Double-Pass 1: Outline ---
    outline_prompt = f"""
    Du bist ein achtsam-mystischer Coach. Erstelle eine OUTLINE als JSON (keinen Fließtext).
    Struktur:
    {{
     "fokus": {{"kern":"...", "punkte":["...","...","..."]}},
     "beruf": {{"kern":"...", "punkte":["...","...","..."]}},
     "liebe": {{"kern":"...", "punkte":["...","...","..."]}},
     "energie": {{"kern":"...", "punkte":["...","...","..."]}}
    }}

    Rahmendaten:
    - Zeitraum: {req.period}
    - Ort: {req.birthPlace} → lat={lat}, lon={lon}, Zeitzone={tzname}
    - Datum: {bdate.strftime('%d.%m.%Y')} · Tagesabschnitt: {dpart}
    - Saison/Hemisphäre: {season} / {hemisphere}
    - Mini-Fakten: Sonne≈{sun_sign}, Mondphase={moon}, Lebenszahl={lifepath}, Chinesisch={cn_animal}
    - Mixer: {', '.join(mixer_list) if mixer_list else 'Standard'}
    - Swiss-Ephemeris: {'aktiv' if swe_data else 'aus'}

    Regeln:
    - Pro Bereich 3–4 Stichpunkte, abgeleitet aus dem Kontext.
    - Letzter Stichpunkt = Mini-Aktion (imperativ, 1 Satz).
    - Keine heiklen medizinisch/juristisch/finanziellen Ratschläge.
    """.strip()

    try:
        outline_raw = oa_text(outline_prompt, seed=req.seed, temperature=0.4)
        outline = try_load_json(outline_raw)
    except Exception as e:
        outline = {"fokus":{"kern":"","punkte":[]}, "error": str(e)}

    # --- Double-Pass 2: Longform ---
    swe_line = (
        f"Aszendent {swe_data['ascendant']['sign']}, MC {swe_data['mc']['sign']}, "
        f"Sonnenhaus {swe_data.get('sunHouse')}, Mondhaus {swe_data.get('moonHouse')}"
    ) if swe_data else "keine genaue Zeit/Ort ⇒ Aszendent & Häuser unbekannt"

    writing_prompt = f"""
    Formuliere aus der OUTLINE ein Horoskop mit 3–4 Sätzen je Sektion im Ton „mystischer Coach“
    (poetisch, warm, aber klar). Integriere die Mini-Aktion organisch in den Absatz. Keine Bullet-Listen.

    Kontext (nur nutzen, nicht erneut aufzählen):
    - Zeitraum: {req.period} · Ort: {req.birthPlace} (Zeitzone {tzname})
    - Saison/Hemisphäre: {season} / {hemisphere}
    - Sonne≈{sun_sign}, Mondphase {moon}, Lebenszahl {lifepath}, Tagesabschnitt {dpart}.
    - Swiss-Ephemeris: {swe_line}.

    OUTLINE:
    ```json
    {json.dumps(outline, ensure_ascii=False, indent=2)}
    ```

    Gebe das Ergebnis als JSON zurück:
    {{
      "fokus": "Absatz",
      "beruf": "Absatz",
      "liebe": "Absatz",
      "energie": "Absatz"
    }}
    """.strip()

    try:
        longform_raw = oa_text(writing_prompt, seed=req.seed, temperature=0.8)
        data = try_load_json(longform_raw)
    except Exception as e:
        data = {"fokus": "", "beruf": "", "liebe": "", "energie": "", "error": str(e)}

    # --------- Ergebnis ---------
    sections = [
        Section(title="Fokus",  text=(data.get("fokus") or "").strip(),
                chips=[f"Sternzeichen {sun_sign}", f"Ort {req.birthPlace or 'unbekannt'}", f"Saison: {season}"]),
        Section(title="Beruf",  text=(data.get("beruf") or "").strip(),
                chips=[f"Lebenszahl {lifepath}"]),
        Section(title="Liebe",  text=(data.get("liebe") or "").strip(),
                chips=[f"Mondphase: {moon}"]),
        Section(title="Energie", text=(data.get("energie") or "").strip(),
                chips=[f"Tag/Nacht: {dpart}"]),
    ]

    disclaimer = (
        "Hinweis: Dieses Angebot dient ausschließlich der Unterhaltung "
        "und achtsamen Selbstreflexion und ersetzt keine professionelle Beratung. "
        "Bei Krisen oder akuter Gefahr: 112 (EU) / lokale Beratungsstellen."
    )

    meta = {
        "period": req.period,
        "tone": req.tone,
        "birthDate": req.birthDate,
        "birthPlace": req.birthPlace,
        "birthTime": req.birthTime,
        "approxDaypart": dpart,
        "geo": {"lat": lat, "lon": lon, "tz": tzname},
        "season": season,
        "hemisphere": hemisphere,
        "mini": {
            "sunSignApprox": sun_sign,
            "moonPhase": moon,
            "moonFrac": round(mf, 3),
            "lifePath": lifepath,
            "chinese": cn_animal
        },
        "swiss": swe_data,
    }

    return ReadingResponse(meta=meta, sections=sections, chips=why_chips, disclaimer=disclaimer)
