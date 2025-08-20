# swe_worker.py — Swiss Ephemeris Worker (Option C) — v1.0
# Python 3.11  |  FastAPI + pyswisseph  | Railway/Nixpacks
# Liefert Asc/MC, Häuserspitzen, Sonnen-/Mondhaus.

import os
import datetime as dt
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from zoneinfo import ZoneInfo

import swisseph as swe

app = FastAPI(title="SWE Worker", version="v1.0")

raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
origins = [o.strip() for o in raw_origins.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ZOD_SIGNS = ["Widder","Stier","Zwillinge","Krebs","Löwe","Jungfrau",
             "Waage","Skorpion","Schütze","Steinbock","Wassermann","Fische"]

def sign_from_deg(lon_deg: float) -> str:
    i = int((lon_deg % 360.0) // 30)
    return ZOD_SIGNS[i]

class SWERequest(BaseModel):
    birthDate: str
    birthTime: str
    lat: float
    lon: float
    tzname: str
    houseSystem: str = Field(default="P", description="P=Placidus, K=Koch, ...")

    @field_validator("birthDate")
    @classmethod
    def _valid_date(cls, v: str) -> str:
        # require YYYY-MM-DD
        try:
            dt.date.fromisoformat(v)
        except Exception:
            raise ValueError("birthDate must be ISO YYYY-MM-DD")
        return v

    @field_validator("birthTime")
    @classmethod
    def _valid_time(cls, v: str) -> str:
        # require HH:MM
        try:
            hh, mm = v.split(":")
            h, m = int(hh), int(mm)
        except Exception:
            raise ValueError("birthTime must be HH:MM")
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("birthTime must be HH:MM 00-23:00-59")
        return v

    @field_validator("houseSystem")
    @classmethod
    def _valid_house(cls, v: str) -> str:
        return (v or "P").strip()[:1]

class SWEResponse(BaseModel):
    houseSystem: str
    ascendant: Dict[str, float | str]
    mc: Dict[str, float | str]
    cusps: List[float]
    sunHouse: Optional[int] = None
    moonHouse: Optional[int] = None

@app.get("/health")
def health():
    return {"ok": True, "engine": "pyswisseph", "version": getattr(swe, "__version__", "unknown")}

def house_of(cusps: List[float], lon_val: float) -> Optional[int]:
    L = lon_val % 360.0
    for i in range(12):
        a = cusps[i] % 360.0
        b = cusps[(i+1) % 12] % 360.0
        if a <= b:
            if a <= L < b:
                return i + 1
        else:
            if L >= a or L < b:
                return i + 1
    return None

@app.post("/swe", response_model=SWEResponse)
def swe_compute(req: SWERequest = Body(...)):
    # Local time with timezone -> UTC -> julian day
    d = dt.date.fromisoformat(req.birthDate)
    hh, mm = req.birthTime.split(":")
    loc = dt.datetime(d.year, d.month, d.day, int(hh), int(mm), tzinfo=ZoneInfo(req.tzname))
    ut = loc.astimezone(dt.timezone.utc)
    ut_hour = ut.hour + ut.minute/60 + ut.second/3600
    jd = swe.julday(ut.year, ut.month, ut.day, ut_hour)

    hcusps, ascmc = swe.houses(jd, req.lat, req.lon, req.houseSystem[:1] or "P")
    # pyswisseph liefert 13 Werte, Index 1..12 sind die 12 Häuserspitzen
    cusps = [hcusps[i] for i in range(1, 13)]

    asc, mc = ascmc[0], ascmc[1]

    # Sonnen-/Mondposition
    sun_lon = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)[0][0]
    moon_lon = swe.calc_ut(jd, swe.MOON, swe.FLG_SWIEPH)[0][0]

    sun_house = house_of(cusps, sun_lon)
    moon_house = house_of(cusps, moon_lon)

    return SWEResponse(
        houseSystem=req.houseSystem[:1] or "P",
        ascendant={"deg": asc, "sign": sign_from_deg(asc)},
        mc={"deg": mc, "sign": sign_from_deg(mc)},
        cusps=cusps,
        sunHouse=sun_house,
        moonHouse=moon_house,
    )
