(function (global) {
  const API_BASE = global.HOROSKOP_API_BASE || "https://horoskopone-production.up.railway.app";
  const ENDPOINT = "/reading";

  function sanitizeTime(t) { return /^\d{1,2}:\d{2}$/.test((t||"").trim()) ? t.trim() : null; }
  function mapPeriod(ui) {
    if (!ui) return "day";
    const s = (""+ui).toLowerCase();
    if (s.includes("heute") || s === "day") return "day";
    if (s.includes("woche") || s === "week") return "week";
    return "month";
  }

  async function callReading({ birthDate, birthPlace, birthTime, approxDaypartUI, periodUI, seed, mixer }) {
    const payload = {
      birthDate: (birthDate || "").trim(),
      birthPlace: (birthPlace || "").trim(),
      birthTime: sanitizeTime(birthTime),
      approxDaypart: approxDaypartUI || "unbekannt",
      period: mapPeriod(periodUI),
      tone: "mystic_deep",
      seed: seed || Math.floor(Math.random() * 1e6),
      mixer: mixer || {}
    };
    const res = await fetch(API_BASE + ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`API ${res.status}: ${text || res.statusText}`);
    }
    return res.json();
  }

  global.HoroskopOne = Object.assign(global.HoroskopOne || {}, { callReading });
})(window);
