import os, json, re
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAI
import httpx

CORS = os.getenv("CORS_ALLOW_ORIGINS", "*")
allow_origins = [o.strip() for o in CORS.split(",")] if CORS != "*" else ["*"]

app = FastAPI(title="horoskop.one API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

AREAS = ["Fokus","Beruf","Liebe","Energie","Soziales"]

def cyrb128(s: str) -> str:
    h1=1779033703; h2=3144134277; h3=1013904242; h4=2773480762
    for ch in s:
        k=ord(ch)
        h1 = h2 ^ ((h1 ^ k) * 597399067 & 0xFFFFFFFF)
        h2 = h3 ^ ((h2 ^ k) * 2869860233 & 0xFFFFFFFF)
        h3 = h4 ^ ((h3 ^ k) * 951274213  & 0xFFFFFFFF)
        h4 = h1 ^ ((h4 ^ k) * 2716044179 & 0xFFFFFFFF)
    h1 = ( (h3 ^ (h1>>18)) * 597399067 ) & 0xFFFFFFFF
    h2 = ( (h4 ^ (h2>>22)) * 2869860233 ) & 0xFFFFFFFF
    h3 = ( (h1 ^ (h3>>17)) * 951274213 ) & 0xFFFFFFFF
    h4 = ( (h2 ^ (h4>>19)) * 2716044179 ) & 0xFFFFFFFF
    return hex((h1 ^ h2 ^ h3 ^ h4) & 0xFFFFFFFF)[2:]

def sign_western(month:int, day:int)->str:
    zones=[("Steinbock",(12,22),(1,19)),("Wassermann",(1,20),(2,18)),("Fische",(2,19),(3,20)),
           ("Widder",(3,21),(4,19)),("Stier",(4,20),(5,20)),("Zwillinge",(5,21),(6,20)),
           ("Krebs",(6,21),(7,22)),("Löwe",(7,23),(8,22)),("Jungfrau",(8,23),(9,22)),
           ("Waage",(9,23),(10,22)),("Skorpion",(10,23),(11,21)),("Schütze",(11,22),(12,21))]
    md=lambda m,d: f"{m:02d}-{d:02d}"
    cur=md(month,day)
    for name,(sm,sd),(em,ed) in zones:
        s=md(sm,sd); e=md(em,ed)
        if s<=e and s<=cur<=e: return name
        if s>e and (cur>=s or cur<=e): return name
    return "Unbekannt"

def sign_chinese(year:int)->str:
    animals=["Ratte","Büffel","Tiger","Hase","Drache","Schlange","Pferd","Ziege","Affe","Hahn","Hund","Schwein"]
    base=2008; idx=(year-base)%12
    return animals[idx]

def life_path(y:int,m:int,d:int)->int:
    s=sum(int(c) for c in f"{y:04d}{m:02d}{d:02d}")
    while s>9: s=sum(int(c) for c in str(s))
    return s

CELTIC=[("Birke",(12,24),(1,20)),("Eberesche",(1,21),(2,17)),("Esche",(2,18),(3,17)),("Erle",(3,18),(4,14)),
        ("Weide",(4,15),(5,12)),("Eiche",(6,10),(7,7)),("Stechpalme",(7,8),(8,4)),("Hasel",(8,5),(9,1)),
        ("Weinrebe",(9,2),(9,29)),("Efeu",(9,30),(10,27)),("Schilfrohr",(10,28),(11,24)),("Holunder",(11,25),(12,23))]

def tree_sign(m:int,d:int)->str:
    md=lambda a,b: f"{a:02d}-{b:02d}"
    cur=md(m,d)
    for name,(sm,sd),(em,ed) in CELTIC:
        s=md(sm,sd); e=md(em,ed)
        if s<=e and s<=cur<=e: return name
        if s>e and (cur>=s or cur<=e): return name
    return ""

def time_bucket_local(time_str: Optional[str], approx: Optional[str]) -> str:
    if time_str:
        try:
            h=int(time_str.split(":")[0])
        except Exception:
            h=None
        if h is not None:
            if 5<=h<11: return "morning"
            if 11<=h<15: return "noon"
            if 15<=h<22: return "evening"
            return "night"
    return approx or ""

async def geocode_place(place: str) -> Dict[str, Any]:
    if not place: return {}
    headers={"user-agent":"horoskop.one/1.0 (contact@horoskop.one)"}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        # Try Open-Meteo geocoding first
        try:
            r=await client.get("https://geocoding-api.open-meteo.com/v1/search",
                               params={"name":place,"count":1,"language":"de","format":"json"})
            if r.status_code==200:
                j=r.json()
                if j.get("results"):
                    res=j["results"][0]
                    lat=float(res["latitude"]); lon=float(res["longitude"])
                    tz=res.get("timezone")
                    if not tz:
                        tz=await fetch_timezone(client, lat, lon)
                    return {"lat":lat,"lon":lon,"name":res.get("name"),"country":res.get("country_code"),"timezone":tz}
        except Exception:
            pass
        # Fallback Nominatim
        try:
            r=await client.get("https://nominatim.openstreetmap.org/search",
                               params={"q":place,"format":"jsonv2","limit":1})
            if r.status_code==200:
                arr=r.json()
                if arr:
                    lat=float(arr[0]["lat"]); lon=float(arr[0]["lon"])
                    tz=await fetch_timezone(client, lat, lon)
                    return {"lat":lat,"lon":lon,"name":arr[0].get("display_name",""),"country":"", "timezone":tz}
        except Exception:
            pass
    return {}

async def fetch_timezone(client: httpx.AsyncClient, lat: float, lon: float) -> Optional[str]:
    try:
        r=await client.get("https://api.open-meteo.com/v1/forecast",
                           params={"latitude":lat,"longitude":lon,"hourly":"temperature_2m","timezone":"auto"})
        if r.status_code==200:
            j=r.json()
            return j.get("timezone")
    except Exception:
        pass
    return None

def build_base_profile(date_str:str, place:str, time_exact: Optional[str], approx: Optional[str]):
    dt=datetime.strptime(date_str,"%Y-%m-%d")
    y,m,d=dt.year,dt.month,dt.day
    return {
        "date": date_str, "place": place, "year": y, "month": m, "day": d,
        "weekday": dt.strftime("%A"),
        "western": sign_western(m,d),
        "chinese": sign_chinese(y),
        "life_path": life_path(y,m,d),
        "tree": tree_sign(m,d),
        "time_exact": bool(time_exact),
        "time": time_exact,
        "time_bucket": time_bucket_local(time_exact, approx),
    }

def build_events(seed: str, profile: dict) -> dict:
    tarot  = ["Der Magier","Die Mäßigkeit","Die Kraft","Der Stern","Das Rad des Schicksals"]
    iching = ["Hex. 24 – Wiederkehr","Hex. 46 – Empordringen","Hex. 61 – Innere Wahrheit","Hex. 42 – Mehrung","Hex. 5 – Warten"]
    astro  = ["Saturn△MC","Mars□Merkur","Jupiter△Sonne","Venus↔Mond","Sonne☌Sonne"]
    def pick(items, salt):
        h=int(cyrb128(seed+salt),16); return items[h%len(items)]
    why = [f"Sternzeichen {profile.get('western')}",
           f"Lebenszahl {profile.get('life_path')}",
           f"Zeitfenster {profile.get('time_bucket') or 'unbekannt'}",
           f"Ort {profile.get('place')}"]
    return {"events":[
        {"key": pick(astro,"a"), "area":"Fokus",  "weight":0.7, "why":[why[0], why[3]]},
        {"key": "Lebenszahl",    "area":"Beruf",  "weight":0.5, "why":[why[1]]},
        {"key": pick(tarot,"t"), "area":"Liebe",  "weight":0.6, "why":[pick(iching,'i')]},
        {"key": pick(iching,"i"),"area":"Energie","weight":0.4, "why":[why[2]]},
    ]}

BASE_RULES = (
    "Du bist ein achtsamer, besonnener Horoskop-Autor.\n"
    "- 2 Sätze je Abschnitt, alltagstauglich.\n"
    "- Keine Heils-/Finanz-/Rechtsversprechen, keine Diagnosen.\n"
    "- Verwende konditionale Sprache (kann/könnte), biete 1 Mini-Aktion (<=5 Min).\n"
    "- Begründe Aussagen mit den gelieferten Profil-Daten/Ereignissen (Why-Chips: z. B. Sternzeichen, Lebenszahl, Zeitfenster, Ort/Zeitzone).\n"
    "- Keine AC/Häuser-Deutung ohne exakte Geburtszeit."
)
MODE_RULES = {
    "coach":   "Ton: sachlich-ermutigend, klare Mini-Schritte.",
    "mystic":  "Ton: leicht bildhaft, trotzdem konkret.",
    "skeptic": "Ton: neutral, dämpfe Gewissheiten; ergänze 1 Selbstcheck-Frage."
}

def sanitize(txt: str) -> str:
    STOP=[(r"Suizid|Selbstmord|Selbstverletz","Bei Krisen: 112 (EU) / lokale Beratungsstellen."),
          (r"Heilung|heilen|Heilmethode","Keine Heilsversprechen. Ärztlichen Rat einholen."),
          (r"Diagnose|Medikament","Keine Diagnosen. Professionelle Hilfe nutzen."),
          (r"Investment|Rendite|Gewinn garantiert","Keine Finanzversprechen. Unabhängig beraten lassen.")]
    for pat,note in STOP:
        if re.search(pat,txt,re.I):
            txt=re.sub(r".*$","Formuliere zurückhaltend, beobachtend.",txt)
            txt+=f" ({note})"
    return txt

def normalize_payload(payload:dict)->dict:
    payload.setdefault("highlights",[])
    payload.setdefault("sections",[])
    for i,sec in enumerate(payload["sections"]):
        area=sec.get("area") or AREAS[i%len(AREAS)]
        if area=="undefined": area=AREAS[i%len(AREAS)]
        sec["area"]=area
        sec["text"]=sanitize(sec.get("text",""))
        sec.setdefault("why",[])
    payload["highlights"]=payload["highlights"][:3]
    payload["sections"]=payload["sections"][:5]
    return payload

@app.get("/health")
def health(): return {"ok": True}

@app.post("/reading")
async def reading(req: Request):
    body=await req.json()
    mode=body.get("mode","coach")
    timeframe=body.get("timeframe","week")
    weights=body.get("weights",{"astro":34,"num":13,"tarot":17,"iching":14,"cn":11,"tree":11})
    inputs=body.get("inputs",{"date":"","time":None,"timeApprox":"","place":"","partnerDate":None})

    date_str=inputs.get("date","")
    place=inputs.get("place","")
    if not date_str or not place:
        return JSONResponse({"error":"date/place fehlt"}, status_code=400)

    base_profile=build_base_profile(date_str, place, inputs.get("time"), inputs.get("timeApprox"))
    geo = await geocode_place(place)
    profile={**base_profile, **({"lat": geo.get("lat"), "lon": geo.get("lon"), "timezone": geo.get("timezone")} if geo else {})}

    seed=cyrb128(json.dumps({"mode":mode,"timeframe":timeframe,"weights":weights,"profile":profile}, ensure_ascii=False))
    events=build_events(seed, profile)

    api_key=os.getenv("OPENAI_API_KEY")
    if not api_key:
        return JSONResponse({"error":"OPENAI_API_KEY fehlt"}, status_code=500)

    client=OpenAI(api_key=api_key)
    instructions=BASE_RULES+"\n"+MODE_RULES.get(mode,"")
    schema_hint=(
        "Antworte als ein einziges JSON-Objekt mit { meta, highlights, sections, ritual, disclaimer }.\n"
        "meta: { seed, mode, timeframe, locale:'de-DE', weights, profile }.\n"
        "highlights: exakt 3 Einträge mit { title, action, why: string[] }.\n"
        "sections: 3–5 Einträge mit { area: 'Fokus'|'Beruf'|'Liebe'|'Energie'|'Soziales', text, action, why:string[] }.\n"
        "ritual: { title, steps: string[] } optional.\n"
        "Formatiere nur JSON (keine Erklärtexte)."
    )
    user_data={"timeframe":timeframe,"mode":mode,"weights":weights,"profile":profile,"events":events}

    resp=client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":instructions},
            {"role":"user","content": schema_hint + "\nDaten:\n" + json.dumps(user_data, ensure_ascii=False)}
        ],
        response_format={"type":"json_object"},
        temperature=0.6, max_tokens=950
    )

    try:
        payload=json.loads(resp.choices[0].message.content)
    except Exception as e:
        return JSONResponse({"error":"LLM-Parsing fehlgeschlagen","details":str(e)}, status_code=500)

    payload.setdefault("meta",{})
    payload["meta"].update({"seed":seed,"mode":mode,"timeframe":timeframe,"locale":"de-DE","weights":weights,"profile":profile})
    payload["disclaimer"]="Unterhaltung & achtsame Selbstreflexion. Keine medizinische, rechtliche oder finanzielle Beratung."

    payload=normalize_payload(payload)
    return payload
