# main.py  — horoskop.one API v6.0 deep-reading (single-file)
import os, re, json, datetime as dt
from typing import Optional, Dict, Any, List

import httpx
from fastapi import FastAPI, Body, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from timezonefinder import TimezoneFinder
from zoneinfo import ZoneInfo

# Rate limiting (slowapi) — optional: falls das Paket fehlt, läuft die App
# ohne Rate-Limiting weiter, statt beim Import abzustürzen.
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _HAS_SLOWAPI = True
except ImportError:
    _HAS_SLOWAPI = False

from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

# --- LLM-Provider-Abstraktion ----------------------------------------------
# Ein dünnes eigenes Interface statt OpenRouter/LiteLLM: bei zwei Prompt-Typen
# und Beta-Volumen ist ein Gateway Overkill. Der Provider wird per
# LLM_PROVIDER (openai|anthropic) gewählt; der Anthropic-Client ist optional —
# fehlt SDK oder Key, läuft alles unverändert über OpenAI weiter.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
try:
    import anthropic as _anthropic_sdk
    _anthropic_client = _anthropic_sdk.Anthropic() if os.getenv("ANTHROPIC_API_KEY") else None
except ImportError:
    _anthropic_sdk = None
    _anthropic_client = None
if LLM_PROVIDER == "anthropic" and _anthropic_client is None:
    print("LLM_PROVIDER=anthropic gesetzt, aber ANTHROPIC_API_KEY/SDK fehlt — nutze openai.")
    LLM_PROVIDER = "openai"

def _llm_id(provider: Optional[str] = None) -> str:
    p = (provider or LLM_PROVIDER)
    return f"anthropic:{ANTHROPIC_MODEL}" if p == "anthropic" else f"openai:{MODEL}"

app = FastAPI(title="horoskop.one API", version="v6.0-deep-reading")

# CORS: Default ist eine restriktive Allowlist der bekannten horoskop.one-Domains.
# Über CORS_ALLOW_ORIGINS (komma-separiert) kann das überschrieben werden, z. B.
# CORS_ALLOW_ORIGINS="*" für offene APIs in Dev-Umgebungen.
DEFAULT_ORIGINS = [
    "https://horoskop.one",
    "https://www.horoskop.one",
    "https://horoskopone-production-4739.up.railway.app",
    "https://horoskopone-production.up.railway.app",
]
def _resolve_cors(raw_origins: str, defaults: List[str]):
    """Parse CORS_ALLOW_ORIGINS and decide whether credentials are safe.

    A wildcard origin combined with allow_credentials=True lets any site on
    the same platform (e.g. *.railway.app) send credentialed cross-origin
    requests, so credentials are disabled automatically whenever a wildcard
    is configured (explicit or via a default that includes "*").
    """
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()] or defaults
    return origins, ("*" not in origins)

origins, _allow_credentials = _resolve_cors(os.getenv("CORS_ALLOW_ORIGINS", ""), DEFAULT_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=_allow_credentials,
    allow_methods=["*"], allow_headers=["*"],
)

# Security headers — applied as real HTTP response headers on every response
# (API routes and the StaticFiles-mounted frontend alike).
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(self), camera=(), microphone=()",
    # HSTS without `includeSubDomains`/`preload` on purpose: the apex and the
    # www subdomain are currently served by different platforms, and a
    # subdomain whose certificate does not match turns an HSTS pin into an
    # unbypassable browser error (ERR_CERT_COMMON_NAME_INVALID with no
    # click-through). Re-add `includeSubDomains; preload` only once *every*
    # subdomain serves a valid certificate. Overridable via HSTS_HEADER.
    "Strict-Transport-Security": os.getenv("HSTS_HEADER", "max-age=31536000"),
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; "
        "connect-src 'self' https://horoskopone-production-4739.up.railway.app "
        "https://horoskopone-production.up.railway.app https://nominatim.openstreetmap.org; "
        "img-src 'self' data: blob:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; base-uri 'self'; frame-ancestors 'none'; "
        "form-action 'self'"
    ),
}

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response

# Rate limiting (optional) — schützt den OpenAI-Key vor Missbrauch.
if _HAS_SLOWAPI:
    limiter = Limiter(key_func=get_remote_address, default_limits=[])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
else:
    limiter = None

# Rate limiting tuning — `/reading` is the expensive endpoint (OpenAI +
# Swiss Ephemeris + Nominatim), so we default to a strict per-IP budget:
# six calls per minute to allow quick "Heute → Woche → Monat" exploration
# without enabling brute-force abuse, and eighty per day to cap long-tail
# scripted replay. Both limits stack via slowapi's "L1;L2" syntax and can
# be overridden at deploy time via the READING_RATE_LIMIT env var.
READING_RATE_LIMIT = os.getenv("READING_RATE_LIMIT", "6/minute;80/day")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "body": exc.body})

@app.get("/favicon.ico")
def favicon(): return Response(status_code=204)

tf = TimezoneFinder()

def parse_birth_date(date_str: str) -> Optional[dt.date]:
    s = (date_str or '').strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', s)
    if m:
        y, mth, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return dt.date(y, mth, d)
    m = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$', s)
    if m:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y = 2000 + y if y < 30 else 1900 + y
        return dt.date(y, mth, d)
    return None

def parse_birth_time(time_str: str) -> Optional[dt.time]:
    s = (time_str or '').strip()
    m = re.match(r'^(\d{1,2}):(\d{2})$', s)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return dt.time(max(0, min(23, h)), max(0, min(59, mi)))

def daypart_from_time(t: Optional[dt.time]) -> str:
    if not t: return "unbekannt"
    h = t.hour
    return "morgens" if 5<=h<11 else "mittags" if 11<=h<15 else "abends" if 15<=h<20 else "nachts"

def zodiac_from_date(d: dt.date) -> str:
    edges=[("Steinbock",1,19),("Wassermann",2,18),("Fische",3,20),("Widder",4,19),("Stier",5,20),
           ("Zwillinge",6,20),("Krebs",7,22),("Löwe",8,22),("Jungfrau",9,22),("Waage",10,22),
           ("Skorpion",11,21),("Schütze",12,21),("Steinbock",12,31)]
    m,dd=d.month,d.day
    for name,mm,lim in edges:
        if (m<mm) or (m==mm and dd<=lim): return name
    return "Steinbock"

def chinese_animal(year:int)->str:
    animals=["Ratte","Büffel","Tiger","Hase","Drache","Schlange","Pferd","Ziege","Affe","Hahn","Hund","Schwein"]
    return animals[((year-1900)%12+12)%12]

# ---------------------------------------------------------------------------
# Numerology
# ---------------------------------------------------------------------------
# Numerology keeps its "Meisterzahlen" 11 / 22 / 33 unreduced — they carry
# extra meaning in the tradition. The single-digit description is stored as
# a lookup so the LLM can be pointed at concrete archetypes.

def _reduce_to_digit(n: int, keep_master: bool = True) -> int:
    """Iteratively sum digits until the number is < 10 (unless a master)."""
    while n > 9 and (not keep_master or n not in (11, 22, 33)):
        n = sum(int(c) for c in str(abs(n)))
    return n

def life_path_number(d: dt.date) -> int:
    """Lebenszahl — sum of all digits in YYYYMMDD, master numbers preserved."""
    s = f"{d.year:04d}{d.month:02d}{d.day:02d}"
    return _reduce_to_digit(sum(int(c) for c in s))

def birthday_number(d: dt.date) -> int:
    """Geburtstagszahl — the day of birth, reduced (11/22 preserved)."""
    return _reduce_to_digit(d.day)

def personal_year_number(bdate: dt.date, ref: Optional[dt.date] = None) -> int:
    """Persönliche Jahreszahl — a rolling 1–9 cycle that changes each year.
    Calculated from the birth month + birth day + CURRENT year (not birth year).
    """
    ref = ref or dt.date.today()
    return _reduce_to_digit(bdate.month + bdate.day + ref.year, keep_master=False)

def personal_month_number(bdate: dt.date, ref: Optional[dt.date] = None) -> int:
    """Persönliche Monatszahl — personal year + current calendar month."""
    ref = ref or dt.date.today()
    return _reduce_to_digit(personal_year_number(bdate, ref) + ref.month, keep_master=False)

def personal_day_number(bdate: dt.date, ref: Optional[dt.date] = None) -> int:
    """Persönliche Tageszahl — personal month + current day of month."""
    ref = ref or dt.date.today()
    return _reduce_to_digit(personal_month_number(bdate, ref) + ref.day, keep_master=False)

# Short, sober archetype descriptions for the nine single digits plus masters.
_LIFEPATH_ARCHETYPES: Dict[int, str] = {
    1: "Pionier — Initiative, Autonomie, Führung. Aufgabe: Unabhängigkeit ohne Einsamkeit.",
    2: "Vermittler — Diplomatie, Sensibilität, Paardynamik. Aufgabe: Grenzen setzen statt verschmelzen.",
    3: "Ausdruck — Kreativität, Sprache, Leichtigkeit. Aufgabe: Tiefe statt Zerstreuung.",
    4: "Bauer — Struktur, Ausdauer, Verlässlichkeit. Aufgabe: Flexibilität statt Sturheit.",
    5: "Wandler — Freiheit, Neugier, Wandel. Aufgabe: Verbindlichkeit ohne Enge.",
    6: "Hüter — Verantwortung, Fürsorge, Harmonie. Aufgabe: Eigenbedürfnis vor Helfersyndrom.",
    7: "Sucher — Analyse, Rückzug, Tiefe. Aufgabe: Vertrauen ins Außen, nicht nur ins Innen.",
    8: "Manifestierer — Macht, Struktur, Material. Aufgabe: Ethik statt Kontrolle.",
    9: "Vollender — Weisheit, Loslassen, Universelles. Aufgabe: Mitgefühl ohne Selbstaufgabe.",
    11: "Meisterzahl — Visionär, Inspirator; 2× 1, hohe Empfindsamkeit, Nervensystem schonen.",
    22: "Meisterzahl — Baumeister; visionärer Macher, große Strukturen, Burn-out-Risiko.",
    33: "Meisterzahl — Lehrer der Liebe; dient bedingungslos, Grenzen notwendig.",
}

def lifepath_archetype(n: int) -> str:
    return _LIFEPATH_ARCHETYPES.get(n, "")

def moon_phase_fraction(day:dt.date)->float:
    ref=dt.datetime(2000,1,6,18,14,tzinfo=dt.timezone.utc); current=dt.datetime(day.year,day.month,day.day,tzinfo=dt.timezone.utc)
    syn=29.53058867; days=(current-ref).total_seconds()/86400.0
    return ((days%syn)/syn)

def moon_phase_name(frac:float)->str:
    if frac<0.03 or frac>0.97: return "Neumond"
    if 0.03<=frac<0.25: return "zunehmende Sichel"
    if 0.25<=frac<0.27: return "erstes Viertel"
    if 0.27<=frac<0.47: return "zunehmender Mond"
    if 0.47<=frac<0.53: return "Vollmond"
    if 0.53<=frac<0.73: return "abnehmender Mond"
    if 0.73<=frac<0.75: return "letztes Viertel"
    return "abnehmende Sichel"

def season_from_date_hemisphere(d:dt.date, lat:Optional[float])->str:
    north=(lat is None) or (lat>=0); m=d.month
    return (["Winter","Winter","Frühling","Frühling","Frühling","Sommer","Sommer","Sommer","Herbst","Herbst","Herbst","Winter"] if north
            else ["Sommer","Sommer","Herbst","Herbst","Herbst","Winter","Winter","Winter","Frühling","Frühling","Frühling","Sommer"])[m-1]

# ---------------------------------------------------------------------------
# I-Ging — all 64 hexagrams with German name + one-line core meaning.
# Index matches the classical King-Wen order (1–64).
# ---------------------------------------------------------------------------
ICHING_HEXAGRAMS: List[Dict[str, str]] = [
    {},  # 0 placeholder so ICHING_HEXAGRAMS[1] == hexagram 1
    {"name": "Das Schöpferische", "core": "Starke, klare Initiative. Handle direkt und aus innerer Überzeugung."},
    {"name": "Das Empfangende", "core": "Hingabe und Annehmen. Folge, beobachte, reagiere statt zu forcieren."},
    {"name": "Die Anfangsschwierigkeit", "core": "Mühsamer Start. Kleine Schritte, nicht alles auf einmal."},
    {"name": "Die Jugendtorheit", "core": "Lernphase — frage Erfahrene, bleibe offen für Korrektur."},
    {"name": "Das Warten", "core": "Geduld. Der richtige Moment ist noch nicht gekommen."},
    {"name": "Der Streit", "core": "Konflikt sichtbar. Eine Lösung erfordert einen kühlen Kopf und klare Grenzen."},
    {"name": "Das Heer", "core": "Disziplin und Führung. Kollektive Aufgabe — Struktur geht vor Spontanität."},
    {"name": "Das Zusammenhalten", "core": "Verbünde dich mit den Richtigen. Loyalität wird belohnt."},
    {"name": "Des Kleinen Zähmungskraft", "core": "Kleine, sanfte Einflussnahme. Sei subtil, nicht laut."},
    {"name": "Das Auftreten", "core": "Benimm dich würdig in schwieriger Umgebung. Keine Provokation."},
    {"name": "Der Friede", "core": "Harmonie und Gleichgewicht. Nutze die Phase für Aufbau."},
    {"name": "Die Stockung", "core": "Blockade und Stillstand. Rückzug und Sammlung statt Durchbruchsversuche."},
    {"name": "Gemeinschaft mit Menschen", "core": "Gemeinsame Sache, gemeinsames Ziel. Offenheit über Klüfte hinweg."},
    {"name": "Der Besitz von Großem", "core": "Fülle und Verantwortung. Teile, statt zu horten."},
    {"name": "Die Bescheidenheit", "core": "Wahre Größe versteckt sich nicht, aber prahlt auch nicht."},
    {"name": "Die Begeisterung", "core": "Aufbruchsstimmung nutzen — aber mit Bodenhaftung."},
    {"name": "Die Nachfolge", "core": "Folge dem richtigen Impuls. Anpassen ist hier kein Schwäche-Zeichen."},
    {"name": "Die Arbeit am Verdorbenen", "core": "Altlasten aufräumen. Mut zur Reparatur, nicht zur Flucht."},
    {"name": "Die Annäherung", "core": "Vorsichtige Kontaktaufnahme. Freundlich, aber aufmerksam."},
    {"name": "Die Betrachtung", "core": "Überblick verschaffen. Erst sehen, dann urteilen."},
    {"name": "Das Durchbeißen", "core": "Hindernis direkt angehen. Entschlossen, aber gerecht."},
    {"name": "Die Anmut", "core": "Form zählt jetzt — Ästhetik, Stil, respektvoller Umgang."},
    {"name": "Die Zersplitterung", "core": "Zerfall sichtbar. Nicht kämpfen, sondern stabilisieren und abwarten."},
    {"name": "Die Wiederkehr", "core": "Wendepunkt. Das Alte kehrt in neuer Form zurück."},
    {"name": "Die Unschuld", "core": "Natürlichkeit und Aufrichtigkeit. Keine Berechnung."},
    {"name": "Des Großen Zähmungskraft", "core": "Große Kraft bändigen. Ressourcen bündeln, bevor du losstürmst."},
    {"name": "Die Ernährung", "core": "Achte darauf, womit du dich nährst — Gedanken, Worte, Beziehungen."},
    {"name": "Des Großen Übergewicht", "core": "Überlastung. Erleichtere das System, bevor es bricht."},
    {"name": "Das Abgründige", "core": "Gefahrenzone — bleib wachsam, aber fließe wie Wasser."},
    {"name": "Das Haftende (Feuer)", "core": "Klarheit und Leuchtkraft. Halte dich an klare Prinzipien."},
    {"name": "Die Einwirkung", "core": "Anziehung, Begegnung, Impuls. Ein neues Band entsteht."},
    {"name": "Die Dauer", "core": "Beständigkeit zählt. Rituale und Treue zu einer Richtung."},
    {"name": "Der Rückzug", "core": "Strategischer Rückzug ist keine Niederlage — er bewahrt die Kraft."},
    {"name": "Des Großen Macht", "core": "Große Kraft — nur gerecht eingesetzt, sonst zerstört sie."},
    {"name": "Der Fortschritt", "core": "Stetes Wachstum. Sonne geht auf, zeige dich."},
    {"name": "Die Verfinsterung des Lichts", "core": "Lichter Geist in dunkler Zeit. Nach innen arbeiten, nicht kämpfen."},
    {"name": "Die Sippe", "core": "Familie und enger Kreis tragen jetzt. Dort liegt die Kraft."},
    {"name": "Der Gegensatz", "core": "Anders-Denken begegnet. Suche nicht den Ausgleich um jeden Preis."},
    {"name": "Das Hemmnis", "core": "Hindernis. Stehenbleiben und die Lage neu bewerten."},
    {"name": "Die Befreiung", "core": "Die Last löst sich. Nutze den Moment für einen klaren Schnitt."},
    {"name": "Die Minderung", "core": "Weniger ist mehr. Abstriche machen, um Kernhaltung zu sichern."},
    {"name": "Die Mehrung", "core": "Zufluss und Wachstum. Teilen verstärkt die Wirkung."},
    {"name": "Der Durchbruch", "core": "Entschlossene Klarstellung. Ehrlich und direkt, ohne Kälte."},
    {"name": "Das Entgegenkommen", "core": "Begegnung mit dem Unerwarteten. Prüfe, bevor du zustimmst."},
    {"name": "Die Sammlung", "core": "Menschen kommen zusammen. Eine gemeinsame Mitte braucht es jetzt."},
    {"name": "Das Empordringen", "core": "Langsames, stetiges Aufsteigen. Kein Durchbruch, aber sichere Bewegung."},
    {"name": "Die Bedrängnis", "core": "Erschöpfung, Knappheit. Würde und innere Haltung bewahren."},
    {"name": "Der Brunnen", "core": "Die Quelle ist da, aber verschüttet — frei räumen, nicht neu graben."},
    {"name": "Die Umwälzung", "core": "Revolution, Häutung. Das Alte muss ganz gehen."},
    {"name": "Der Tiegel", "core": "Transformation durch Reife. Was jetzt entsteht, hält."},
    {"name": "Das Erregende (Donner)", "core": "Schock und Erschütterung — wirken lassen, nicht verdrängen."},
    {"name": "Das Stillehalten (Berg)", "core": "Innehalten, Meditation, Rückzug in die eigene Mitte."},
    {"name": "Die Entwicklung", "core": "Organisches Reifen. Nichts erzwingen, alles entfalten."},
    {"name": "Die heiratende Jüngste", "core": "Eine untergeordnete Rolle annehmen. Demut zahlt sich aus."},
    {"name": "Die Fülle", "core": "Gipfel der Kraft. Nutze sie, bevor das Licht wieder abnimmt."},
    {"name": "Der Wanderer", "core": "Fremde Umgebung. Sei höflich, zurückhaltend, beobachtend."},
    {"name": "Das Sanfte (Wind)", "core": "Beständig sanfter Druck bewirkt mehr als ein Sturm."},
    {"name": "Das Heitere (See)", "core": "Freude, Austausch, Verbundenheit. Vorsicht vor Oberflächlichkeit."},
    {"name": "Die Auflösung", "core": "Starre löst sich auf. Gefühle wieder fließen lassen."},
    {"name": "Die Beschränkung", "core": "Grenzen akzeptieren. Zu viel Freiheit lähmt."},
    {"name": "Innere Wahrheit", "core": "Aufrichtigkeit durchdringt jede Wand. Rede, was wirklich ist."},
    {"name": "Des Kleinen Übergewicht", "core": "Kleine Dinge sorgfältig tun. Jetzt keine große Geste."},
    {"name": "Nach der Vollendung", "core": "Ziel erreicht — nicht nachlässig werden, sonst zerfällt es."},
    {"name": "Vor der Vollendung", "core": "Kurz vor dem Durchbruch — letzte Ordnung, letzte Sorgfalt."},
]

def iching_index(d: dt.date) -> int:
    """Deterministic hexagram index (1..64) derived from the date."""
    daynum = (d - dt.date(d.year, 1, 1)).days + 1
    return ((daynum + d.year - 1) % 64) + 1

def iching_lookup(idx: int) -> Dict[str, str]:
    """Return {'name', 'core'} for a hexagram index (1..64)."""
    if 1 <= idx <= 64:
        return ICHING_HEXAGRAMS[idx]
    return {"name": "", "core": ""}

# ---------------------------------------------------------------------------
# Tarot — 22 Major Arcana with deterministic draw from birth date + period + seed.
# This is deliberately NOT randomized: we want two people with identical inputs
# to get the same card (and the same person to get the same card for the same
# period), so the reading is reproducible and cache-friendly.
# ---------------------------------------------------------------------------
TAROT_MAJOR: List[Dict[str, str]] = [
    {"name": "Der Narr",          "core": "Aufbruch ohne Plan, reiner Anfang, Vertrauen."},
    {"name": "Der Magier",        "core": "Willen, Werkzeuge, Fähigkeit zur Manifestation."},
    {"name": "Die Hohepriesterin","core": "Innere Weisheit, Intuition, das Ungesagte."},
    {"name": "Die Herrscherin",   "core": "Fülle, Natur, schöpferische Weiblichkeit."},
    {"name": "Der Herrscher",     "core": "Struktur, Autorität, klare Ordnung."},
    {"name": "Der Hierophant",    "core": "Tradition, Lehre, verbindende Werte."},
    {"name": "Die Liebenden",     "core": "Entscheidung für eine Verbindung, Wahl aus dem Herzen."},
    {"name": "Der Wagen",         "core": "Wille und Richtung. Disziplin siegt."},
    {"name": "Die Kraft",         "core": "Sanfte Stärke, Umgang mit den eigenen Trieben."},
    {"name": "Der Eremit",        "core": "Rückzug, Selbstkenntnis, innerer Kompass."},
    {"name": "Das Rad des Schicksals", "core": "Glückswelle und Wendepunkt — bleibe handlungsfähig."},
    {"name": "Gerechtigkeit",     "core": "Klares Urteil, Wahrheit, Konsequenz."},
    {"name": "Der Gehängte",      "core": "Perspektivwechsel, Hingabe, Warten."},
    {"name": "Der Tod",           "core": "Ende und Wandlung, damit Neues entstehen kann."},
    {"name": "Die Mäßigkeit",     "core": "Balance, Geduld, Verschmelzung der Gegensätze."},
    {"name": "Der Teufel",        "core": "Abhängigkeit, Schatten, ungelöste Bindung."},
    {"name": "Der Turm",          "core": "Schock, Befreiung durch Zusammenbruch des Illusorischen."},
    {"name": "Der Stern",         "core": "Hoffnung, Inspiration, Heilung."},
    {"name": "Der Mond",          "core": "Unbewusstes, Träume, Unsicherheit."},
    {"name": "Die Sonne",         "core": "Lebensfreude, Klarheit, sichtbarer Erfolg."},
    {"name": "Das Gericht",       "core": "Ruf, Berufung, bewusste Entscheidung."},
    {"name": "Die Welt",          "core": "Abschluss, Ganzheit, neue Ebene."},
]

def _det_hash(*parts: Any) -> int:
    """Deterministic non-cryptographic 32-bit hash for card draws and cache keys.
    Uses Python's string hashing via a stable digest so the result does not
    depend on PYTHONHASHSEED."""
    import hashlib
    h = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(h[:8], 16)

def tarot_draw(bdate: dt.date, period: str = "day", seed: Optional[int] = None,
               ref: Optional[dt.date] = None) -> Dict[str, Any]:
    """Deterministically draw one Major Arcana card.

    The draw is stable across calls with identical inputs and changes with
    the period bucket (today / ISO week / year-month) so a "Heute" reading
    gets a different card than a "Monat" reading.
    """
    ref = ref or dt.date.today()
    bucket = _period_bucket(period, ref)
    idx = _det_hash(bdate.isoformat(), period, bucket, seed if seed is not None else "") % len(TAROT_MAJOR)
    card = TAROT_MAJOR[idx]
    return {"index": idx, "name": card["name"], "core": card["core"]}

def _period_bucket(period: str, ref: Optional[dt.date] = None) -> str:
    """Stable cache bucket for a period:
    - day   → ISO date string (changes daily)
    - week  → ISO year-week string (changes weekly)
    - month → YYYY-MM (changes monthly)"""
    ref = ref or dt.date.today()
    p = (period or "day").lower()
    if p == "week":
        iso_year, iso_week, _ = ref.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if p == "month":
        return f"{ref.year}-{ref.month:02d}"
    return ref.isoformat()

def celtic_tree(d:dt.date)->str:
    ranges=[("Birke",(12,24),(1,20)),("Eberesche",(1,21),(2,17)),("Esche",(2,18),(3,17)),("Erle",(3,18),(4,14)),("Weide",(4,15),(5,12)),
            ("Weißdorn",(5,13),(6,9)),("Eiche",(6,10),(7,7)),("Stechpalme",(7,8),(8,4)),("Hasel",(8,5),(9,1)),("Weinrebe",(9,2),(9,29)),
            ("Efeu",(9,30),(10,27)),("Schilfrohr",(10,28),(11,24)),("Holunder",(11,25),(12,23))]
    y=d.year; md=lambda m,dd: dt.date(y,m,dd)
    for name,(m1,d1),(m2,d2) in ranges:
        s,e=md(m1,d1),md(m2,d2)
        if (s<=e and s<=d<=e) or (s>e and (d>=s or d<=e)): return name
    return "Birke"

async def geocode(place: str) -> Optional[Dict[str, Any]]:
    """Resolve a free-text birthplace to coordinates via Nominatim.

    Strategy (two-pass):
      1. DACH-first — restrict to countrycodes=de,at,ch so that common German
         town names (Neustadt, Stuttgart-Weilimdorf, Bad Saulgau, …) don't
         collide with homonyms in the US or elsewhere.
      2. If that yields nothing, retry worldwide so international users and
         less common place names still work.

    Returns a dict with lat, lon, display (canonical label) and
    countryCode, or None if the place couldn't be resolved.
    """
    if not place:
        return None
    headers = {
        "User-Agent": "horoskop.one/1.0 (contact: kontakt@horoskop.one)",
        "Accept-Language": "de,en",
    }
    base_params = {
        "format": "jsonv2",
        "limit": "5",
        "addressdetails": "1",
        "q": place.strip(),
    }

    def _pick(data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not data:
            return None
        # Prefer administrative / populated-place hits over e.g. shops, bus stops.
        preferred_classes = {"place", "boundary"}
        ordered = sorted(
            data,
            key=lambda d: (0 if d.get("class") in preferred_classes else 1,
                           -float(d.get("importance") or 0)),
        )
        hit = ordered[0]
        addr = hit.get("address") or {}
        return {
            "lat": float(hit["lat"]),
            "lon": float(hit["lon"]),
            "display": hit.get("display_name") or place,
            "countryCode": (addr.get("country_code") or "").upper() or None,
        }

    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            # Pass 1: DACH only
            r = await cli.get(
                "https://nominatim.openstreetmap.org/search",
                params={**base_params, "countrycodes": "de,at,ch"},
                headers=headers,
            )
            if r.status_code == 200:
                hit = _pick(r.json() or [])
                if hit:
                    return hit
            # Pass 2: worldwide fallback
            r = await cli.get(
                "https://nominatim.openstreetmap.org/search",
                params=base_params,
                headers=headers,
            )
            if r.status_code != 200:
                return None
            return _pick(r.json() or [])
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None

def find_timezone(lat:Optional[float], lon:Optional[float])->str:
    if lat is None or lon is None: return "Europe/Berlin"
    try:
        tz=tf.timezone_at(lat=lat,lng=lon); return tz or "Europe/Berlin"
    except (ValueError, TypeError):
        return "Europe/Berlin"

def now_local(d:dt.date, tzname:str)->dt.datetime:
    return dt.datetime(d.year,d.month,d.day,12,0,tzinfo=ZoneInfo(tzname))

try:
    import swisseph as swe
    HAS_SWE=True
except Exception:
    HAS_SWE=False

ZOD_SIGNS=["Widder","Stier","Zwillinge","Krebs","Löwe","Jungfrau","Waage","Skorpion","Schütze","Steinbock","Wassermann","Fische"]
def sign_from_deg(lon_deg:float)->str: return ZOD_SIGNS[int((lon_deg%360.0)//30)]

def swe_compute(bdate:dt.date,btime:Optional[dt.time],lat:Optional[float],lon:Optional[float],tzname:str,house_sys:Optional[str]=None):
    if not (HAS_SWE and btime and lat is not None and lon is not None): return None
    house_sys=(house_sys or os.getenv("HOUSE_SYSTEM","P")).strip()[:1] or "P"
    loc=dt.datetime.combine(bdate,btime).replace(tzinfo=ZoneInfo(tzname)); ut=loc.astimezone(dt.timezone.utc)
    jd=swe.julday(ut.year,ut.month,ut.day,ut.hour+ut.minute/60+ut.second/3600)
    raw_cusps,ascmc=swe.houses(jd,lat,lon,house_sys.encode()); asc,mc=ascmc[0],ascmc[1]
    # pyswisseph 2.x gibt 12 Cusps zurück, ältere Bindings 13 (Index 0 unbenutzt).
    cusps = [raw_cusps[i] for i in range(1, 13)] if len(raw_cusps) >= 13 else list(raw_cusps[:12])
    planets={"Sonne":swe.SUN,"Mond":swe.MOON,"Merkur":swe.MERCURY,"Venus":swe.VENUS,"Mars":swe.MARS,"Jupiter":swe.JUPITER,"Saturn":swe.SATURN,
             "Uranus":swe.URANUS,"Neptun":swe.NEPTUNE,"Pluto":swe.PLUTO}
    pos={}
    for name,code in planets.items():
        lonlat,_=swe.calc_ut(jd,code,swe.FLG_SWIEPH); pos[name]={"lon":lonlat[0],"sign":sign_from_deg(lonlat[0])}
    def house_of(L):
        L=L%360.0
        for i in range(12):
            a=cusps[i]%360.0; b=cusps[(i+1)%12]%360.0
            if (a<=b and a<=L<b) or (a>b and (L>=a or L<b)): return i+1
        return None
    return {
        "houseSystem":house_sys,
        "ascendant":{"deg":asc,"sign":sign_from_deg(asc)},
        "mc":{"deg":mc,"sign":sign_from_deg(mc)},
        "cusps":list(cusps),
        "planets":pos,
        "sunHouse":house_of(pos["Sonne"]["lon"]),
        "moonHouse":house_of(pos["Mond"]["lon"]),
        "utc":ut.isoformat()
    }

def _chat_kwargs(model: str, temperature: float, seed: Optional[int] = None) -> Dict[str, Any]:
    """Modellbewusste Parameter für chat.completions.

    Die GPT-5-/o-Reasoning-Familie akzeptiert nur die Default-Temperatur und
    ignoriert/verweigert `seed`; ein gesetzter `temperature`-Wert führt dort
    zu einem 400-Fehler ("Unsupported value") — genau das ließ alle Readings
    still auf den Fallback-Text zurückfallen. Für diese Modelle senden wir
    stattdessen `reasoning_effort` (Default: low; per OPENAI_REASONING_EFFORT
    übersteuerbar). "minimal" erzeugte erfundene Wörter („zuprinzig") in den
    deutschen Texten — die eine Stufe mehr Denken kostet bei Kurztexten kaum
    etwas und hält die Prosa sauber.
    """
    kwargs: Dict[str, Any] = {"model": model}
    if model.startswith(("gpt-5", "o1", "o3", "o4")):
        kwargs["reasoning_effort"] = os.getenv("OPENAI_REASONING_EFFORT", "low")
    else:
        kwargs["temperature"] = temperature
        if seed is not None:
            kwargs["seed"] = seed
    return kwargs

_LLM_DEFAULT_SYSTEM = ("Du bist ein klarer, sachlicher und freundlicher Schreibassistent. "
                       "Du schreibst verständlich, konkret und alltagsnah — ohne Esoterik, "
                       "ohne Pathos, ohne blumige Metaphern. "
                       "Du schreibst fehlerfreies, natürliches Deutsch und verwendest "
                       "ausschließlich existierende deutsche Wörter — keine "
                       "Wortneuschöpfungen, keine erfundenen Adjektive, keine gestelzten "
                       "Komposita. Im Zweifel wähle das einfache, gebräuchliche Wort.")

def _anthropic_text(system: str, user: str) -> str:
    """Ein Text-Call gegen die Anthropic Messages API.

    Claude Sonnet 5 lehnt Nicht-Default-Sampling-Parameter ab und denkt
    standardmäßig adaptiv; für kurze Deutungstexte reicht effort=low
    (schnell, günstig) — per ANTHROPIC_EFFORT übersteuerbar. max_tokens
    deckt Denken + Antwort gemeinsam ab, daher großzügig.
    """
    resp = _anthropic_client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        output_config={"effort": os.getenv("ANTHROPIC_EFFORT", "low")},
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), None)
    if text is None:
        raise RuntimeError(f"Anthropic-Antwort ohne Text (stop_reason={resp.stop_reason})")
    return text

def llm_text(system: str, user: str, temperature: float = 0.8,
             seed: Optional[int] = None, provider: Optional[str] = None) -> str:
    """Provider-neutraler Text-Call. `provider` übersteuert LLM_PROVIDER
    (genutzt vom /compare-Blindtest)."""
    p = (provider or LLM_PROVIDER)
    if p == "anthropic":
        if _anthropic_client is None:
            raise RuntimeError("Anthropic nicht konfiguriert (ANTHROPIC_API_KEY fehlt)")
        return _anthropic_text(system, user)
    kwargs = dict(_chat_kwargs(MODEL, temperature, seed), messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])
    return client.chat.completions.create(**kwargs).choices[0].message.content

def oa_text(prompt:str, seed:Optional[int]=None, temperature:float=0.8)->str:
    return llm_text(_LLM_DEFAULT_SYSTEM, prompt, temperature, seed)

def try_load_json(maybe:str)->Any:
    m=re.search(r"```json([\s\S]*?)```", maybe)
    if m:
        try: return json.loads(m.group(1))
        except json.JSONDecodeError: pass
    m=re.search(r"\{[\s\S]*\}$", maybe.strip())
    if m:
        try: return json.loads(m.group(0))
        except json.JSONDecodeError: pass
    try: return json.loads(maybe)
    except json.JSONDecodeError: return {"raw": maybe}

# ---------------------------------------------------------------------------
# Deep-Reading Types – 7 specialized prompts inspired by life-path coaching
# + 1 "classic" (the original 4-section reading)
# ---------------------------------------------------------------------------

DEEP_READING_TYPES = {
    "classic": {
        "label": "Klassisches Reading",
        "desc": "Fokus, Beruf, Liebe & Energie – dein Tages-/Wochen-/Monatshoroskop.",
    },
    "blueprint": {
        "label": "Lebensplan-Decoder",
        "desc": "Persönlichkeitsmerkmale, verborgene Stärken, Schwächen und Lebensaufgabe.",
    },
    "soul_purpose": {
        "label": "Seelenaufgabe",
        "desc": "Kernmission, Lektionen und dein Beitrag für die Welt – mit Alltagsimpulsen.",
    },
    "career": {
        "label": "Berufung & Karriere",
        "desc": "3 ideale Karrierepfade, natürliche Talente und ein Feld, das du meiden solltest.",
    },
    "relationship": {
        "label": "Beziehungs-Landkarte",
        "desc": "Kompatibilität, Liebeslektionen und das Bild deines idealen Partners.",
    },
    "wealth": {
        "label": "Fülle & Wohlstand",
        "desc": "Geld-Persönlichkeit, Blockaden und deine individuelle Wohlstandsstrategie.",
    },
    "timeline": {
        "label": "Zukunfts-Zeitstrahl",
        "desc": "Wendepunkte, Wachstumsphasen und deine 5-Jahres-Roadmap.",
    },
    "genius": {
        "label": "Inneres Genie",
        "desc": "Dein einzigartiges Talent und eine 3-Schritte-Routine, um es zu entfalten.",
    },
}

# ---------------------------------------------------------------------------
# Tone & Mixer directives — these turn the UI Kosmischer Mixer into actual
# prompt signals, so slider positions and tone mode really influence the
# generated reading (instead of being ignored).
# ---------------------------------------------------------------------------

# Labels shown in the response for each mixer key.
_MIXER_LABELS: Dict[str, str] = {
    "astro": "Astrologie / Transite",
    "num":   "Numerologie",
    "tarot": "Tarot-Archetypen",
    "iching": "I-Ging",
    "cn":    "Chinesisches Tierkreiszeichen",
    "tree":  "Keltischer Baumkreis",
}

_TONE_DIRECTIVES: Dict[str, str] = {
    "mystic_coach": (
        "Schreibe in einer ausbalancierten Stimme: warm, achtsam, zugleich klar "
        "und handlungsorientiert. Eine Prise Mystik ist erlaubt, darf aber nie "
        "die Konkretheit überlagern. Nutze ruhige Bilder, bleib aber alltagsnah."
    ),
    "mystisch": (
        "Schreibe in einer poetisch-mystischen Stimme: Bilder aus Natur, Mond, "
        "Jahreszeiten und Archetypen sind willkommen. Bleibe trotzdem verständlich, "
        "gib am Ende jedes Abschnitts einen greifbaren Impuls."
    ),
    "coach": (
        "Schreibe wie ein pragmatischer Coach: klar, direkt, umsetzbar. "
        "Keine Esoterik, keine Metaphern. Jede Aussage mündet in einen "
        "konkreten, überprüfbaren nächsten Schritt."
    ),
    "skeptisch": (
        "Schreibe aus einer reflektiert-skeptischen Perspektive: die Symbole "
        "werden als archetypische Bilder interpretiert (nicht als Vorhersage). "
        "Rationaler Ton, Psychologie statt Prophetie, viele 'vielleicht', "
        "'eine Möglichkeit wäre', 'Einladung zur Selbstreflexion'."
    ),
}

# Mapping tone → human-readable label for the frontend meta.
_TONE_LABELS: Dict[str, str] = {
    "mystic_coach": "Mystic Coach (balanciert)",
    "mystisch":     "Mystisch",
    "coach":        "Coach (rational)",
    "skeptisch":    "Skeptisch / reflektiert",
    # Legacy keys (older clients).
    "mystic_deep":  "Mystic Coach (balanciert)",
}

def _tone_directive(tone: Optional[str]) -> str:
    """Return a short system-prompt-sized stylistic instruction for the tone."""
    key = (tone or "mystic_coach").strip().lower()
    return _TONE_DIRECTIVES.get(key) or _TONE_DIRECTIVES["mystic_coach"]

def _normalize_mixer(raw: Optional[Dict[str, Any]]) -> Dict[str, int]:
    """Clamp negative values, coerce to int, rescale so the total equals 100.

    If the input is empty or all-zero, return a balanced default.
    """
    default = {"astro": 34, "num": 13, "tarot": 17, "iching": 14, "cn": 11, "tree": 11}
    if not raw:
        return default
    cleaned: Dict[str, int] = {}
    for k in _MIXER_LABELS.keys():
        try:
            v = int(round(float(raw.get(k, 0))))
        except (TypeError, ValueError):
            v = 0
        cleaned[k] = max(0, v)
    total = sum(cleaned.values())
    if total <= 0:
        return default
    # Rescale to exactly 100 using largest-remainder so rounding errors don't drift.
    scaled = {k: (v * 100) / total for k, v in cleaned.items()}
    floored = {k: int(v) for k, v in scaled.items()}
    diff = 100 - sum(floored.values())
    # Distribute the remainder to the keys with the largest fractional parts.
    order = sorted(scaled.items(), key=lambda kv: kv[1] - int(kv[1]), reverse=True)
    i = 0
    while diff > 0 and order:
        floored[order[i % len(order)][0]] += 1
        diff -= 1
        i += 1
    return floored

def _mixer_directive(mixer: Dict[str, int]) -> str:
    """Render the normalized mixer as a structured prompt block.

    The LLM sees an ordered list of traditions by weight and an explicit
    instruction on how to let the weights colour the text.
    """
    ordered = sorted(mixer.items(), key=lambda kv: kv[1], reverse=True)
    lines = [f"- {_MIXER_LABELS[k]}: {v}%" for k, v in ordered if v > 0]
    if not lines:
        return ""
    lead = _MIXER_LABELS[ordered[0][0]]
    return (
        "Gewichtung der Traditionen (Kosmischer Mixer):\n"
        + "\n".join(lines)
        + f"\n\nInstruktion: Baue die Deutung sichtbar um die am stärksten gewichtete "
        f"Tradition (**{lead}**). Niedrig gewichtete Traditionen dürfen nur als "
        f"kurze Randbemerkung erscheinen oder ganz weggelassen werden. "
        f"Stimme deine Bildsprache, Fachbegriffe und Beispiele an die Gewichte an."
    )

def _deep_system_prompt(rtype: str) -> str:
    """Return the system prompt for a given reading type."""
    base = (
        "Du bist ein sachlicher, klarer Lebensberater. "
        "Du verbindest Psychologie, Astrologie, Numerologie und Archetypen. "
        "Deine Sprache ist klar, direkt, freundlich und alltagsnah — ohne Esoterik, ohne Pathos, ohne blumige Metaphern. "
        "Du gibst immer konkrete, umsetzbare Impulse. "
        "Antworte immer auf Deutsch."
    )
    specifics = {
        "blueprint": (
            "Du bist ein Lebensplan-Analyst. Analysiere den Menschen anhand von Psychologie, "
            "Numerologie und Lebensmuster-Mapping. Benenne konkrete Persönlichkeitsmerkmale, "
            "Stärken, Schwächen und die zentrale Lebensaufgabe. "
            "Schreibe direkt und ehrlich — keine Floskeln, keine esoterische Sprache."
        ),
        "soul_purpose": (
            "Du bist ein Lebensaufgaben-Berater. Beschreibe die Kernaufgabe im Leben, "
            "die Lektionen die anstehen und den konkreten Beitrag, den diese Person leisten kann. "
            "Gib klare, umsetzbare Ratschläge für den Alltag — sachlich und ohne Esoterik."
        ),
        "career": (
            "Du bist ein Karriereberater. Analysiere natürliche Talente, "
            "Entscheidungsstil und Antriebe anhand der Daten. "
            "Nenne 3 konkrete Karriere- oder Geschäftspfade die passen würden, "
            "und ein Feld das eher gemieden werden sollte. Schreibe sachlich und direkt."
        ),
        "relationship": (
            "Du bist ein Beziehungsberater. Beschreibe, welche Art von Menschen "
            "gut kompatibel sind, welche Lektionen in Beziehungen anstehen, "
            "und worauf bei der Partnerwahl geachtet werden sollte. "
            "Schreibe klar und nüchtern — keine romantische Verklärung."
        ),
        "wealth": (
            "Du bist ein Finanz-Coach. Beschreibe die natürliche Geld-Persönlichkeit, "
            "typische Fehler die finanzielles Wachstum bremsen, und eine konkrete Strategie "
            "die zur Person passt. Sachlich, direkt, ohne generische Tipps."
        ),
        "timeline": (
            "Du bist ein Zukunfts-Planer. Nutze das Geburtsdatum und die astrologischen Daten "
            "um Schlüssel-Wendepunkte zu beschreiben (Vergangenheit, Gegenwart, Zukunft), "
            "Wachstumsphasen und Herausforderungen, und einen konkreten 5-Jahres-Ausblick. "
            "Schreibe wie eine sachliche Roadmap — klar und greifbar."
        ),
        "genius": (
            "Du bist ein Talent-Berater. Identifiziere das besondere Talent oder die Fähigkeit, "
            "die diese Person auszeichnet. "
            "Gib dann eine praktische 3-Schritte-Tagesroutine, um dieses Talent gezielt zu entwickeln. "
            "Schreibe sachlich, konkret, ohne Übertreibung."
        ),
    }
    return base + "\n\n" + specifics.get(rtype, "")

def _deep_user_prompt(rtype: str, ctx: Dict[str, Any]) -> str:
    """Build the user prompt for a deep reading, incorporating all astrological context."""
    # Shared context block used by all reading types
    context_block = f"""
Geburtsdaten:
- Datum: {ctx['bdate_str']} · Tagesabschnitt: {ctx['dpart']}
- Ort: {ctx['place']} (lat={ctx['lat']}, lon={ctx['lon']}, Zeitzone={ctx['tzname']})
- Saison / Hemisphäre: {ctx['season']} / {ctx['hemisphere']}

Astrologisches Profil:
- Sternzeichen (Sonne): {ctx['sun_sign']}
- Mondphase: {ctx['moon']} (Zyklus: {ctx['moon_frac']:.1%})
{ctx['swe_line']}

Numerologie:
- Lebenszahl: {ctx['lifepath']} — {ctx.get('lifepath_arch','')}
- Geburtstagszahl: {ctx.get('bday_num','–')}
- Aktueller Zyklus: Persönliches Jahr {ctx.get('personal_year','–')} · Monat {ctx.get('personal_month','–')} · Tag {ctx.get('personal_day','–')}

Symbolische Karten:
- Chinesisches Tierzeichen: {ctx['cn_animal']} (Jahr {ctx['birth_year']})
- Keltischer Baum: {ctx['tree']}
- I-Ging Hexagramm {ctx['hex_idx']} — **{ctx.get('hex_name','')}**: {ctx.get('hex_core','')}
- Tarot (deterministisch gezogen): **{ctx.get('tarot_name','')}** — {ctx.get('tarot_core','')}
"""

    instructions = {
        "blueprint": f"""
{context_block}
Erstelle eine tiefgehende Lebensplan-Analyse als JSON:
{{
  "persoenlichkeit": "3-4 Sätze: Kernpersönlichkeit basierend auf Sternzeichen, Lebenszahl und chinesischem Zeichen",
  "staerken": "3-4 verborgene Stärken als Fließtext, poetisch aber klar",
  "schwaechen": "3-4 ehrliche Schwächen/Wachstumsfelder als Fließtext",
  "lebensaufgabe": "Die eine große Lebensaufgabe, 3-4 Sätze, tiefgründig und motivierend",
  "tagesimpuls": "Ein konkreter Impuls für heute (1-2 Sätze, Imperativ)"
}}
Leite alles spezifisch aus den Geburtsdaten ab. Keine generischen Phrasen.
""",
        "soul_purpose": f"""
{context_block}
Erstelle eine Seelenaufgaben-Analyse als JSON:
{{
  "kernmission": "3-4 Sätze: Die zentrale Lebensaufgabe der Seele",
  "lektionen": "3-4 Sätze: Die wichtigsten Lektionen, die zu lernen sind",
  "weltbeitrag": "3-4 Sätze: Der einzigartige Beitrag für die Welt",
  "alltagsausrichtung": "3 konkrete, sofort umsetzbare Schritte (als Fließtext), um ab heute das Leben auf die Seelenaufgabe auszurichten",
  "affirmation": "Ein kraftvoller Leitsatz (1 Satz)"
}}
Leite alles spezifisch aus den Geburtsdaten ab.
""",
        "career": f"""
{context_block}
Erstelle eine Berufungs-Analyse als JSON:
{{
  "talente": "3-4 Sätze: Natürliche Talente und Entscheidungsstil",
  "pfad_1": {{"titel": "Karrierepfad-Name", "beschreibung": "2-3 Sätze warum dieser Pfad ideal ist"}},
  "pfad_2": {{"titel": "Karrierepfad-Name", "beschreibung": "2-3 Sätze"}},
  "pfad_3": {{"titel": "Karrierepfad-Name", "beschreibung": "2-3 Sätze"}},
  "meiden": {{"feld": "Berufsfeld-Name", "grund": "2-3 Sätze warum dieses Feld gemieden werden sollte"}},
  "naechster_schritt": "Ein konkreter Schritt für diese Woche (1-2 Sätze)"
}}
Leite Talente und Pfade spezifisch aus Sternzeichen, Lebenszahl und chinesischem Zeichen ab.
""",
        "relationship": f"""
{context_block}
Erstelle eine Beziehungs-Analyse als JSON:
{{
  "liebesstil": "3-4 Sätze: Wie diese Person liebt und geliebt werden möchte",
  "kompatibilitaet": "3-4 Sätze: Welche Sternzeichen/Typen am besten passen und warum",
  "liebeslektionen": "3-4 Sätze: Die wichtigsten Beziehungslektionen",
  "idealer_partner": "3-4 Sätze: Exakte Beschreibung des Partners, der zum höchsten Selbst führt",
  "beziehungsimpuls": "Ein konkreter Impuls für die Partnerschaft oder Partnersuche (1-2 Sätze)"
}}
Leite alles aus dem astrologischen Profil ab, besonders Venus-bezogene Aspekte und Mondphase.
""",
        "wealth": f"""
{context_block}
Erstelle eine Wohlstands-Analyse als JSON:
{{
  "geld_persoenlichkeit": "3-4 Sätze: Die natürliche Beziehung zu Geld und Ressourcen",
  "blockaden": "3-4 Sätze: Welche Muster und Fehler finanzielles Wachstum blockieren",
  "wohlstandsstrategie": "3-4 Sätze: Die individuelle Strategie zur Fülle, die zum wahren Selbst passt",
  "chancen_zeitfenster": "2-3 Sätze: Aktuelle kosmische Chancen-Fenster für Wohlstand",
  "geld_ritual": "Ein konkretes tägliches Ritual für Fülle-Bewusstsein (1-2 Sätze)"
}}
Keine generischen Finanztipps. Aus dem astrologischen Profil ableiten.
Hinweis: Dies ist keine Finanzberatung, sondern achtsame Selbstreflexion.
""",
        "timeline": f"""
{context_block}
Erstelle einen Zukunfts-Zeitstrahl als JSON:
{{
  "vergangene_phase": "3-4 Sätze: Die prägendste Phase der Vergangenheit und was sie gelehrt hat",
  "aktuelle_phase": "3-4 Sätze: Wo die Person gerade steht und welche Energie gerade wirkt",
  "wendepunkt": "2-3 Sätze: Der nächste große Wendepunkt (wann und warum)",
  "jahr_1_2": "3-4 Sätze: Die nächsten 1-2 Jahre – Fokus, Chancen, Herausforderungen",
  "jahr_3_5": "3-4 Sätze: Jahre 3-5 – wohin die Reise geht, Transformation",
  "vision": "Ein kraftvolles Zukunftsbild (2-3 Sätze, poetisch und konkret)"
}}
Nutze Saturn-Zyklen, Lebenszahl-Phasen und I-Ging für die Zeitstruktur.
""",
        "genius": f"""
{context_block}
Erstelle eine Inneres-Genie-Analyse als JSON:
{{
  "einzigartiges_talent": "3-4 Sätze: Das eine Talent oder die eine Fähigkeit, die diese Person von 99% der Menschen abhebt",
  "warum_dieses_talent": "2-3 Sätze: Warum gerade dieses Talent im astrologischen Profil verankert ist",
  "schritt_1": {{"titel": "Morgenroutine-Titel", "beschreibung": "2-3 Sätze: Konkreter erster Tagesschritt"}},
  "schritt_2": {{"titel": "Tagesübung-Titel", "beschreibung": "2-3 Sätze: Konkreter zweiter Schritt"}},
  "schritt_3": {{"titel": "Abendritual-Titel", "beschreibung": "2-3 Sätze: Konkreter dritter Schritt"}},
  "meisterschafts_vision": "2-3 Sätze: Wie sich Meisterschaft und Anerkennung entfalten werden"
}}
Leite das Talent spezifisch aus Sternzeichen + Lebenszahl + chinesischem Zeichen ab.
""",
    }
    return instructions.get(rtype, "")

def _deep_section_map() -> Dict[str, List[Dict[str, str]]]:
    """Map reading types to their section definitions (title + JSON key)."""
    return {
        "blueprint": [
            {"key": "persoenlichkeit", "title": "Deine Persönlichkeit"},
            {"key": "staerken", "title": "Verborgene Stärken"},
            {"key": "schwaechen", "title": "Wachstumsfelder"},
            {"key": "lebensaufgabe", "title": "Deine Lebensaufgabe"},
            {"key": "tagesimpuls", "title": "Impuls für heute"},
        ],
        "soul_purpose": [
            {"key": "kernmission", "title": "Deine Kernmission"},
            {"key": "lektionen", "title": "Deine Lektionen"},
            {"key": "weltbeitrag", "title": "Dein Beitrag für die Welt"},
            {"key": "alltagsausrichtung", "title": "Ausrichtung im Alltag"},
            {"key": "affirmation", "title": "Dein Leitsatz"},
        ],
        "career": [
            {"key": "talente", "title": "Deine natürlichen Talente"},
            {"key": "pfad_1", "title": "Karrierepfad 1", "nested": True},
            {"key": "pfad_2", "title": "Karrierepfad 2", "nested": True},
            {"key": "pfad_3", "title": "Karrierepfad 3", "nested": True},
            {"key": "meiden", "title": "Dieses Feld meiden", "nested": True},
            {"key": "naechster_schritt", "title": "Dein nächster Schritt"},
        ],
        "relationship": [
            {"key": "liebesstil", "title": "Dein Liebesstil"},
            {"key": "kompatibilitaet", "title": "Kompatibilität"},
            {"key": "liebeslektionen", "title": "Deine Liebeslektionen"},
            {"key": "idealer_partner", "title": "Dein idealer Partner"},
            {"key": "beziehungsimpuls", "title": "Impuls für deine Beziehung"},
        ],
        "wealth": [
            {"key": "geld_persoenlichkeit", "title": "Deine Geld-Persönlichkeit"},
            {"key": "blockaden", "title": "Deine Blockaden"},
            {"key": "wohlstandsstrategie", "title": "Deine Wohlstandsstrategie"},
            {"key": "chancen_zeitfenster", "title": "Kosmisches Chancen-Fenster"},
            {"key": "geld_ritual", "title": "Dein Fülle-Ritual"},
        ],
        "timeline": [
            {"key": "vergangene_phase", "title": "Deine Vergangenheit"},
            {"key": "aktuelle_phase", "title": "Wo du jetzt stehst"},
            {"key": "wendepunkt", "title": "Der nächste Wendepunkt"},
            {"key": "jahr_1_2", "title": "Die nächsten 1–2 Jahre"},
            {"key": "jahr_3_5", "title": "Jahre 3–5: Deine Transformation"},
            {"key": "vision", "title": "Deine Vision"},
        ],
        "genius": [
            {"key": "einzigartiges_talent", "title": "Dein einzigartiges Talent"},
            {"key": "warum_dieses_talent", "title": "Warum dieses Talent"},
            {"key": "schritt_1", "title": "Schritt 1: Morgenroutine", "nested": True},
            {"key": "schritt_2", "title": "Schritt 2: Tagesübung", "nested": True},
            {"key": "schritt_3", "title": "Schritt 3: Abendritual", "nested": True},
            {"key": "meisterschafts_vision", "title": "Deine Meisterschafts-Vision"},
        ],
    }

def _extract_sections(rtype: str, data: Dict[str, Any], why_chips: List[str]) -> List:
    """Convert the AI JSON response into Section objects based on reading type."""
    section_defs = _deep_section_map().get(rtype, [])
    sections = []
    for i, sdef in enumerate(section_defs):
        key = sdef["key"]
        title = sdef["title"]
        raw = data.get(key, "")
        if sdef.get("nested") and isinstance(raw, dict):
            t = raw.get("titel", raw.get("feld", ""))
            desc = raw.get("beschreibung", raw.get("grund", ""))
            text = f"**{t}** — {desc}" if t else str(desc)
        elif isinstance(raw, dict):
            text = json.dumps(raw, ensure_ascii=False)
        else:
            text = str(raw).strip()
        chips_for = [why_chips[min(i, len(why_chips) - 1)]] if why_chips else []
        sections.append({"title": title, "text": text, "chips": chips_for})
    return sections

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

VALID_READING_TYPES = list(DEEP_READING_TYPES.keys())

class ReadingRequest(BaseModel):
    # max_length bounds keep oversized free-text fields (which get embedded
    # directly into the OpenAI prompt) from amplifying per-request cost —
    # the rate limiter caps call *count*, not payload size.
    birthDate: str = Field(..., max_length=32)
    birthPlace: str = Field(..., max_length=200)
    birthTime: Optional[str] = Field(None, max_length=16)
    approxDaypart: Optional[str] = Field(None, max_length=32)
    period: str = Field("day", max_length=16, description="day|week|month")
    tone: str = Field("mystic_deep", max_length=64)
    readingType: str = Field("classic", max_length=64, description="classic|blueprint|soul_purpose|career|relationship|wealth|timeline|genius")
    seed: Optional[int] = None
    mixer: Optional[Dict[str, float]] = None
    coords: Optional[Dict[str, float]] = None

class Section(BaseModel):
    title: str
    text: str
    chips: List[str] = []

class ReadingResponse(BaseModel):
    meta: Dict[str, Any]
    sections: List[Section]
    chips: List[str] = []
    disclaimer: str

@app.get("/health")
@app.get("/healthz")
def health(): return {"ok": True, "provider": LLM_PROVIDER, "model": _llm_id()}

@app.get("/reading-types")
def reading_types():
    """Return available reading types for the frontend."""
    return [{"id": k, **v} for k, v in DEEP_READING_TYPES.items()]

# ---------------------------------------------------------------------------
# Response cache — simple in-memory TTL cache keyed by the full input set.
#
# The cache intentionally buckets by period (today / iso-week / year-month)
# so that two calls with identical inputs within the same bucket return the
# same reading instantly, while a new day/week/month produces a fresh one.
# This cuts Railway + OpenAI cost dramatically for users who click through
# Heute → Woche → Monat or refresh the page repeatedly.
# ---------------------------------------------------------------------------
import time

_READING_CACHE: Dict[str, tuple] = {}
_READING_CACHE_TTL = int(os.getenv("READING_CACHE_TTL", "86400"))  # 24 h default
_READING_CACHE_MAX = int(os.getenv("READING_CACHE_MAX", "512"))

def _cache_key(req: "ReadingRequest") -> str:
    mixer_items = tuple(sorted((req.mixer or {}).items()))
    return "|".join([
        (req.birthDate or "").strip(),
        (req.birthPlace or "").strip().lower(),
        (req.birthTime or "").strip(),
        (req.approxDaypart or "").strip().lower(),
        (req.period or "day").strip().lower(),
        (req.tone or "").strip().lower(),
        (req.readingType or "classic").strip().lower(),
        str(req.seed or ""),
        repr(mixer_items),
        _period_bucket(req.period),
        _llm_id(),  # Provider-Wechsel darf keine gecachten Fremdtexte liefern
    ])

def _cache_get(key: str):
    entry = _READING_CACHE.get(key)
    if not entry:
        return None
    ts, resp = entry
    if (time.time() - ts) > _READING_CACHE_TTL:
        _READING_CACHE.pop(key, None)
        return None
    return resp

def _cache_put(key: str, resp) -> None:
    # Evict oldest entry if we reach the cap.
    if len(_READING_CACHE) >= _READING_CACHE_MAX:
        oldest_key = min(_READING_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _READING_CACHE.pop(oldest_key, None)
    _READING_CACHE[key] = (time.time(), resp)


async def _reading_impl(req: ReadingRequest):
  try:
    # Cache short-circuit — identical inputs within the same period bucket
    # get the same response without hitting OpenAI or Nominatim.
    ckey = _cache_key(req)
    cached = _cache_get(ckey)
    if cached is not None:
        meta = dict(cached.meta)
        meta["cacheHit"] = True
        return ReadingResponse(meta=meta, sections=cached.sections, chips=cached.chips, disclaimer=cached.disclaimer)

    bdate=parse_birth_date(req.birthDate) or dt.date.today()
    btime=parse_birth_time(req.birthTime)
    dpart=(req.approxDaypart or daypart_from_time(btime)).lower()

    resolved_place = None
    country_code = None
    if req.coords and req.coords.get("lat") is not None and req.coords.get("lon") is not None:
        lat, lon = req.coords["lat"], req.coords["lon"]
    else:
        geo = await geocode(req.birthPlace)
        if geo:
            lat, lon = geo["lat"], geo["lon"]
            resolved_place = geo.get("display")
            country_code = geo.get("countryCode")
        else:
            lat, lon = None, None
    tzname=find_timezone(lat,lon); _=now_local(bdate,tzname)

    hemisphere="Nord" if (lat is None or lat>=0) else "Süd"
    season=season_from_date_hemisphere(bdate,lat)
    sun_sign=zodiac_from_date(bdate); cn_animal=chinese_animal(bdate.year)
    lifepath=life_path_number(bdate); tree=celtic_tree(bdate)
    hex_idx=iching_index(bdate); mf=moon_phase_fraction(bdate); moon=moon_phase_name(mf)

    # New in v6.1: proper I-Ging, extended numerology, deterministic tarot draw.
    today = dt.date.today()
    hex_info = iching_lookup(hex_idx)
    hex_name = hex_info.get("name", "")
    hex_core = hex_info.get("core", "")
    lifepath_arch = lifepath_archetype(lifepath)
    bday_num = birthday_number(bdate)
    personal_year = personal_year_number(bdate, today)
    personal_month = personal_month_number(bdate, today)
    personal_day = personal_day_number(bdate, today)
    tarot = tarot_draw(bdate, req.period, req.seed, today)

    swe_data=swe_compute(bdate,btime,lat,lon,tzname)

    active_mixer = _normalize_mixer(req.mixer)
    mixer_block = _mixer_directive(active_mixer)
    tone_block = _tone_directive(req.tone)
    mixer_list=[f"{k}:{v}%" for k,v in active_mixer.items()]
    why_chips=[f"Sternzeichen {sun_sign}", f"Ort {req.birthPlace or 'unbekannt'}",
               f"Saison: {season} ({hemisphere}-Halbkugel)", f"Mondphase: {moon}"]
    if swe_data:
        why_chips.insert(0, f"Aszendent {swe_data['ascendant']['sign']}")
        if swe_data.get("sunHouse"):  why_chips.append(f"Sonnenhaus {swe_data['sunHouse']}")
        if swe_data.get("moonHouse"): why_chips.append(f"Mondhaus {swe_data['moonHouse']}")

    swe_line=(f"Aszendent {swe_data['ascendant']['sign']}, MC {swe_data['mc']['sign']}, "
              f"Sonnenhaus {swe_data.get('sunHouse')}, Mondhaus {swe_data.get('moonHouse')}"
             ) if swe_data else "keine genaue Zeit/Ort ⇒ Aszendent & Häuser unbekannt"

    rtype = req.readingType if req.readingType in VALID_READING_TYPES else "classic"

    disclaimer="Unterhaltung & Selbstreflexion – kein Ersatz für professionelle Beratung. Krisen: 112 (EU)."

    meta={
        "period": req.period, "tone": req.tone,
        "toneLabel": _TONE_LABELS.get((req.tone or "").lower(), _TONE_LABELS["mystic_coach"]),
        "activeMixer": active_mixer,
        "mixerLabels": _MIXER_LABELS,
        "readingType": rtype,
        "readingLabel": DEEP_READING_TYPES[rtype]["label"],
        "birthDate": req.birthDate, "birthPlace": req.birthPlace, "birthTime": req.birthTime,
        "resolvedPlace": resolved_place, "countryCode": country_code,
        "approxDaypart": dpart, "geo": {"lat":lat,"lon":lon,"tz":tzname},
        "season": season, "hemisphere": "Nord" if (lat is None or lat>=0) else "Süd",
        "mini": {
            "sunSignApprox": sun_sign,
            "moonPhase": moon, "moonFrac": round(mf,3),
            "iChing": hex_idx,
            "iChingName": hex_name,
            "iChingCore": hex_core,
            "lifePath": lifepath,
            "lifePathArchetype": lifepath_arch,
            "birthdayNumber": bday_num,
            "personalYear": personal_year,
            "personalMonth": personal_month,
            "personalDay": personal_day,
            "chinese": cn_animal,
            "tree": tree,
            "tarot": tarot,
        },
        "swiss": swe_data,
    }

    # --- Classic reading (original 4-section flow) ---
    if rtype == "classic":
        outline_prompt=f"""
Du bist ein sachlicher, klarer Berater. Erstelle eine OUTLINE als JSON (keinen Fließtext).
Struktur:
{{
 "fokus": {{"kern":"...", "punkte":["...","...","..."]}},
 "beruf": {{"kern":"...", "punkte":["...","...","..."]}},
 "liebe": {{"kern":"...", "punkte":["...","...","..."]}},
 "energie": {{"kern":"...", "punkte":["...","...","..."]}}
}}

Rahmendaten:
- Zeitraum: {req.period}
- Ort: {resolved_place or req.birthPlace} → lat={lat}, lon={lon}, Zeitzone={tzname}
- Datum: {bdate.strftime('%d.%m.%Y')} · Tagesabschnitt: {dpart}
- Saison/Hemisphäre: {season} / {hemisphere}

Symbole der Traditionen (nutze nur, was laut Mixer hoch gewichtet ist):
- Astrologie: Sonne≈{sun_sign}, Mondphase {moon}, {swe_line}
- Numerologie: Lebenszahl {lifepath} ({lifepath_arch}); Persönliche Jahres-/Monats-/Tageszahl {personal_year}/{personal_month}/{personal_day}; Geburtstagszahl {bday_num}
- Tarot (deterministisch gezogen): **{tarot['name']}** — {tarot['core']}
- I-Ging: Hexagramm {hex_idx} — **{hex_name}**: {hex_core}
- Chinesisches Tierkreiszeichen: {cn_animal}
- Keltischer Baumkreis: {tree}

{mixer_block}

Ton-Vorgabe: {tone_block}

Regeln:
- Pro Bereich 3–4 Stichpunkte, direkt aus den Rahmendaten abgeleitet.
- Die Traditions-Gewichtung oben entscheidet, welche Symbolsprache dominiert.
  Nenne hoch gewichtete Symbole BEIM NAMEN (z. B. „Hexagramm 42 – Die Mehrung", „Der Eremit").
- Letzter Stichpunkt = ultra-kurze Mini-Aktion (imperativ, 1 Satz) ohne „Aktion:"-Prefix.
- Keine medizinisch/juristisch/finanziell heiklen Ratschläge.
"""
        try:
            outline_raw=oa_text(outline_prompt, seed=req.seed, temperature=0.4)
            outline=try_load_json(outline_raw)
        except Exception as e:
            outline={"fokus":{"kern":"","punkte":[]}, "error":str(e)}

        writing_prompt=f"""
Formuliere aus der OUTLINE ein Horoskop mit 3–4 Sätzen je Sektion.

Ton-Vorgabe: {tone_block}

Integriere die Mini-Aktion organisch in den Absatz. Keine Bullet-Listen.

{mixer_block}

Kontext (nur nutzen, nicht erneut aufzählen):
- Zeitraum: {req.period} · Ort: {resolved_place or req.birthPlace} (Zeitzone {tzname})
- Saison/Hemisphäre: {season} / {hemisphere}
- Sonne≈{sun_sign}, Mondphase {moon}, Tagesabschnitt {dpart}.
- Numerologie: Lebenszahl {lifepath} ({lifepath_arch}); Persönliche Jahreszahl {personal_year}, Monat {personal_month}, Tag {personal_day}.
- Tarot: **{tarot['name']}** — {tarot['core']}.
- I-Ging: Hexagramm {hex_idx} — **{hex_name}**: {hex_core}.
- Chinesisch {cn_animal}, Keltischer Baum {tree}.
- Swiss-Ephemeris: {swe_line}.

OUTLINE:
```json
{json.dumps(outline, ensure_ascii=False, indent=2)}
```
Gib nur JSON:
{{
 "fokus": "Absatz",
 "beruf": "Absatz",
 "liebe": "Absatz",
 "energie": "Absatz"
}}
"""
        try:
            longform_raw=oa_text(writing_prompt, seed=req.seed, temperature=0.8)
            data=try_load_json(longform_raw)
        except Exception as e:
            data={"fokus":"","beruf":"","liebe":"","energie":"","error":str(e)}

        # Distribute mixer chips across sections (#8): each section gets the
        # dominant tradition's chip plus one section-specific signal. The two
        # top traditions also appear on the header via the meta.activeMixer
        # rendering, so the user sees both a global and per-section view.
        sorted_mix = sorted(active_mixer.items(), key=lambda kv: kv[1], reverse=True)
        top1 = sorted_mix[0] if sorted_mix else None
        top2 = sorted_mix[1] if len(sorted_mix) > 1 else None
        top1_chip = f"{_MIXER_LABELS[top1[0]]} {top1[1]}%" if top1 and top1[1] > 0 else None
        top2_chip = f"{_MIXER_LABELS[top2[0]]} {top2[1]}%" if top2 and top2[1] > 0 else None

        def _sec_chips(base: List[str]) -> List[str]:
            return [c for c in base + [top1_chip] if c]

        sections=[
            Section(title="Fokus",  text=(data.get("fokus")  or "").strip(),
                    chips=_sec_chips([why_chips[0], why_chips[1], f"Saison: {season}"])),
            Section(title="Beruf",  text=(data.get("beruf")  or "").strip(),
                    chips=_sec_chips([f"Lebenszahl {lifepath}", f"P-Jahr {personal_year}"])),
            Section(title="Liebe",  text=(data.get("liebe")  or "").strip(),
                    chips=_sec_chips([f"Mondphase: {moon}", f"Tarot: {tarot['name']}"] + ([top2_chip] if top2_chip else []))),
            Section(title="Energie",text=(data.get("energie") or "").strip(),
                    chips=_sec_chips([f"Tag/Nacht: {dpart}", f"I-Ging: {hex_name}" if hex_name else ""])),
        ]
        resp = ReadingResponse(meta=meta, sections=sections, chips=why_chips, disclaimer=disclaimer)
        _cache_put(ckey, resp)
        return resp

    # --- Deep readings (7 specialized types) ---
    ctx = {
        "bdate_str": bdate.strftime('%d.%m.%Y'),
        "dpart": dpart,
        "place": req.birthPlace,
        "lat": lat, "lon": lon, "tzname": tzname,
        "season": season, "hemisphere": hemisphere,
        "sun_sign": sun_sign, "moon": moon, "moon_frac": mf,
        "lifepath": lifepath,
        "lifepath_arch": lifepath_arch,
        "personal_year": personal_year,
        "personal_month": personal_month,
        "personal_day": personal_day,
        "bday_num": bday_num,
        "cn_animal": cn_animal,
        "birth_year": bdate.year,
        "tree": tree,
        "hex_idx": hex_idx, "hex_name": hex_name, "hex_core": hex_core,
        "tarot_name": tarot["name"], "tarot_core": tarot["core"],
        "swe_line": (f"- Swiss-Ephemeris: {swe_line}" if swe_data
                     else "- (Keine exakte Geburtszeit → keine Häuser/Aszendent-Berechnung)"),
    }

    system_prompt = (_deep_system_prompt(rtype) + "\n\nTon-Vorgabe: " + tone_block
                     + "\n\nSprache: fehlerfreies, natürliches Deutsch; ausschließlich "
                       "existierende Wörter — keine Wortneuschöpfungen oder erfundenen "
                       "Adjektive. Im Zweifel das einfache, gebräuchliche Wort.")
    user_prompt = _deep_user_prompt(rtype, ctx)
    if mixer_block:
        user_prompt = mixer_block + "\n\n" + user_prompt

    try:
        raw = llm_text(system_prompt, user_prompt, temperature=0.7, seed=req.seed)
        data = try_load_json(raw)
    except Exception as e:
        print(f"deep reading LLM failed ({_llm_id()}): {e}")
        data = {"error": str(e)}

    sections = [Section(**s) for s in _extract_sections(rtype, data, why_chips)]

    # Add mixer + per-section enrichment chips so the UI shows which
    # tradition coloured each section (deep readings previously had only
    # a single generic chip per section).
    sorted_mix = sorted(active_mixer.items(), key=lambda kv: kv[1], reverse=True)
    top1 = sorted_mix[0] if sorted_mix else None
    top1_chip = f"{_MIXER_LABELS[top1[0]]} {top1[1]}%" if top1 and top1[1] > 0 else None
    extras = [why_chips[0] if why_chips else None, f"Mondphase: {moon}", f"P-Jahr {personal_year}"]
    if hex_name:
        extras.append(f"I-Ging: {hex_name}")
    if tarot.get("name"):
        extras.append(f"Tarot: {tarot['name']}")
    for i, s in enumerate(sections):
        # Avoid duplicating chips that already exist on the section.
        have = set(s.chips)
        add = [top1_chip] if top1_chip else []
        add.append(extras[i % len(extras)])
        for c in add:
            if c and c not in have:
                s.chips.append(c)
                have.add(c)

    resp = ReadingResponse(meta=meta, sections=sections, chips=why_chips, disclaimer=disclaimer)
    _cache_put(ckey, resp)
    return resp
  except Exception as exc:
    # Never return 500 — always give the frontend a usable response
    import traceback; traceback.print_exc()
    fallback_disclaimer="Unterhaltung & Selbstreflexion – kein Ersatz für professionelle Beratung."
    return ReadingResponse(
        meta={"error": str(exc), "readingType": getattr(req, 'readingType', 'classic')},
        sections=[Section(title="Fehler", text=f"Es ist ein Fehler aufgetreten: {exc}", chips=[])],
        chips=[], disclaimer=fallback_disclaimer,
    )

# Run: uvicorn main:app --host 0.0.0.0 --port 8080

# Öffentliche Routen mit optionalem Rate-Limiting. Slowapi erwartet ein
# `Request`-Argument im Endpoint — das reichen wir an die gemeinsame
# `_reading_impl`-Funktion weiter, ohne die Logik zu duplizieren.
if _HAS_SLOWAPI and limiter is not None:
    @app.post("/reading")
    @limiter.limit(READING_RATE_LIMIT)
    async def reading(request: Request, req: ReadingRequest = Body(...)):
        return await _reading_impl(req)

    @app.post("/readings", response_model=ReadingResponse)
    @limiter.limit(READING_RATE_LIMIT)
    async def readings_alias(request: Request, req: ReadingRequest = Body(...)):
        return await _reading_impl(req)
else:
    @app.post("/reading")
    async def reading(req: ReadingRequest = Body(...)):
        return await _reading_impl(req)

    @app.post("/readings", response_model=ReadingResponse)
    async def readings_alias(req: ReadingRequest = Body(...)):
        return await _reading_impl(req)


# ===========================================================================
# Das Monatsbrett — kalendergebundenes Senet-Orakelspiel (docs/spielkonzept.md)
#
# Alles Orakelhafte ist deterministisch und zustandslos: Tageslage, Wurf und
# Regelprüfung berechnet der Server aus (Datum, Geburtsprofil); die
# Steinpositionen hält in Phase 1 der Client (LocalStorage) und schickt sie
# zur Validierung mit.
# ===========================================================================

# --- Ganzhi (60er-Zyklus) — die Liubo-Referenz -----------------------------
# Anker: 27.01.2019 war ein Jiǎzǐ-Tag (Index 0), vgl.
# https://ytliu0.github.io/ChineseCalendar/sexagenary.html
_GANZHI_ANCHOR = dt.date(2019, 1, 27)
_STEMS = [("Jiǎ", "Holz"), ("Yǐ", "Holz"), ("Bǐng", "Feuer"), ("Dīng", "Feuer"),
          ("Wù", "Erde"), ("Jǐ", "Erde"), ("Gēng", "Metall"), ("Xīn", "Metall"),
          ("Rén", "Wasser"), ("Guǐ", "Wasser")]
_BRANCHES = [("Zǐ", "Ratte"), ("Chǒu", "Büffel"), ("Yín", "Tiger"), ("Mǎo", "Hase"),
             ("Chén", "Drache"), ("Sì", "Schlange"), ("Wǔ", "Pferd"), ("Wèi", "Ziege"),
             ("Shēn", "Affe"), ("Yǒu", "Hahn"), ("Xū", "Hund"), ("Hài", "Schwein")]

def ganzhi_day(d: dt.date) -> Dict[str, Any]:
    """Sexagesimales Tageszeichen (Stamm-Zweig) für ein Datum."""
    idx = (d - _GANZHI_ANCHOR).days % 60
    stem, element = _STEMS[idx % 10]
    branch, animal = _BRANCHES[idx % 12]
    return {"index": idx + 1, "pinyin": f"{stem}{branch.lower()}",
            "label": f"{element}-{animal}", "element": element, "animal": animal}

# --- Erklärungstexte für die Tageslage -------------------------------------
# Kurze, statische Deutungsbausteine — kein LLM nötig, keine Kosten. Die
# Systemtexte beantworten: Was ist das, woher kommt es, wofür taugt es?

_ELEMENT_TRAITS: Dict[str, str] = {
    "Holz": "Wachstum, Anfang, Beweglichkeit — gut für alles, was keimen soll",
    "Feuer": "Ausstrahlung, Begeisterung, Sichtbarkeit — gut für Auftritt und Ausdruck",
    "Erde": "Stabilität, Fürsorge, Verlässlichkeit — gut für Ordnen und Nähren",
    "Metall": "Klarheit, Präzision, Konsequenz — gut für Entscheidungen und Trennung von Unnötigem",
    "Wasser": "Tiefe, Intuition, Anpassung — gut für Zuhören, Forschen, Fließenlassen",
}
_ANIMAL_TRAITS: Dict[str, str] = {
    "Ratte": "wach, findig, vorausschauend", "Büffel": "geduldig, ausdauernd, tragfähig",
    "Tiger": "mutig, initiativ, leidenschaftlich", "Hase": "diplomatisch, feinfühlig, friedliebend",
    "Drache": "visionär, kraftvoll, großgesinnt", "Schlange": "weise, verschwiegen, analytisch",
    "Pferd": "freiheitsliebend, dynamisch, direkt", "Ziege": "kreativ, sanft, gemeinschaftlich",
    "Affe": "erfinderisch, verspielt, wendig", "Hahn": "genau, aufrichtig, pflichtbewusst",
    "Hund": "loyal, gerecht, beschützend", "Schwein": "großzügig, ehrlich, genussfähig",
}
_MOON_MEANINGS: Dict[str, str] = {
    "Neumond": "Stunde null des Zyklus: säen, wünschen, still beginnen.",
    "zunehmende Sichel": "Erste Energie kehrt zurück: kleine Schritte, zarte Anfänge.",
    "erstes Viertel": "Erste Hürde: dranbleiben, Entscheidungen treffen.",
    "zunehmender Mond": "Aufbauphase: Kraft sammeln, wachsen lassen, sichtbar werden.",
    "Vollmond": "Höhepunkt und Erntezeit: Klarheit, Fülle — und Gefühle in Großformat.",
    "abnehmender Mond": "Loslassphase: aussortieren, verdauen, weitergeben.",
    "letztes Viertel": "Bilanz: vergeben, abschließen, Ballast abwerfen.",
    "abnehmende Sichel": "Ausklang: ruhen, reflektieren, Raum für das Neue schaffen.",
}
_SYSTEM_INFO: Dict[str, Dict[str, str]] = {
    "moon": {
        "title": "Die Mondphase",
        "text": ("Der Mond durchläuft seinen Zyklus in rund 29,5 Tagen — er ist der älteste "
                 "Kalender der Menschheit. Fast alle Kulturen lasen in ihm denselben Rhythmus: "
                 "zunehmend = aufbauen, Vollmond = ernten, abnehmend = loslassen. "
                 "Das Monatsbrett übernimmt diesen Bogen als Spielfeld."),
        "link": "/methoden.html#mondphase",
    },
    "hexagram": {
        "title": "Das I-Ging-Hexagramm",
        "text": ("Das I Ging („Buch der Wandlungen“) ist ein rund 3000 Jahre alter chinesischer "
                 "Weisheits- und Orakeltext — einer der ältesten der Welt, kommentiert von "
                 "Konfuzius, geschätzt von C. G. Jung. Seine 64 Hexagramme beschreiben "
                 "Grundsituationen des Wandels; sie eignen sich weniger für Vorhersagen als für "
                 "die Frage: Welche Haltung passt zu diesem Moment?"),
        "link": "/methoden.html#i-ging",
    },
    "ganzhi": {
        "title": "Das Tageszeichen (Ganzhi)",
        "text": ("Der 60er-Zyklus aus zehn Himmelsstämmen (Elementen) und zwölf Erdzweigen "
                 "(Tierzeichen) zählt in China seit über 3000 Jahren die Tage — belegt schon auf "
                 "den Orakelknochen der Shang-Dynastie. Auch das antike Spiel Liubo war mit "
                 "diesem Kalender verwoben: Brett und Orakel waren dasselbe System. Jedes "
                 "Tageszeichen verbindet ein Element mit einem Tier zu einer Tagesqualität."),
        "link": "/methoden.html#chinesisch",
    },
    "field": {
        "title": "Das Senet-Feld",
        "text": ("Senet ist eines der ältesten Brettspiele der Welt (Ägypten, ab ca. 3000 "
                 "v. Chr.) — und zugleich ein religiöses Sinnbild: Die 30 Felder galten als "
                 "Stationen der Seelenreise, gespielt wurde symbolisch auch gegen das Schicksal. "
                 "Das Monatsbrett legt diese 30 Häuser auf die 30 Tage des Mondmonats; die "
                 "Sonderhäuser (Wiedergeburt, Wasser, die drei Schwellen) folgen dem "
                 "historischen Brett."),
        "link": "/methoden.html",
    },
}

def board_explanations(today: Dict[str, Any]) -> List[Dict[str, str]]:
    """Die vier Tageslage-Elemente mit Heute-Deutung + Hintergrund."""
    moon_name = today["moon"]["name"]
    gz = today["ganzhi"]
    return [
        {"key": "moon", "title": f"{_SYSTEM_INFO['moon']['title']}: {moon_name}",
         "heute": _MOON_MEANINGS.get(moon_name, ""),
         "hintergrund": _SYSTEM_INFO["moon"]["text"], "link": _SYSTEM_INFO["moon"]["link"]},
        {"key": "hexagram",
         "title": f"I-Ging {today['hexagram']['index']} — „{today['hexagram']['name']}“",
         "heute": today["hexagram"]["core"],
         "hintergrund": _SYSTEM_INFO["hexagram"]["text"], "link": _SYSTEM_INFO["hexagram"]["link"]},
        {"key": "ganzhi", "title": f"Tageszeichen {gz['label']} ({gz['pinyin']})",
         "heute": (f"{gz['element']}: {_ELEMENT_TRAITS.get(gz['element'], '')}. "
                   f"Der {gz['animal']} ist {_ANIMAL_TRAITS.get(gz['animal'], '')}."),
         "hintergrund": _SYSTEM_INFO["ganzhi"]["text"], "link": _SYSTEM_INFO["ganzhi"]["link"]},
        {"key": "field",
         "title": f"Feld {today['field']['index']} — {today['field']['name']}",
         "heute": today["field"]["core"],
         "hintergrund": _SYSTEM_INFO["field"]["text"], "link": _SYSTEM_INFO["field"]["link"]},
    ]

# --- Mondmonats-Brett ------------------------------------------------------
_SYNODIC = 29.53058867

def lunar_board(d: dt.date) -> Dict[str, Any]:
    """Brett-Zyklus: von Neumond zu Neumond. Liefert eine stabile Brett-ID
    (Datum des Zyklus-Neumonds) und den Tag im Brett (1..30).

    Die Tagesfraktion von `days_since` ist innerhalb eines Zyklus konstant
    (wir werten immer Mitternacht aus), daher ist die Brett-ID über den
    ganzen Zyklus hinweg stabil.
    """
    frac = moon_phase_fraction(d)
    days_since = frac * _SYNODIC
    new_moon = (dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)
                - dt.timedelta(days=days_since))
    day_index = min(30, int(days_since) + 1)
    return {"boardId": new_moon.date().isoformat(), "dayIndex": day_index}

# --- Die 30 Felder — Senet-Häuser + thematische Stationen ------------------
# Felder 15 und 26–30 folgen den historisch belegten Senet-Häusern; die
# übrigen Stationen sind thematisch auf den Mondbogen gelegt (1–14 zunehmend
# = Aufbau, 16–25 abnehmend = Ernte & Loslassen).
FIELD_EVENTS: List[Dict[str, str]] = [
    {"name": "Der Aufbruch", "core": "Etwas beginnt leise. Setze den ersten, kleinen Schritt."},
    {"name": "Die Schwelle", "core": "Altes liegt hinter dir, Neues ist noch formlos. Bleib offen."},
    {"name": "Das Saatkorn", "core": "Was du jetzt pflanzt, trägt den ganzen Monat. Wähle bewusst."},
    {"name": "Der junge Mond", "core": "Erste Konturen werden sichtbar. Benenne, was du willst."},
    {"name": "Die Weggabelung", "core": "Zwei Richtungen ziehen. Entscheide dich für eine — heute."},
    {"name": "Das Werkzeug", "core": "Dir fehlt nichts. Nutze, was du schon in Händen hältst."},
    {"name": "Der Gefährte", "core": "Du musst nicht allein gehen. Bitte um das, was du brauchst."},
    {"name": "Die Prüfung", "core": "Ein Widerstand zeigt, was dir wichtig ist. Weiche nicht aus."},
    {"name": "Der Rastplatz", "core": "Halte kurz inne und schau zurück: Es ist mehr geschafft, als du denkst."},
    {"name": "Die Strömung", "core": "Es läuft. Verstärke, was von selbst in Bewegung ist."},
    {"name": "Der Spiegel", "core": "Was dich an anderen reizt, erzählt von dir. Sieh genau hin."},
    {"name": "Die Brücke", "core": "Ein Zwischenraum will überquert werden. Vertrau der Konstruktion."},
    {"name": "Der Hüter", "core": "Grenzen schützen, was reift. Sag heute einmal freundlich Nein."},
    {"name": "Der Vorabend", "core": "Kurz vor der Fülle: Sammle dich, statt zu zerstreuen."},
    {"name": "Haus der Wiedergeburt", "core": "Vollmond-Feld. Hierher kehrt zurück, was neu beginnen darf."},
    {"name": "Die Fülle", "core": "Nimm an, was da ist — ohne sofort nach dem Nächsten zu greifen."},
    {"name": "Die Lese", "core": "Trenne reif von unreif. Nicht alles muss mit."},
    {"name": "Das Geschenk", "core": "Etwas will weitergegeben werden. Teilen vermehrt es."},
    {"name": "Die Wende", "core": "Der Bogen neigt sich. Richte den Blick vom Außen nach innen."},
    {"name": "Der Abendstern", "core": "Würdige einen stillen Erfolg, den niemand sonst gesehen hat."},
    {"name": "Das Sieb", "core": "Lass fallen, was nur Gewohnheit ist. Behalte, was nährt."},
    {"name": "Die Quelle", "core": "Erneuere deine Kraft an ihrem Ursprung — nicht an ihren Ersatzmitteln."},
    {"name": "Der Schatten", "core": "Was du vermeidest, wartet geduldig. Ein kurzer Blick genügt heute."},
    {"name": "Die Stille", "core": "Weniger Worte, mehr Wahrnehmung. Höre einen Tag lang zu."},
    {"name": "Der Vorbote", "core": "Das Ende des Zyklus kündigt sich an. Schließe einen offenen Kreis."},
    {"name": "Schönes Haus", "core": "Segensfeld. Dankbarkeit für das, was dieser Monat gebracht hat."},
    {"name": "Haus des Wassers", "core": "Die Strömung trägt zurück zur Wiedergeburt — ein Umweg, keine Strafe."},
    {"name": "Haus der drei Wahrheiten", "core": "Nur was wahr ist, geht hinaus. Prüfe dein Motiv."},
    {"name": "Haus des Re-Atum", "core": "Die Schwelle des Horizonts. Bereit sein ist alles."},
    {"name": "Der Horizont", "core": "Ankunft. Was hier steht, tritt hinaus ins Binsengefilde."},
]

# --- Steine & Regeln -------------------------------------------------------
STONES: Dict[str, str] = {
    "fokus": "Fokus", "werk": "Werk", "liebe": "Liebe",
    "kraft": "Kraft", "geist": "Geist",
}
_STONE_ORDER = list(STONES.keys())  # deterministische Reihenfolge (Orakelwahl)
_START, _AARU = 0, 31  # 0 = vor dem Brett, 31 = ausgezogen (Binsengefilde)

def board_throw(birth_date: str, board_id: str, day_index: int) -> int:
    """Deterministischer Senet-Wurf (1..5) aus Profil + Bretttag."""
    return _det_hash("board", (birth_date or "").strip(), board_id, day_index) % 5 + 1

# --- Seltene Ereignistage (docs/spielideen.md #3) --------------------------
# Deterministisch aus Profil + Bretttag: im Schnitt ~2 besondere Tage pro
# Mondmonat und Person — selten genug, dass sie sich wie Geschenke anfühlen,
# und fair, weil vorherbestimmt statt ausgewürfelt.
BOARD_EVENTS: Dict[str, Dict[str, str]] = {
    "sternschnuppe": {
        "symbol": "✨", "name": "Sternschnuppe",
        "text": "Das Orakel wirft heute zweimal — du wählst, welcher Wurf gilt."},
    "rueckenwind": {
        "symbol": "🌬", "name": "Rückenwind",
        "text": "Ein günstiger Wind schiebt an: dein Stein zieht heute ein Feld weiter."},
}

def board_event(birth_date: str, board_id: str, day_index: int) -> Optional[Dict[str, str]]:
    """Besonderer Moment des Tages (oder None). Zwei feste Lose aus 30."""
    r = _det_hash("event", (birth_date or "").strip(), board_id, day_index) % 30
    key = {7: "sternschnuppe", 13: "rueckenwind"}.get(r)
    return {"key": key, **BOARD_EVENTS[key]} if key else None

def board_alt_throw(birth_date: str, board_id: str, day_index: int) -> int:
    """Zweiter Wurf am Sternschnuppen-Tag (1..5, unabhängig vom ersten)."""
    return _det_hash("board-alt", (birth_date or "").strip(), board_id, day_index) % 5 + 1

def _water_landing(positions: Dict[str, int], stone: str) -> int:
    """Feld 27 (Haus des Wassers): zurück zu Feld 15; ist es belegt, das
    nächste freie Feld darunter."""
    taken = {p for s, p in positions.items() if s != stone and 1 <= p <= 30}
    f = 15
    while f in taken and f > 1:
        f -= 1
    return f

def legal_moves(positions: Dict[str, int], throw: int) -> Dict[str, int]:
    """Zielfeld je Stein für alle legalen Züge.

    Regeln (v1, docs/spielkonzept.md): kein Landen auf eigenem Stein;
    Feld 27 leitet nach 15 um; Auszug (→31) aus 30 mit jedem Wurf, aus 29
    nur mit 2, aus 28 nur mit 3; Überwürfe darüber hinaus sind nicht legal.
    """
    moves: Dict[str, int] = {}
    for stone in _STONE_ORDER:
        pos = positions.get(stone, _START)
        if pos == _AARU:
            continue
        target = pos + throw
        if target > 30:
            if pos == 30 or (pos == 29 and throw == 2) or (pos == 28 and throw == 3):
                moves[stone] = _AARU
            continue
        final = _water_landing(positions, stone) if target == 27 else target
        occupied = {p for s, p in positions.items() if s != stone and 1 <= p <= 30}
        if final not in occupied:
            moves[stone] = final
    return moves

def _validate_positions(raw: Dict[str, int]) -> Dict[str, int]:
    """Client-Positionen prüfen: bekannte Steine, Wertebereich, keine
    Doppelbelegung von Brettfeldern (0 und 31 dürfen mehrfach vorkommen)."""
    pos: Dict[str, int] = {}
    for stone in _STONE_ORDER:
        v = raw.get(stone, _START)
        if not isinstance(v, int) or not (_START <= v <= _AARU):
            raise ValueError(f"Ungültige Position für {stone}")
        pos[stone] = v
    on_board = [v for v in pos.values() if 1 <= v <= 30]
    if len(on_board) != len(set(on_board)):
        raise ValueError("Zwei Steine auf demselben Feld")
    return pos

def board_today(d: Optional[dt.date] = None) -> Dict[str, Any]:
    """Globale Tageslage — für alle Spieler identisch, daher cachebar."""
    d = d or dt.date.today()
    lb = lunar_board(d)
    mf = moon_phase_fraction(d)
    hex_idx = iching_index(d)
    hx = iching_lookup(hex_idx)
    field = FIELD_EVENTS[lb["dayIndex"] - 1]
    today = {
        "date": d.isoformat(),
        "boardId": lb["boardId"], "dayIndex": lb["dayIndex"],
        "moon": {"name": moon_phase_name(mf), "frac": round(mf, 3)},
        "hexagram": {"index": hex_idx, "name": hx.get("name", ""), "core": hx.get("core", "")},
        "ganzhi": ganzhi_day(d),
        "field": {"index": lb["dayIndex"], **field},
        "stones": STONES,
    }
    today["explain"] = board_explanations(today)
    return today

# --- Request-Modelle -------------------------------------------------------

class BoardThrowRequest(BaseModel):
    birthDate: str = Field(..., max_length=32)
    positions: Dict[str, int] = Field(default_factory=dict)
    dayIndex: Optional[int] = Field(None, ge=1, le=30)

class BoardMoveRequest(BaseModel):
    birthDate: str = Field(..., max_length=32)
    birthPlace: Optional[str] = Field(None, max_length=200)
    positions: Dict[str, int] = Field(default_factory=dict)
    stone: str = Field(..., max_length=16)
    tone: Optional[str] = Field(None, max_length=64)
    dayIndex: Optional[int] = Field(None, ge=1, le=30)
    useAlt: bool = False  # Sternschnuppen-Tag: den zweiten Wurf nehmen

def _board_reading(req: BoardMoveRequest, today: Dict[str, Any], stone: str,
                   from_pos: int, to_pos: int, is_today: bool,
                   event: Optional[Dict[str, str]] = None) -> str:
    """Mikro-Lesung zum Zug. LLM nur für den aktuellen Tag; Nachhol-Züge und
    LLM-Fehler bekommen einen deterministischen Kurztext."""
    field = FIELD_EVENTS[min(to_pos, 30) - 1] if to_pos >= 1 else FIELD_EVENTS[0]
    stone_label = STONES.get(stone, stone)
    if to_pos == _AARU:
        fallback = (f"{stone_label} verlässt das Brett ins Binsengefilde — "
                    f"dieser Bereich hat seinen Monatsweg vollendet.")
    else:
        fallback = f"{stone_label} erreicht {field['name']}: {field['core']}"
    if not is_today:
        return fallback
    bdate = parse_birth_date(req.birthDate)
    sun = zodiac_from_date(bdate) if bdate else "unbekannt"
    lp = life_path_number(bdate) if bdate else "–"
    prompt = f"""Tageslage: Tag {today['dayIndex']} des Mondmonats · {today['moon']['name']} ·
I-Ging {today['hexagram']['index']} „{today['hexagram']['name']}“ ({today['hexagram']['core']}) ·
Tageszeichen {today['ganzhi']['label']}.

Zug: Der Stein „{stone_label}“ ({'zieht aus ins Binsengefilde' if to_pos == _AARU else f"zieht von Feld {from_pos} auf Feld {to_pos} „{field['name']}“ — {field['core']}"}).
Profil: Sternzeichen {sun}, Lebenszahl {lp}{f", Ort {req.birthPlace}" if req.birthPlace else ""}.{f'''
Besonderer Tag: {event['symbol']} {event['name']} — {event['text']} Webe dieses seltene Ereignis kurz in die Deutung ein.''' if event else ""}

Schreibe 2–3 Sätze Deutung dieses Zuges für den Lebensbereich {stone_label} und
schließe mit einem konkreten Tagesimpuls (Imperativ, 1 Satz). Keine Aufzählung,
keine Überschrift, keine medizinisch/juristisch/finanziell heiklen Ratschläge."""
    try:
        return oa_text(_tone_directive(req.tone) + "\n\n" + prompt, temperature=0.8).strip()
    except Exception as e:
        # Sichtbar loggen — ein stiller Fallback hat in Produktion wochenlang
        # den Temperature-Bug der GPT-5-Umstellung verdeckt.
        print(f"board reading LLM failed ({MODEL}): {e}")
        return fallback

async def _board_move_impl(req: BoardMoveRequest):
    today = board_today()
    day = req.dayIndex or today["dayIndex"]
    if day > today["dayIndex"]:
        return JSONResponse(status_code=422, content={"detail": "Dieser Tag liegt in der Zukunft."})
    try:
        positions = _validate_positions(req.positions)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    event = board_event(req.birthDate, today["boardId"], day)
    if req.useAlt and not (event and event["key"] == "sternschnuppe"):
        return JSONResponse(status_code=422, content={
            "detail": "Heute gibt es keinen zweiten Wurf."})
    if req.useAlt:
        throw = board_alt_throw(req.birthDate, today["boardId"], day)
    else:
        throw = board_throw(req.birthDate, today["boardId"], day)
        if event and event["key"] == "rueckenwind":
            throw += 1  # Rückenwind: ein Feld weiter (Auszug verlangt weiter Präzision)
    moves = legal_moves(positions, throw)
    if req.stone not in moves:
        return JSONResponse(status_code=422, content={
            "detail": "Dieser Zug ist nicht erlaubt.", "throw": throw, "legalMoves": moves})
    from_pos = positions[req.stone]
    to_pos = moves[req.stone]
    positions[req.stone] = to_pos
    is_today = (day == today["dayIndex"])
    text = _board_reading(req, today, req.stone, from_pos, to_pos, is_today, event)
    field = FIELD_EVENTS[min(to_pos, 30) - 1]
    chips = [f"Tag {day}", today["moon"]["name"],
             f"I-Ging: {today['hexagram']['name']}", today["ganzhi"]["label"]]
    if event:
        chips.append(f"{event['symbol']} {event['name']}")
    return {
        "boardId": today["boardId"], "dayIndex": day, "throw": throw,
        "positions": positions, "event": event,
        "moved": {"stone": req.stone, "from": from_pos, "to": to_pos,
                  "water": (from_pos + throw == 27 and to_pos != 27),
                  "field": field["name"] if to_pos != _AARU else "Binsengefilde"},
        "reading": {"text": text, "chips": chips},
        "disclaimer": "Unterhaltung & Selbstreflexion – kein Ersatz für professionelle Beratung.",
    }

@app.get("/board/today")
def board_today_route():
    return board_today()

@app.get("/board/fields")
def board_fields_route():
    """Alle 30 Feldkarten (für das Feld-Album im Frontend) — statisch,
    identisch für alle, daher unbegrenzt cachebar."""
    return {"fields": [{"index": i + 1, **f} for i, f in enumerate(FIELD_EVENTS)]}

@app.post("/board/throw")
def board_throw_route(req: BoardThrowRequest = Body(...)):
    today = board_today()
    day = req.dayIndex or today["dayIndex"]
    if day > today["dayIndex"]:
        return JSONResponse(status_code=422, content={"detail": "Dieser Tag liegt in der Zukunft."})
    try:
        positions = _validate_positions(req.positions)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    throw = board_throw(req.birthDate, today["boardId"], day)
    event = board_event(req.birthDate, today["boardId"], day)
    effective = throw + 1 if (event and event["key"] == "rueckenwind") else throw
    resp = {"boardId": today["boardId"], "dayIndex": day, "throw": throw,
            "event": event, "legalMoves": legal_moves(positions, effective)}
    if event and event["key"] == "sternschnuppe":
        alt = board_alt_throw(req.birthDate, today["boardId"], day)
        resp["alt"] = {"throw": alt, "legalMoves": legal_moves(positions, alt)}
    return resp

# /board/move ruft das LLM auf und bekommt darum dasselbe Rate-Limit wie
# /reading (Nachholzüge sind LLM-frei, zählen aber mit — 80/Tag reicht weit).
if _HAS_SLOWAPI and limiter is not None:
    @app.post("/board/move")
    @limiter.limit(READING_RATE_LIMIT)
    async def board_move(request: Request, req: BoardMoveRequest = Body(...)):
        return await _board_move_impl(req)
else:
    @app.post("/board/move")
    async def board_move(req: BoardMoveRequest = Body(...)):
        return await _board_move_impl(req)


# ---------------------------------------------------------------------------
# /resonanz — Partner-Resonanz (docs/spielideen.md #5): zweites Geburtsdatum
# → gemeinsame Tageslesung aus Sonnenzeichen-Paar, Lebenszahlen und
# chinesischen Jahreszeichen. Rein deterministische Inputs, LLM-Text mit
# deterministischem Fallback; teilt das Reading-Rate-Limit.
# ---------------------------------------------------------------------------

class ResonanzRequest(BaseModel):
    birthDate: str = Field(..., max_length=32)
    partnerDate: str = Field(..., max_length=32)
    tone: Optional[str] = Field(None, max_length=64)

def _resonanz_impl(req: ResonanzRequest):
    d1 = parse_birth_date(req.birthDate)
    d2 = parse_birth_date(req.partnerDate)
    if not d1 or not d2:
        return JSONResponse(status_code=422, content={
            "detail": "Bitte beide Geburtsdaten angeben (TT.MM.JJJJ)."})
    today = board_today()
    z1, z2 = zodiac_from_date(d1), zodiac_from_date(d2)
    lp1, lp2 = life_path_number(d1), life_path_number(d2)
    a1, a2 = chinese_animal(d1.year), chinese_animal(d2.year)
    chips = [f"{z1} & {z2}", f"Lebenszahlen {lp1} & {lp2}", f"{a1} & {a2}"]
    fallback = (f"{z1} trifft {z2}, Lebenszahl {lp1} trifft {lp2}, "
                f"{a1} begegnet {a2}. Unter dem heutigen Feld "
                f"„{today['field']['name']}“ gilt für euch beide: {today['field']['core']}")
    prompt = f"""Tageslage: Tag {today['dayIndex']} des Mondmonats · {today['moon']['name']} ·
I-Ging {today['hexagram']['index']} „{today['hexagram']['name']}“ ({today['hexagram']['core']}) ·
Tageszeichen {today['ganzhi']['label']} · Feld „{today['field']['name']}“ — {today['field']['core']}.

Paar-Resonanz: Person A ist Sternzeichen {z1}, Lebenszahl {lp1}, Jahreszeichen {a1}.
Person B ist Sternzeichen {z2}, Lebenszahl {lp2}, Jahreszeichen {a2}.

Schreibe 3–4 Sätze darüber, wie diese beiden Energien heute zusammenwirken —
was sie einander geben, wo es knistern oder haken kann — und schließe mit einem
konkreten gemeinsamen Tagesimpuls (Imperativ, 1 Satz). Sprich beide als „ihr" an.
Keine Aufzählung, keine Überschrift, keine medizinisch/juristisch/finanziell
heiklen Ratschläge, keine Beziehungsprognosen über den heutigen Tag hinaus."""
    seed = _det_hash("resonanz", req.birthDate.strip(), req.partnerDate.strip(), today["date"])
    try:
        text = oa_text(_tone_directive(req.tone) + "\n\n" + prompt, seed=seed).strip()
    except Exception as e:
        print(f"resonanz LLM failed ({_llm_id()}): {e}")
        text = fallback
    return {"date": today["date"], "chips": chips, "text": text,
            "pair": {"zodiac": [z1, z2], "lifePath": [lp1, lp2], "animal": [a1, a2]},
            "disclaimer": "Unterhaltung & Selbstreflexion – kein Ersatz für professionelle Beratung."}

if _HAS_SLOWAPI and limiter is not None:
    @app.post("/resonanz")
    @limiter.limit(READING_RATE_LIMIT)
    async def resonanz(request: Request, req: ResonanzRequest = Body(...)):
        return _resonanz_impl(req)
else:
    @app.post("/resonanz")
    async def resonanz(req: ResonanzRequest = Body(...)):
        return _resonanz_impl(req)


# ---------------------------------------------------------------------------
# /compare — Blind-A/B-Test der LLM-Provider (OpenAI vs. Anthropic).
# Erzeugt dieselbe Tages-Mikrodeutung mit beiden Providern und zeigt sie in
# zufälliger (aber deterministischer) Reihenfolge als A/B — die Auflösung
# steht eingeklappt darunter. Nur nutzbar, wenn beide Provider konfiguriert
# sind; teilt sich das Rate-Limit der Readings.
# ---------------------------------------------------------------------------
import html as _html

def _compare_prompt(birth_date: str, stone: str) -> tuple:
    today = board_today()
    bdate = parse_birth_date(birth_date)
    sun = zodiac_from_date(bdate) if bdate else "unbekannt"
    lp = life_path_number(bdate) if bdate else "–"
    stone_label = STONES.get(stone, "Fokus")
    field = today["field"]
    user = f"""Tageslage: Tag {today['dayIndex']} des Mondmonats · {today['moon']['name']} ·
I-Ging {today['hexagram']['index']} „{today['hexagram']['name']}“ ({today['hexagram']['core']}) ·
Tageszeichen {today['ganzhi']['label']}.

Zug: Der Stein „{stone_label}“ zieht auf Feld {field['index']} „{field['name']}“ — {field['core']}.
Profil: Sternzeichen {sun}, Lebenszahl {lp}.

Schreibe 2–3 Sätze Deutung dieses Zuges für den Lebensbereich {stone_label} und
schließe mit einem konkreten Tagesimpuls (Imperativ, 1 Satz). Keine Aufzählung,
keine Überschrift, keine medizinisch/juristisch/finanziell heiklen Ratschläge."""
    return _tone_directive(None), user, today

def _compare_page(body: str) -> Response:
    page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LLM-Blindvergleich · horoskop.one</title>
<style>body{{font-family:Georgia,serif;background:#f3ead7;color:#2b2317;max-width:720px;
margin:0 auto;padding:24px;line-height:1.6}}
.card{{background:#fffaf0;border:1px solid #dcca9e;border-radius:14px;padding:20px;margin:16px 0}}
h1{{font-size:22px}}h2{{font-size:16px;color:#8a6420;letter-spacing:.08em;text-transform:uppercase}}
input,select{{padding:10px;border:1px solid #cdb98c;border-radius:8px;font-size:16px}}
button{{background:#a9782c;color:#fffaf0;border:none;border-radius:10px;padding:12px 18px;
font-size:16px;cursor:pointer}}details{{margin-top:14px}}summary{{cursor:pointer;color:#8a6420}}
.hint{{color:#6b5c40;font-size:14px}}</style></head><body>
<h1>🔬 LLM-Blindvergleich</h1>{body}</body></html>"""
    return Response(content=page, media_type="text/html; charset=utf-8")

async def _compare_impl(birthDate: Optional[str], stone: str):
    if _anthropic_client is None:
        return _compare_page(
            "<div class='card'><p>Für den Vergleich müssen <b>beide</b> Provider konfiguriert "
            "sein — bitte <code>ANTHROPIC_API_KEY</code> in den Railway-Variablen setzen "
            "(OPENAI_API_KEY ist bereits vorhanden).</p></div>")
    if not birthDate:
        return _compare_page("""<div class='card'>
<p>Erzeugt dieselbe Tages-Mikrodeutung einmal mit OpenAI und einmal mit Anthropic —
in zufälliger Reihenfolge, damit du blind entscheiden kannst.</p>
<form method="get" action="/compare">
<label>Geburtsdatum: <input type="date" name="birthDate" required></label>
<label> Stein: <select name="stone"><option value="fokus">Fokus</option>
<option value="werk">Werk</option><option value="liebe">Liebe</option>
<option value="kraft">Kraft</option><option value="geist">Geist</option></select></label>
<button type="submit">Vergleich erzeugen</button></form>
<p class="hint">Jeder Aufruf kostet zwei LLM-Anfragen und zählt gegen das Reading-Rate-Limit.</p>
</div>""")
    if re.match(r'^\d{4}-\d{2}-\d{2}$', birthDate.strip()):
        y, m, d = birthDate.strip().split('-')
        birthDate = f"{d}.{m}.{y}"
    system, user, today = _compare_prompt(birthDate[:32], stone[:16])
    results = {}
    for prov in ("openai", "anthropic"):
        try:
            results[prov] = llm_text(system, user, temperature=0.8, provider=prov)
        except Exception as e:
            print(f"compare: {prov} failed: {e}")
            results[prov] = f"[{prov} fehlgeschlagen: {e}]"
    # Deterministische, aber tagesabhängige Zuordnung A/B — nicht erratbar
    # ohne Auflösung, aber reproduzierbar beim Neuladen.
    flip = _det_hash("compare", birthDate, today["date"]) % 2 == 1
    order = [("anthropic", ANTHROPIC_MODEL), ("openai", MODEL)] if flip \
        else [("openai", MODEL), ("anthropic", ANTHROPIC_MODEL)]
    blocks = ""
    for label, (prov, _model) in zip(("A", "B"), order):
        blocks += (f"<div class='card'><h2>Version {label}</h2>"
                   f"<p>{_html.escape(results[prov])}</p></div>")
    reveal = " · ".join(f"Version {label} = {prov} ({_html.escape(model)})"
                        for label, (prov, model) in zip(("A", "B"), order))
    blocks += (f"<details><summary>🔍 Auflösung (erst nach deinem Urteil öffnen)</summary>"
               f"<p>{reveal}</p></details>"
               f"<p class='hint'>Tag {today['dayIndex']} · {_html.escape(today['moon']['name'])} · "
               f"I-Ging {today['hexagram']['index']} · {_html.escape(today['ganzhi']['label'])} · "
               f"<a href='/compare'>Neuer Vergleich</a></p>")
    return _compare_page(blocks)

if _HAS_SLOWAPI and limiter is not None:
    @app.get("/compare")
    @limiter.limit(READING_RATE_LIMIT)
    async def compare(request: Request, birthDate: Optional[str] = None, stone: str = "fokus"):
        return await _compare_impl(birthDate, stone)
else:
    @app.get("/compare")
    async def compare(birthDate: Optional[str] = None, stone: str = "fokus"):
        return await _compare_impl(birthDate, stone)


# Host-/Pfad-Routing für die Spiel-Beta: play.horoskop.one (und der Pfad
# /play auf jeder Domain) liefern das Brett statt der klassischen Startseite.
@app.middleware("http")
async def play_subdomain_rewrite(request: Request, call_next):
    host = (request.headers.get("host") or "").split(":")[0].lower()
    path = request.scope.get("path", "")
    if path == "/play" or path == "/play/":
        request.scope["path"] = "/play.html"
    elif host.startswith("play.") and path == "/":
        request.scope["path"] = "/play.html"
    return await call_next(request)


# Serve built frontend
try:
    here = os.path.dirname(__file__)
    dist_dir = os.path.join(here, 'dist')
    if os.path.isdir(dist_dir):
        app.mount('/', StaticFiles(directory=dist_dir, html=True), name='static')
except OSError as _e:
    print('Static mount failed:', _e)
