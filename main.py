import os, json, re
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

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

def pick(seed: str, items: list[str], salt: str) -> str:
    h = int(cyrb128(seed + salt), 16)
    return items[h % len(items)]

def build_events(seed: str) -> dict:
    tarot  = ["Der Magier","Die Mäßigkeit","Die Kraft","Der Stern","Das Rad des Schicksals"]
    iching = ["Hexagramm 24","Hexagramm 46","Hexagramm 61","Hexagramm 42","Hexagramm 5"]
    astro  = ["Saturn△MC","Mars□Merkur","Jupiter△Sonne","Venus↔Mond","Sonne☌Sonne"]
    return {
        "events": [
            { "key": pick(seed, astro,  "a"), "weight": 0.7, "area": "Fokus",  "window": "+3 Tage" },
            { "key": "Lebenszahl",       "weight": 0.5, "area": "Beruf",  "window": "+5 Tage" },
            { "key": pick(seed, tarot,  "t"), "weight": 0.6, "area": "Liebe",  "window": "+1 Tag" },
            { "key": pick(seed, iching, "i"), "weight": 0.4, "area": "Energie","window": "+7 Tage" },
        ]
    }

BASE_RULES = (
    "Du bist ein besonnener, achtsamer Horoskop-Autor.\n"
    "- Max 2 Sätze je Abschnitt, alltagstauglich.\n"
    "- Keine Heils-/Finanz-/Rechtsversprechen. Keine Diagnosen.\n"
    "- Bei sensiblen Themen neutralisieren + 1 Reflexionsfrage.\n"
    "- Jede Sektion wenn möglich mit 1 Mini-Aktion (≤5 Min).\n"
    "- Nutze NUR die gelieferten Events/Why als Begründungen."
)
MODE_RULES = {
    "coach":   "Ton: sachlich-ermutigend, lösungsfokussiert, konkrete Mini-Schritte.",
    "mystic":  "Ton: bildhaft-mild, trotzdem konkret; keine Esoterik-Übertreibung.",
    "skeptic": "Ton: neutral-konditional (kann/könnte), dämpfe Gewissheiten, ergänze 1 Selbstcheck-Frage."
}

STOP_HINTS = [
    (r"Suizid|Selbstmord|Selbstverletz", "Bei Krisen: 112 (EU) / lokale Beratungsstellen."),
    (r"Heilung|heilen|Heilmethode", "Keine Heilsversprechen. Sprich bei gesundheitlichen Fragen mit Ärzt:innen."),
    (r"Diagnose|Medikament", "Keine Diagnosen. Nutze professionelle Hilfe."),
    (r"Investment|Rendite|Gewinn garantiert", "Keine Finanzversprechen. Hole dir unabhängigen Rat.")
]
def sanitize(txt: str) -> str:
    for pat, note in STOP_HINTS:
        if __import__("re").search(pat, txt, flags=__import__("re").I):
            txt = __import__("re").sub(r".*$", "Formuliere zurückhaltend, beobachtend.", txt)
            txt += f" ({note})"
    return txt

from fastapi.responses import JSONResponse

@app.get("/health")
def health(): return {"ok": True}

@app.post("/reading")
async def reading(req: Request):
    body = await req.json()
    mode = body.get("mode", "coach")
    timeframe = body.get("timeframe", "day")
    weights = body.get("weights", {"astro":34,"num":13,"tarot":17,"iching":14,"cn":11,"tree":11})
    inputs  = body.get("inputs", {"date":"","time":None,"place":"","goals":[],"mood":"neutral","style":"pragmatisch"})

    seed = cyrb128(json.dumps({"mode":mode,"timeframe":timeframe,"weights":weights,"inputs":inputs}, ensure_ascii=False))
    events = build_events(seed)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return JSONResponse({"error":"OPENAI_API_KEY fehlt"}, status_code=500)

    client = OpenAI(api_key=api_key)

    instructions = BASE_RULES + "\n" + MODE_RULES.get(mode, "")
    user_data = {"timeframe": timeframe, "mode": mode, "weights": weights, "inputs": inputs, "events": events}

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content": instructions},
            {"role":"user","content":
                "Erzeuge ein JSON-Reading mit Feldern meta, highlights, sections, ritual, disclaimer. "
                "meta: seed, mode, timeframe, locale, weights, inputs. "
                "sections: 3-5 Einträge aus {Beruf, Liebe, Energie, Fokus, Soziales}, je 2 Sätze + ggf. Aktion. "
                "Highlights: 3 Einträge (title, why[], action). Nutze diese Daten:\n" + json.dumps(user_data, ensure_ascii=False)}
        ],
        response_format={"type":"json_object"},
        temperature=0.7,
        max_tokens=900
    )

    payload = json.loads(resp.choices[0].message.content)
    payload.setdefault("meta", {})
    payload["meta"]["seed"] = seed
    payload["meta"]["mode"] = mode
    payload["meta"]["timeframe"] = timeframe
    payload["meta"]["locale"] = "de-DE"
    payload["meta"]["weights"] = weights
    payload["meta"]["inputs"] = inputs

    for sec in payload.get("sections", []):
        sec["text"] = sanitize(sec.get("text",""))
    payload["disclaimer"] = "Unterhaltung & achtsame Selbstreflexion. Keine medizinische, rechtliche oder finanzielle Beratung."

    return payload
