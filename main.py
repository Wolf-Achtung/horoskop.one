import os, json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

# ---------- CORS ----------
# Setze in Railway optional CORS_ALLOW_ORIGINS="https://horoskop.one,https://<user>.github.io"
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

# ---------- Mini-Seed & Utils ----------
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

# ---------- JSON-Schema (Structured Outputs) ----------
JSON_SCHEMA = {
    "name": "Reading",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "meta": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "seed": {"type":"string"},
                    "mode": {"enum":["mystic","coach","skeptic"]},
                    "timeframe": {"enum":["day","week","month"]},
                    "locale": {"type":"string"},
                    "weights": {
                        "type":"object",
                        "additionalProperties": False,
                        "properties": {
                            "astro":{"type":"number"}, "num":{"type":"number"},
                            "tarot":{"type":"number"}, "iching":{"type":"number"},
                            "cn":{"type":"number"},    "tree":{"type":"number"}
                        },
                        "required": ["astro","num","tarot","iching","cn","tree"]
                    },
                    "inputs": {
                        "type":"object",
                        "additionalProperties": True,
                        "properties": {
                            "date":{"type":"string"},
                            "time":{"type":["string","null"]},
                            "place":{"type":"string"},
                            "goals":{"type":"array","items":{"type":"string"}},
                            "mood":{"type":"string"},
                            "style":{"type":"string"}
                        },
                        "required": ["date","place"]
                    }
                },
                "required": ["seed","mode","timeframe","locale","weights","inputs"]
            },
            "highlights": {
                "type":"array",
                "items":{
                    "type":"object","additionalProperties":False,
                    "properties":{
                        "title":{"type":"string"},
                        "why":{"type":"array","items":{"type":"string"}},
                        "action":{"type":"string"}
                    },
                    "required":["title","why","action"]
                }
            },
            "sections": {
                "type":"array","minItems":3,"maxItems":5,
                "items":{
                    "type":"object","additionalProperties":False,
                    "properties":{
                        "area":{"enum":["Beruf","Liebe","Energie","Fokus","Soziales"]},
                        "text":{"type":"string"},
                        "why":{"type":"array","items":{"type":"string"}},
                        "action":{"type":"string"}
                    },
                    "required":["area","text","why"]
                }
            },
            "ritual": {
                "type":"object","additionalProperties":False,
                "properties":{
                    "title":{"type":"string"},
                    "steps":{"type":"array","items":{"type":"string"}}
                },
                "required":["title","steps"]
            },
            "disclaimer": {"type":"string"}
        },
        "required": ["meta","highlights","sections","ritual","disclaimer"]
    }
}

INSTRUCTIONS = (
    "Du bist ein besonnener, achtsamer Horoskop-Autor.\n"
    "Regeln:\n"
    "- Maximal 2 Sätze pro Abschnitt, konkret, alltagstauglich.\n"
    "- Keine Heils-, Finanz- oder Rechtsversprechen. Keine Diagnosen.\n"
    "- Bei sensiblen Themen: neutralisieren & Selbstreflexionsfrage anbieten.\n"
    "- Jede Sektion nach Möglichkeit mit einer kleinen Action (≤5 Min).\n"
    "- Nutze NUR die gelieferten Events/Why-Hinweise als Begründungen; keine neuen Ursachen erfinden.\n"
    "- Sprache: de-DE. Ton: gemäß 'mode'."
)

@app.post("/reading")
async def reading(req: Request):
    body = await req.json()
    mode = body.get("mode", "mystic")
    timeframe = body.get("timeframe", "day")
    weights = body.get("weights", {"astro":34,"num":13,"tarot":17,"iching":14,"cn":11,"tree":11})
    inputs  = body.get("inputs", {"date":"","time":None,"place":"","goals":[],"mood":"neutral","style":"pragmatisch"})

    seed = cyrb128(json.dumps({"mode":mode,"timeframe":timeframe,"weights":weights,"inputs":inputs}, ensure_ascii=False))
    events = build_events(seed)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error":"OPENAI_API_KEY fehlt"}

    client = OpenAI(api_key=api_key)

    # Responses API mit Structured Outputs (json_schema)
    # Referenz: Structured Outputs & API Reference. :contentReference[oaicite:2]{index=2}
    resp = client.responses.create(
        model="gpt-4o-mini",
        instructions=INSTRUCTIONS,
        input=[{
            "role":"user",
            "content": "Erzeuge ein JSON-Reading gemäß Schema. Daten:\n" +
                       json.dumps({"timeframe":timeframe,"mode":mode,"weights":weights,"inputs":inputs,"events":events}, ensure_ascii=False)
        }],
        response_format={"type":"json_schema","json_schema":JSON_SCHEMA},
        max_output_tokens=900,
        temperature=0.7
    )

    # Viele SDKs stellen .output_text bereit (Fallback unten). :contentReference[oaicite:3]{index=3}
    try:
        text = getattr(resp, "output_text", None)
        payload = json.loads(text) if text else json.loads(resp.output[0].content[0].text)
    except Exception as e:
        return {"error": f"Parsing-Fehler: {e}"}

    payload["meta"]["seed"] = seed
    payload["meta"]["locale"] = "de-DE"
    return payload
