/* global React, ReactDOM */
const { useState, useMemo, useEffect } = React;

// ——— Daten ———
const METHODS = [
  { key: "astro",  label: "Astrologie / Transite", color: "#d4af37" },
  { key: "num",    label: "Numerologie",           color: "#6366f1" },
  { key: "tarot",  label: "Tarot",                 color: "#ef4444" },
  { key: "iching", label: "I-Ging",                color: "#10b981" },
  { key: "cn",     label: "Chinesisch",            color: "#f59e0b" },
  { key: "tree",   label: "Baumkreis",             color: "#14b8a6" },
];

const PRESETS = {
  Balance:  { astro:34, num:13, tarot:17, iching:14, cn:11, tree:11 },
  Rational: { astro:55, num:20, tarot: 8, iching: 7, cn: 5, tree: 5 },
  Mystisch: { astro:35, num:10, tarot:25, iching:15, cn: 8, tree: 7 },
};

const MODES = [
  { key: "mystic", label: "Mystisch" },
  { key: "coach",  label: "Coach" },
  { key: "skeptic",label: "Skeptisch" },
];

const TIMEFRAMES = [
  { key: "day",   label: "Heute" },
  { key: "week",  label: "Woche" },
  { key: "month", label: "Monat" },
];

// ——— Utils ———
const clamp = (n, min=0, max=100) => Math.max(min, Math.min(max, n));
const round2 = (n) => Math.round(n*100)/100;
const sumValues = (obj) => Object.values(obj).reduce((a,b)=>a+b,0);

function rebalance(prev, changedKey, newVal){
  const next = { ...prev, [changedKey]: clamp(newVal) };
  const keys = Object.keys(next);
  const others = keys.filter(k=>k!==changedKey);
  const rest = 100 - next[changedKey];
  const sumOthers = others.reduce((acc,k)=>acc+(prev[k]||0),0);
  if (sumOthers <= 0) {
    const even = rest/others.length;
    others.forEach(k=> next[k]=even);
    return next;
  }
  others.forEach(k=>{
    const share = prev[k]/sumOthers;
    next[k] = rest * share;
  });
  return next;
}

function toGradient(weights){
  let acc=0, stops=[];
  METHODS.forEach(({key,color})=>{
    const pct = clamp(weights[key]||0);
    if (pct<=0) return;
    const start=acc, end=acc+pct;
    stops.push(`${color} ${start}% ${end}%`);
    acc=end;
  });
  if (!stops.length) stops.push(`#e5e7eb 0% 100%`);
  return `conic-gradient(${stops.join(", ")})`;
}

// ——— Segmented Control ———
function Segmented({ label, value, onChange, options }){
  return (
    <div>
      <div className="mb-1 text-sm" style={{color:"#cbd5e1"}}>{label}</div>
      <div className="inline-flex overflow-hidden rounded-xl" style={{border:"1px solid rgba(255,255,255,.1)"}}>
        {options.map((opt,i)=>{
          const active = opt.value===value;
          return (
            <button key={opt.value}
              onClick={()=>onChange(opt.value)}
              className={active ? "px-3 py-1.5 text-sm bg-amber-400/90 text-black"
                                : "px-3 py-1.5 text-sm bg-white/5 text-slate-200 hover:bg-white/10"}
              style={i?{borderLeft:"1px solid rgba(255,255,255,.1)"}:{}}
              aria-pressed={active}>
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ——— Hauptkomponente ———
function KosmischerMixer(){
  const [mode, setMode] = useState("mystic");
  const [timeframe, setTimeframe] = useState("day");
  const [copied, setCopied] = useState(false);
  const [weights, setWeights] = useState({ ...PRESETS.Balance });

  const total = useMemo(()=>round2(sumValues(weights)),[weights]);
  const gradient = useMemo(()=>toGradient(weights),[weights]);

  const setPreset = (name) => {
    const preset = PRESETS[name];
    if (!preset) return;
    const next = { ...preset };
    const s = sumValues(next);
    const factor = s>0 ? 100/s : 0;
    Object.keys(next).forEach(k=> next[k]=round2(next[k]*factor));
    setWeights(next);
  };

  const onChangeWeight = (key,val) => setWeights(rebalance(weights, key, val));

  const onCopy = async () => {
    const payload = { mode, timeframe,
      weights: Object.fromEntries(METHODS.map(m=>[m.key, round2(weights[m.key])]))
    };
    try {
      await navigator.clipboard.writeText(JSON.stringify(payload,null,2));
      setCopied(true); setTimeout(()=>setCopied(false),1200);
    } catch {}
  };

  // Mixer-Status nach außen funken (Seite hört auf "horoskop:mixer")
  useEffect(()=>{
    const detail = { mode, timeframe,
      weights: Object.fromEntries(METHODS.map(m=>[m.key, round2(weights[m.key])])) };
    window.dispatchEvent(new CustomEvent("horoskop:mixer", { detail }));
  }, [mode, timeframe, weights]);

  return (
    <div className="mx-auto max-w-3xl p-4" style={{color:"#e5e7eb"}}>
      <div className="rounded-2xl p-6 shadow-xl"
           style={{background:"linear-gradient(180deg,#0b1020,#000)",border:"1px solid rgba(255,255,255,.08)"}}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-2xl font-semibold">Kosmischer Mixer<span className="text-slate-400">™</span></h2>
          <div className="flex flex-wrap gap-2">
            {Object.keys(PRESETS).map(p=>(
              <button key={p} onClick={()=>setPreset(p)}
                className="rounded-xl border bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10"
                style={{borderColor:"rgba(255,255,255,.1)"}}>{p}</button>
            ))}
            <button onClick={()=>setPreset("Balance")}
              className="rounded-xl border bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10"
              style={{borderColor:"rgba(255,255,255,.1)"}}>Zurücksetzen</button>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Segmented label="Ton" value={mode}
            onChange={(v)=>setMode(v)}
            options={MODES.map(m=>({value:m.key,label:m.label}))}/>
          <Segmented label="Zeitraum" value={timeframe}
            onChange={(v)=>setTimeframe(v)}
            options={TIMEFRAMES.map(t=>({value:t.key,label:t.label}))}/>
        </div>

        <div className="mt-6 flex flex-col items-center gap-6 sm:flex-row">
          <div className="flex items-center justify-center">
            <div className="h-40 w-40 rounded-full" style={{ background: gradient }} aria-label="Gewichtungs-Donut"/>
            <div className="-ml-32 h-28 w-28 rounded-full" style={{ background:"rgba(0,0,0,.9)", border:"1px solid rgba(255,255,255,.1)" }}/>
          </div>
          <div className="grid flex-1 grid-cols-1 gap-2 sm:grid-cols-2">
            {METHODS.map(m=>(
              <div key={m.key} className="flex items-center justify-between gap-3 rounded-xl p-3"
                   style={{background:"rgba(255,255,255,.05)",border:"1px solid rgba(255,255,255,.1)"}}>
                <div className="flex items-center gap-2">
                  <span className="inline-block h-3 w-3 rounded-full" style={{background:m.color}}></span>
                  <span className="text-sm text-slate-200">{m.label}</span>
                </div>
                <span className="tabular-nums text-sm text-slate-300">{round2(weights[m.key])}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4">
          {METHODS.map(m=>(
            <div key={m.key} className="rounded-2xl p-4"
                 style={{background:"rgba(255,255,255,.05)",border:"1px solid rgba(255,255,255,.1)"}}>
              <label htmlFor={`slider-${m.key}`} className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2">
                  <span className="inline-block h-3 w-3 rounded-full" style={{background:m.color}}></span>{m.label}
                </span>
                <span className="tabular-nums text-slate-300">{round2(weights[m.key])}%</span>
              </label>
              <input id={`slider-${m.key}`} type="range" min="0" max="100" step="1"
                value={Math.round(weights[m.key])}
                onChange={(e)=>onChangeWeight(m.key, Number(e.target.value))}
                className="mt-2 w-full cursor-pointer accent-amber-400"
                aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(weights[m.key])}/>
            </div>
          ))}
        </div>

        <div className="mt-6 flex flex-col items-center justify-between gap-3 sm:flex-row">
          <div className="text-sm text-slate-400">Summe: <span className="tabular-nums font-medium text-slate-200">
            {total.toFixed(2)}%</span> · bleibt automatisch bei 100%</div>
          <div className="flex items-center gap-2">
            <button onClick={onCopy}
              className="rounded-xl bg-amber-400/90 px-4 py-2 text-sm font-medium text-black shadow hover:bg-amber-300">
              JSON kopieren
            </button>
          </div>
        </div>

        {copied && (
          <div role="status" className="mt-3 rounded-xl p-3 text-center"
               style={{background:"rgba(16,185,129,.1)", color:"#6ee7b7", border:"1px solid rgba(16,185,129,.3)"}}>
            JSON in die Zwischenablage kopiert ✓
          </div>
        )}
      </div>
      <p className="mt-4 text-xs" style={{color:"#94a3b8"}}>
        Tipp: „Rational“ → sachlicher; „Mystisch“ → erzählerischer. Ton & Zeitraum fließen später in die LLM-Pipeline ein.
      </p>
    </div>
  );
}

// global verfügbar machen
window.KosmischerMixer = KosmischerMixer;
