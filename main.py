import os, json, re
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request

LONGFORM_INSTRUCTIONS = (
    'Schreibe pro Bereich (Fokus, Beruf, Liebe, Energie, Soziales) einen Absatz mit 3–4 wohlklingenden Sätzen im Modus {mode}. '
    'Schließe mit einem sanften Handlungshinweis als Teil des Fließtextes (realistisch in 1–5 Minuten). '
    'Achtsam, poetisch, seriös; keine Heilsversprechen; klare Bilder; Begründungen nur andeuten.'
)
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

# ------------------------- Utilities -------------------------

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

def bucket_midpoint_h(approx: Optional[str]) -> int:
    mapping={"morning":8,"noon":13,"evening":19,"night":1}
    return mapping.get(approx or "", 12)

def hemisphere(lat: Optional[float]) -> str:
    if lat is None: return ""
    return "north" if lat >= 0 else "south"

def season_of(date_str: str, hemi: str) -> str:
    dt=datetime.strptime(date_str, "%Y-%m-%d")
    m=dt.month
    north = {12:"winter",1:"winter",2:"winter",3:"spring",4:"spring",5:"spring",6:"summer",7:"summer",8:"summer",9:"autumn",10:"autumn",11:"autumn"}
    south = {12:"summer",1:"summer",2:"summer",3:"autumn",4:"autumn",5:"autumn",6:"winter",7:"winter",8:"winter",9:"spring",10:"spring",11:"spring"}
    return (north if hemi=="north" else south).get(m,"")

# ------------------------- External data -------------------------

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

async def sunrise_sunset(client: httpx.AsyncClient, lat: float, lon: float, date_str: str, tz: Optional[str]) -> Dict[str, Optional[str]]:
    try:
        r=await client.get("https://api.open-meteo.com/v1/forecast",
                           params={"latitude":lat,"longitude":lon,"daily":"sunrise,sunset,moon_phase",
                                   "timezone":tz or "auto","start_date":date_str,"end_date":date_str})
        if r.status_code==200:
            j=r.json()
            sr=(j.get("daily",{}).get("sunrise") or [None])[0]
            ss=(j.get("daily",{}).get("sunset")  or [None])[0]
            mp=(j.get("daily",{}).get("moon_phase") or [None])[0]
            return {"sunrise": sr, "sunset": ss, "moon_phase": mp}
    except Exception:
        pass
    return {"sunrise": None, "sunset": None, "moon_phase": None}

def moon_phase_name(val: Optional[float]) -> str:
    if val is None: return ""
    # Open-Meteo uses 0.0=new, 0.25=first quarter, 0.5=full, 0.75=last quarter
    v=float(val)%1.0
    if v<0.03 or v>0.97: return "Neumond"
    if 0.22<=v<=0.28: return "Erstes Viertel"
    if 0.47<=v<=0.53: return "Vollmond"
    if 0.72<=v<=0.78: return "Letztes Viertel"
    if 0.03<=v<0.22: return "zunehmend (Sichel)"
    if 0.28<v<0.47:  return "zunehmend (bauchig)"
    if 0.53<v<0.72:  return "abnehmend (bauchig)"
    return "abnehmend (Sichel)"

# ------------------------- Profile & Events -------------------------

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
           f"Ort {profile.get('place')}",
           f"Tag/Nacht: {'Tag' if profile.get('birth_is_day') else 'Nacht'}",
           f"Saison: {profile.get('season')} ({'Nord' if profile.get('hemisphere')=='north' else 'Süd'}-Halbkugel)",
           f"Mondphase: {profile.get('moon_phase_name') or ''}"]
    return {"events":[
        {"key": pick(astro,"a"), "area":"Fokus",  "weight":0.7, "why":[why[0], why[3], why[5]]},
        {"key": "Lebenszahl",    "area":"Beruf",  "weight":0.5, "why":[why[1]]},
        {"key": pick(tarot,"t"), "area":"Liebe",  "weight":0.6, "why":[why[6] or why[2]]},
        {"key": pick(iching,"i"),"area":"Energie","weight":0.4, "why":[why[4]]},
    ]}

# ------------------------- Guardrails -------------------------

BASE_RULES = (
    "Du bist ein achtsamer, besonnener Horoskop-Autor.\n"
    "- 2 Sätze je Abschnitt, alltagstauglich.\n"
    "- Keine Heils-/Finanz-/Rechtsversprechen, keine Diagnosen.\n"
    "- Verwende konditionale Sprache (kann/könnte), biete 1 Mini-Aktion (<=5 Min).\n"
    "- Begründe Aussagen mit den gelieferten Profil-Daten/Ereignissen (Why-Chips: z. B. Sternzeichen, Lebenszahl, Zeitfenster, Ort/Zeitzone, Tag/Nacht, Saison/Hemisphäre, Mondphase).\n"
    "- Keine AC/Häuser-Deutung ohne exakte Geburtszeit."
)
MODE_RULES = {
    "coach":        "Ton: sachlich-ermutigend, klare Mini-Schritte.",
    "mystic":       "Ton: leicht bildhaft, trotzdem konkret.",
    "mystic_coach": "Ton: ruhig-ermutigend mit leicht mystischem Flair; klare Mini-Schritte; seriös und knapp.",
    "mystic_deep":  "Ton: poetisch-ruhig, deutlich mystischer; sanfte Metaphern, zwei Sätze pro Abschnitt, klare Mini-Aktion; keine Heilsversprechen.",
    "skeptic":      "Ton: neutral, dämpfe Gewissheiten; ergänze 1 Selbstcheck-Frage."
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

# ------------------------- API -------------------------

@app.get("/health")
def health(): return {"ok": True}

@app.post("/reading")
async def reading(req: Request):
    body=await req.json()
    mode=body.get("mode","mystic_deep")
    timeframe=body.get("timeframe","week")
    weights=body.get("weights",{"astro":34,"num":13,"tarot":17,"iching":14,"cn":11,"tree":11})
    inputs=body.get("inputs",{"date":"","time":None,"timeApprox":"","place":"","partnerDate":None})

    date_str=inputs.get("date","")
    place=inputs.get("place","")
    if not date_str or not place:
        return JSONResponse({"error":"date/place fehlt"}, status_code=400)

    # Base profile
    profile = build_base_profile(date_str, place, inputs.get("time"), inputs.get("timeApprox"))

    # Geo + timezone + sunrise/sunset + moon phase
    headers={"user-agent":"horoskop.one/1.0 (contact@horoskop.one)"}
    async with httpx.AsyncClient(timeout=12.0, headers=headers) as client:
        geo = await geocode_place(place)
        if geo:
            profile.update({"lat": geo.get("lat"), "lon": geo.get("lon"), "timezone": geo.get("timezone")})
            ss = await sunrise_sunset(client, geo["latitude"] if "latitude" in geo else geo["lat"],
                                      geo["longitude"] if "longitude" in geo else geo["lon"],
                                      date_str, geo.get("timezone"))
            profile.update(ss)
            # Day/Night + Season
            hemi = hemisphere(profile.get("lat"))
            profile["hemisphere"] = hemi
            profile["season"] = season_of(date_str, hemi)
            # Determine day/night at birth time (local)
            time_str = profile.get("time")
            if not time_str and profile.get("time_bucket"):
                hour = bucket_midpoint_h(profile.get("time_bucket"))
                time_str = f"{hour:02d}:00"
            def to_minutes(s):
                try:
                    t=s.split("T")[1] if "T" in s else s
                    hh,mm=t.split(":")[:2]
                    return int(hh)*60+int(mm)
                except Exception:
                    return None
            if time_str and profile.get("sunrise") and profile.get("sunset"):
                tm = to_minutes(time_str)
                sr = to_minutes(profile["sunrise"])
                ss2 = to_minutes(profile["sunset"])
                if tm is not None and sr is not None and ss2 is not None:
                    profile["birth_is_day"] = bool(sr <= tm < ss2)
            # Moon phase name
            profile["moon_phase_name"] = moon_phase_name(profile.get("moon_phase"))
        else:
            # still provide hemisphere/season if place unparsable: guess via None
            profile["hemisphere"] = ""
            profile["season"] = ""

    # Seed and events
    seed=cyrb128(json.dumps({"mode":mode,"timeframe":timeframe,"weights":weights,"profile":profile}, ensure_ascii=False))
    events=build_events(seed, profile)

    api_key=os.getenv("OPENAI_API_KEY")
    if not api_key:
        return JSONResponse({"error":"OPENAI_API_KEY fehlt"}, status_code=500)

    client_oa=OpenAI(api_key=api_key)

    # -------- Pass 1: Outline --------
    outline_instructions = (
        BASE_RULES + "\n" + MODE_RULES.get(mode,"") + "\n"
        "Erzeuge zunächst eine **Outline** als JSON-Objekt mit:\n"
        "{ outline: { highlights: [{title, why:string[]}], sections:[{area, intention, reasons:string[], action_hint}], ritual:{idea} } }\n"
        "- Nutze **nur** Gründe aus den gelieferten Daten (profile/events/weights/mini-ephemeriden).\n"
        "- Bereiche nur aus: 'Fokus','Beruf','Liebe','Energie','Soziales'.\n"
        "- Keine Häuser/Aszendent ohne exakte Zeit.\n"
        "- Keine Heils-/Finanz-/Rechtsversprechen.\n"
        "Formatiere **nur JSON**."
    )
    data_blob={"timeframe":timeframe,"mode":mode,"weights":weights,"profile":profile,"events":events}
    outline_resp = client_oa.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":outline_instructions},
            {"role":"user","content": json.dumps(data_blob, ensure_ascii=False)}
        ],
        response_format={"type":"json_object"},
        temperature=0.5, max_tokens=800
    )
    try:
        outline_json = json.loads(outline_resp.choices[0].message.content)
        outline = outline_json.get("outline", outline_json)
    except Exception as e:
        outline = {"highlights":[],"sections":[],"ritual":{"idea":""}}

    # -------- Pass 2: Final text --------
    final_instructions = (
        BASE_RULES + "\n" + MODE_RULES.get(mode,"") + "\n"
        "Du bekommst eine Outline. Schreibe daraus die **endgültige Ausgabe** als JSON-Objekt mit:\n"
        "{ meta, highlights, sections, ritual, disclaimer }\n"
        "meta: { seed, mode, timeframe, locale:'de-DE', weights, profile, ephemeris: { moon_phase, moon_phase_name, sunrise, sunset, season, hemisphere, birth_is_day } }\n"
        "highlights: exakt 3 Einträge mit { title, action, why:string[] } (kurz, konkret).\n"
        "sections: 3–5 Einträge mit { area, text (genau 2 Sätze), action, why:string[] }.\n"
        "ritual: { title, steps:string[] } (2–4 Mini-Schritte, <=5 Min).\n"
        "Nutze **nur** Gründe aus Outline und gelieferten Fakten.\n"
        "Formatiere **nur JSON**."
    )
    ephem = {
        "moon_phase": profile.get("moon_phase"),
        "moon_phase_name": profile.get("moon_phase_name"),
        "sunrise": profile.get("sunrise"),
        "sunset": profile.get("sunset"),
        "season": profile.get("season"),
        "hemisphere": profile.get("hemisphere"),
        "birth_is_day": profile.get("birth_is_day", None),
    }
    final_data = {
        "seed": seed, "mode": mode, "timeframe": timeframe, "weights": weights, "profile": profile,
        "ephemeris": ephem, "outline": outline
    }
    final_resp = client_oa.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content": final_instructions},
            {"role":"user","content": json.dumps(final_data, ensure_ascii=False)}
        ],
        response_format={"type":"json_object"},
        temperature=0.6, max_tokens=1100
    )

    try:
        payload=json.loads(final_resp.choices[0].message.content)
    except Exception as e:
        return JSONResponse({"error":"LLM-Parsing fehlgeschlagen (final)","details":str(e)}, status_code=500)

    # Patch meta + disclaimer + normalization
    payload.setdefault("meta",{})
    payload["meta"].update({"seed":seed,"mode":mode,"timeframe":timeframe,"locale":"de-DE","weights":weights,
                            "profile":profile, "ephemeris": ephem})
    payload["disclaimer"]="Unterhaltung & achtsame Selbstreflexion. Keine medizinische, rechtliche oder finanzielle Beratung."
    payload=normalize_payload(payload)
    return payload


from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

@app.get("/og")
def og_image(title: str = "horoskop.one", subtitle: str = "Mystischer Kompass", place: str = "", tf: str = "", moon: str = "", seed: int = 0):
    random.seed(seed or 12345)
    W,H = 1200,630
    img = Image.new("RGB",(W,H),(11,16,32))
    drw = ImageDraw.Draw(img)

    # gradient
    for y in range(H):
        t = y/H
        col = (int(11+(t*30)), int(16+(t*40)), int(32+(t*60)))
        drw.line([(0,y),(W,y)], fill=col)

    # subtle stars
    for _ in range(220):
        x = random.randint(0,W-1); y = random.randint(0,H-1)
        drw.point((x,y), fill=(230,235,255))

    # title/sub
    try:
        f_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 52)
        f_sub   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        f_chip  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except:
        f_title = f_sub = f_chip = ImageFont.load_default()

    drw.text((56,76), title, font=f_title, fill=(231,236,255))
    drw.text((56,112), subtitle, font=f_sub, fill=(159,178,217))

    # Chips row
    x=56; y=150
    def chip(txt):
        nonlocal x
        pad=10
        tw,th = drw.textsize(txt,font=f_chip)
        w = tw + pad*2; h = 28
        drw.rounded_rectangle((x,y,w+x,h+y), radius=14, outline=(42,63,121), fill=(13,32,63))
        drw.text((x+pad,y+6), txt, font=f_chip, fill=(187,208,255))
        x += w + 10
    if place: chip("📍 "+place)
    if tf:    chip("🕰 "+tf)
    if moon:  chip("☾ "+moon)

    # Footer
    drw.text((56,600),"horoskop.one • mystischer Kompass", font=f_sub, fill=(126,150,201))

    b=BytesIO(); img.save(b, format="PNG"); b.seek(0)
    from fastapi.responses import Response
    return Response(content=b.read(), media_type="image/png")

@app.get("/version")
def version():
    return {"version":"5.4-longform","default_mode":"mystic_deep","notes":"3-4 Saetze pro Sektion, integrierter Hinweis"}
