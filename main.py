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
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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
raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
origins = [o.strip() for o in raw_origins.split(",") if o.strip()] or DEFAULT_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# Rate limiting (optional) — schützt den OpenAI-Key vor Missbrauch.
if _HAS_SLOWAPI:
    limiter = Limiter(key_func=get_remote_address, default_limits=[])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
else:
    limiter = None

READING_RATE_LIMIT = os.getenv("READING_RATE_LIMIT", "10/minute")

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

def life_path_number(d:dt.date)->int:
    s=f"{d.year:04d}{d.month:02d}{d.day:02d}"; n=sum(int(c) for c in s)
    while n>9 and n not in (11,22,33): n=sum(int(c) for c in str(n))
    return n

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

def iching_index(d:dt.date)->int:
    daynum=(d-dt.date(d.year,1,1)).days+1; idx=(daynum+d.year)%64
    return idx if idx!=0 else 1

def celtic_tree(d:dt.date)->str:
    ranges=[("Birke",(12,24),(1,20)),("Eberesche",(1,21),(2,17)),("Esche",(2,18),(3,17)),("Erle",(3,18),(4,14)),("Weide",(4,15),(5,12)),
            ("Weißdorn",(5,13),(6,9)),("Eiche",(6,10),(7,7)),("Stechpalme",(7,8),(8,4)),("Hasel",(8,5),(9,1)),("Weinrebe",(9,2),(9,29)),
            ("Efeu",(9,30),(10,27)),("Schilfrohr",(10,28),(11,24)),("Holunder",(11,25),(12,23))]
    y=d.year; md=lambda m,dd: dt.date(y,m,dd)
    for name,(m1,d1),(m2,d2) in ranges:
        s,e=md(m1,d1),md(m2,d2)
        if (s<=e and s<=d<=e) or (s>e and (d>=s or d<=e)): return name
    return "Birke"

async def geocode(place:str)->Optional[Dict[str,float]]:
    if not place: return None
    try:
        url="https://nominatim.openstreetmap.org/search"; params={"format":"json","limit":"1","q":place}
        headers={"User-Agent":"horoskop.one/1.0 (contact: support@horoskop.one)"}
        async with httpx.AsyncClient(timeout=10) as cli:
            r=await cli.get(url, params=params, headers=headers)
            if r.status_code!=200: return None
            data=r.json() or []
            if not data: return None
            return {"lat":float(data[0]["lat"]), "lon":float(data[0]["lon"])}
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

def oa_text(prompt:str, seed:Optional[int]=None, temperature:float=0.8)->str:
    kwargs=dict(model=MODEL, temperature=temperature, messages=[
        {"role":"system","content":"Du bist ein klarer, sachlicher und freundlicher Schreibassistent. Du schreibst verständlich, konkret und alltagsnah — ohne Esoterik, ohne Pathos, ohne blumige Metaphern."},
        {"role":"user","content":prompt},
    ])
    if seed is not None: kwargs["seed"]=seed
    cr=client.chat.completions.create(**kwargs)
    return cr.choices[0].message.content

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
- Lebenszahl (Numerologie): {ctx['lifepath']}
- Chinesisches Tierzeichen: {ctx['cn_animal']} (Jahr {ctx['birth_year']})
- Keltischer Baum: {ctx['tree']}
- I-Ging Hexagramm: {ctx['hex_idx']}
{ctx['swe_line']}
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
    birthDate: str
    birthPlace: str
    birthTime: Optional[str] = None
    approxDaypart: Optional[str] = None
    period: str = Field("day", description="day|week|month")
    tone: str = "mystic_deep"
    readingType: str = Field("classic", description="classic|blueprint|soul_purpose|career|relationship|wealth|timeline|genius")
    seed: Optional[int] = None
    mixer: Optional[Dict[str,int]] = None
    coords: Optional[Dict[str,float]] = None

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
def health(): return {"ok": True, "model": MODEL}

@app.get("/reading-types")
def reading_types():
    """Return available reading types for the frontend."""
    return [{"id": k, **v} for k, v in DEEP_READING_TYPES.items()]

async def _reading_impl(req: ReadingRequest):
  try:
    bdate=parse_birth_date(req.birthDate) or dt.date.today()
    btime=parse_birth_time(req.birthTime)
    dpart=(req.approxDaypart or daypart_from_time(btime)).lower()

    if req.coords and req.coords.get("lat") is not None and req.coords.get("lon") is not None:
        lat, lon = req.coords["lat"], req.coords["lon"]
    else:
        geo=await geocode(req.birthPlace); lat=geo["lat"] if geo else None; lon=geo["lon"] if geo else None
    tzname=find_timezone(lat,lon); _=now_local(bdate,tzname)

    hemisphere="Nord" if (lat is None or lat>=0) else "Süd"
    season=season_from_date_hemisphere(bdate,lat)
    sun_sign=zodiac_from_date(bdate); cn_animal=chinese_animal(bdate.year)
    lifepath=life_path_number(bdate); tree=celtic_tree(bdate)
    hex_idx=iching_index(bdate); mf=moon_phase_fraction(bdate); moon=moon_phase_name(mf)

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

    disclaimer=("Hinweis: Dieses Angebot dient ausschließlich der Unterhaltung "
                "und achtsamen Selbstreflexion und ersetzt keine professionelle Beratung. "
                "Bei Krisen oder akuter Gefahr: 112 (EU) / lokale Beratungsstellen.")

    meta={
        "period": req.period, "tone": req.tone,
        "toneLabel": _TONE_LABELS.get((req.tone or "").lower(), _TONE_LABELS["mystic_coach"]),
        "activeMixer": active_mixer,
        "mixerLabels": _MIXER_LABELS,
        "readingType": rtype,
        "readingLabel": DEEP_READING_TYPES[rtype]["label"],
        "birthDate": req.birthDate, "birthPlace": req.birthPlace, "birthTime": req.birthTime,
        "approxDaypart": dpart, "geo": {"lat":lat,"lon":lon,"tz":tzname},
        "season": season, "hemisphere": "Nord" if (lat is None or lat>=0) else "Süd",
        "mini": {"sunSignApprox": zodiac_from_date(bdate), "moonPhase": moon, "moonFrac": round(mf,3),
                 "iChing": iching_index(bdate), "lifePath": life_path_number(bdate),
                 "chinese": chinese_animal(bdate.year), "tree": celtic_tree(bdate)},
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
- Ort: {req.birthPlace} → lat={lat}, lon={lon}, Zeitzone={tzname}
- Datum: {bdate.strftime('%d.%m.%Y')} · Tagesabschnitt: {dpart}
- Saison/Hemisphäre: {season} / {hemisphere}
- Mini-Ephemeriden: Sonne≈{sun_sign}, Mondphase={moon}, I-Ging={hex_idx}, Lebenszahl={lifepath}, Chinesisch={cn_animal}, Baum={tree}

{mixer_block}

Ton-Vorgabe: {tone_block}

Regeln:
- Pro Bereich 3–4 Stichpunkte, direkt aus den Rahmendaten abgeleitet.
- Die Traditions-Gewichtung oben entscheidet, welche Symbolsprache dominiert.
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
- Zeitraum: {req.period} · Ort: {req.birthPlace} (Zeitzone {tzname})
- Saison/Hemisphäre: {season} / {hemisphere}
- Sonne≈{sun_sign}, Mondphase {moon}, I-Ging {hex_idx}, Lebenszahl {lifepath}, Chinesisch {cn_animal}, Baum {tree}, Tagesabschnitt {dpart}.
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

        # Add the two highest-weighted traditions as chips on the first section
        # so users can see the mixer actually shaped the output.
        top_traditions = sorted(active_mixer.items(), key=lambda kv: kv[1], reverse=True)[:2]
        mixer_chips = [f"{_MIXER_LABELS[k]} {v}%" for k, v in top_traditions if v > 0]

        sections=[
            Section(title="Fokus",  text=(data.get("fokus")  or "").strip(), chips=[why_chips[0],why_chips[1],f"Saison: {season}"] + mixer_chips),
            Section(title="Beruf",  text=(data.get("beruf")  or "").strip(), chips=[f"Lebenszahl {life_path_number(bdate)}"]),
            Section(title="Liebe",  text=(data.get("liebe")  or "").strip(), chips=[f"Mondphase: {moon}"]),
            Section(title="Energie",text=(data.get("energie") or "").strip(), chips=[f"Tag/Nacht: {dpart}"]),
        ]
        return ReadingResponse(meta=meta, sections=sections, chips=why_chips, disclaimer=disclaimer)

    # --- Deep readings (7 specialized types) ---
    ctx = {
        "bdate_str": bdate.strftime('%d.%m.%Y'),
        "dpart": dpart,
        "place": req.birthPlace,
        "lat": lat, "lon": lon, "tzname": tzname,
        "season": season, "hemisphere": hemisphere,
        "sun_sign": sun_sign, "moon": moon, "moon_frac": mf,
        "lifepath": lifepath, "cn_animal": cn_animal,
        "birth_year": bdate.year,
        "tree": tree, "hex_idx": hex_idx,
        "swe_line": (f"- Swiss-Ephemeris: {swe_line}" if swe_data
                     else "- (Keine exakte Geburtszeit → keine Häuser/Aszendent-Berechnung)"),
    }

    system_prompt = _deep_system_prompt(rtype) + "\n\nTon-Vorgabe: " + tone_block
    user_prompt = _deep_user_prompt(rtype, ctx)
    if mixer_block:
        user_prompt = mixer_block + "\n\n" + user_prompt

    try:
        raw = client.chat.completions.create(
            model=MODEL, temperature=0.7,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **({"seed": req.seed} if req.seed is not None else {}),
        ).choices[0].message.content
        data = try_load_json(raw)
    except Exception as e:
        data = {"error": str(e)}

    sections = [Section(**s) for s in _extract_sections(rtype, data, why_chips)]

    return ReadingResponse(meta=meta, sections=sections, chips=why_chips, disclaimer=disclaimer)
  except Exception as exc:
    # Never return 500 — always give the frontend a usable response
    import traceback; traceback.print_exc()
    fallback_disclaimer=("Hinweis: Dieses Angebot dient ausschließlich der Unterhaltung "
                         "und achtsamen Selbstreflexion und ersetzt keine professionelle Beratung.")
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


# Serve built frontend
try:
    here = os.path.dirname(__file__)
    dist_dir = os.path.join(here, 'dist')
    if os.path.isdir(dist_dir):
        app.mount('/', StaticFiles(directory=dist_dir, html=True), name='static')
except OSError as _e:
    print('Static mount failed:', _e)
