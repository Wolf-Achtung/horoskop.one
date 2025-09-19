# main.py  — horoskop.one API v5.4 longform (corrected, single-file)
import os, re, json, datetime as dt
from typing import Optional, Dict, Any, List

import httpx
from fastapi import FastAPI, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from timezonefinder import TimezoneFinder
from zoneinfo import ZoneInfo

from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

app = FastAPI(title="horoskop.one API", version="v5.4-longform")

raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
origins = [o.strip() for o in raw_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "body": exc.body})

@app.get("/favicon.ico")
def favicon(): return Response(status_code=204)

tf = TimezoneFinder()

def parse_birth_date(date_str: str) -> Optional[dt.date]:
    s = (date_str or '').strip()
    m = re.match(r'^(\\d{4})-(\\d{2})-(\\d{2})$', s)
    if m:
        y, mth, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return dt.date(y, mth, d)
    m = re.match(r'^(\\d{1,2})\\.(\\d{1,2})\\.(\\d{2,4})$', s)
    if m:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y = 2000 + y if y < 30 else 1900 + y
        return dt.date(y, mth, d)
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
    url="https://nominatim.openstreetmap.org/search"; params={"format":"json","limit":"1","q":place}
    headers={"User-Agent":"horoskop.one/1.0 (contact: support@horoskop.one)"}
    async with httpx.AsyncClient(timeout=10) as cli:
        r=await cli.get(url, params=params, headers=headers)
        if r.status_code!=200: return None
        data=r.json() or []
        if not data: return None
        try: return {"lat":float(data[0]["lat"]), "lon":float(data[0]["lon"])}
        except: return None

def find_timezone(lat:Optional[float], lon:Optional[float])->str:
    if lat is None or lon is None: return "Europe/Berlin"
    try:
        tz=tf.timezone_at(lat=lat,lng=lon); return tz or "Europe/Berlin"
    except: return "Europe/Berlin"

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
    cusps,ascmc=swe.houses(jd,lat,lon,house_sys); asc,mc=ascmc[0],ascmc[1]
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
        {"role":"system","content":"Du bist ein präziser, poetischer, freundlicher Schreibassistent."},
        {"role":"user","content":prompt},
    ])
    if seed is not None: kwargs["seed"]=seed
    cr=client.chat.completions.create(**kwargs)
    return cr.choices[0].message.content

def try_load_json(maybe:str)->Any:
    m=re.search(r"```json([\\s\\S]*?)```", maybe)
    if m:
        try: return json.loads(m.group(1))
        except: pass
    m=re.search(r"\\{[\\s\\S]*\\}$", maybe.strip())
    if m:
        try: return json.loads(m.group(0))
        except: pass
    try: return json.loads(maybe)
    except: return {"raw": maybe}

class ReadingRequest(BaseModel):
    birthDate: str
    birthPlace: str
    birthTime: Optional[str] = None
    approxDaypart: Optional[str] = None
    period: str = Field("day", description="day|week|month")
    tone: str = "mystic_deep"
    seed: Optional[int] = None
    mixer: Optional[Dict[str,int]] = None

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
def health(): return {"ok": True, "model": MODEL}

@app.post("/reading", response_model=ReadingResponse)
async def reading(req: ReadingRequest = Body(...)):
    bdate=parse_birth_date(req.birthDate) or dt.date.today()
    btime=parse_birth_time(req.birthTime)
    dpart=(req.approxDaypart or daypart_from_time(btime)).lower()

    geo=await geocode(req.birthPlace); lat=geo["lat"] if geo else None; lon=geo["lon"] if geo else None
    tzname=find_timezone(lat,lon); _=now_local(bdate,tzname)

    hemisphere="Nord" if (lat is None or lat>=0) else "Süd"
    season=season_from_date_hemisphere(bdate,lat)
    sun_sign=zodiac_from_date(bdate); cn_animal=chinese_animal(bdate.year)
    lifepath=life_path_number(bdate); tree=celtic_tree(bdate)
    hex_idx=iching_index(bdate); mf=moon_phase_fraction(bdate); moon=moon_phase_name(mf)

    swe_data=swe_compute(bdate,btime,lat,lon,tzname)

    mixer=req.mixer or {}; mixer_list=[f"{k}:{v}%" for k,v in mixer.items()]
    why_chips=[f"Sternzeichen {sun_sign}", f"Ort {req.birthPlace or 'unbekannt'}",
               f"Saison: {season} ({hemisphere}-Halbkugel)", f"Mondphase: {moon}"]
    if swe_data:
        why_chips.insert(0, f"Aszendent {swe_data['ascendant']['sign']}")
        if swe_data.get("sunHouse"):  why_chips.append(f"Sonnenhaus {swe_data['sunHouse']}")
        if swe_data.get("moonHouse"): why_chips.append(f"Mondhaus {swe_data['moonHouse']}")

    outline_prompt=f"""
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
- Mini-Ephemeriden: Sonne≈{sun_sign}, Mondphase={moon}, I-Ging={hex_idx}, Lebenszahl={lifepath}, Chinesisch={cn_animal}, Baum={tree}
- Mixer: {', '.join(mixer_list) if mixer_list else 'Standard'}

Regeln:
- Pro Bereich 3–4 Stichpunkte, direkt aus den Rahmendaten abgeleitet.
- Letzter Stichpunkt = ultra-kurze Mini-Aktion (imperativ, 1 Satz) ohne „Aktion:“-Prefix.
- Keine medizinisch/juristisch/finanziell heiklen Ratschläge.
"""
    try:
        outline_raw=oa_text(outline_prompt, seed=req.seed, temperature=0.4)
        outline=try_load_json(outline_raw)
    except Exception as e:
        outline={"fokus":{"kern":"","punkte":[]}, "error":str(e)}

    swe_line=(f"Aszendent {swe_data['ascendant']['sign']}, MC {swe_data['mc']['sign']}, "
              f"Sonnenhaus {swe_data.get('sunHouse')}, Mondhaus {swe_data.get('moonHouse')}"
             ) if swe_data else "keine genaue Zeit/Ort ⇒ Aszendent & Häuser unbekannt"

    writing_prompt=f"""
Formuliere aus der OUTLINE ein Horoskop mit 3–4 Sätzen je Sektion im Ton „mystischer Coach“
(poetisch, warm, aber klar). Integriere die Mini-Aktion organisch in den Absatz. Keine Bullet-Listen.

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

    sections=[
        Section(title="Fokus",  text=(data.get("fokus")  or "").strip(), chips=[why_chips[0],why_chips[1],f"Saison: {season}"]),
        Section(title="Beruf",  text=(data.get("beruf")  or "").strip(), chips=[f"Lebenszahl {life_path_number(bdate)}"]),
        Section(title="Liebe",  text=(data.get("liebe")  or "").strip(), chips=[f"Mondphase: {moon}"]),
        Section(title="Energie",text=(data.get("energie") or "").strip(), chips=[f"Tag/Nacht: {dpart}"]),
    ]

    disclaimer=("Hinweis: Dieses Angebot dient ausschließlich der Unterhaltung "
                "und achtsamen Selbstreflexion und ersetzt keine professionelle Beratung. "
                "Bei Krisen oder akuter Gefahr: 112 (EU) / lokale Beratungsstellen.")

    meta={
        "period": req.period, "tone": req.tone,
        "birthDate": req.birthDate, "birthPlace": req.birthPlace, "birthTime": req.birthTime,
        "approxDaypart": dpart, "geo": {"lat":lat,"lon":lon,"tz":tzname},
        "season": season, "hemisphere": "Nord" if (lat is None or lat>=0) else "Süd",
        "mini": {"sunSignApprox": zodiac_from_date(bdate), "moonPhase": moon, "moonFrac": round(mf,3),
                 "iChing": iching_index(bdate), "lifePath": life_path_number(bdate),
                 "chinese": chinese_animal(bdate.year), "tree": celtic_tree(bdate)},
        "swiss": swe_data,
    }
    return ReadingResponse(meta=meta, sections=sections, chips=why_chips, disclaimer=disclaimer)

# Run: uvicorn main:app --host 0.0.0.0 --port 8080


@app.post('/readings', response_model=ReadingResponse)
async def readings_alias(req: ReadingRequest = Body(...)):
    return await reading(req)


# Serve built frontend
try:
    here = os.path.dirname(__file__)
    dist_dir = os.path.join(here, 'dist')
    if os.path.isdir(dist_dir):
        app.mount('/', StaticFiles(directory=dist_dir, html=True), name='static')
except Exception as _e:
    print('Static mount failed:', _e)
