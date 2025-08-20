/* global React, ReactDOM */
const { useState, useMemo, useEffect } = React;

const METHODS = [
  { key: "astro",  label: "Astrologie / Transite", color: "#9bb4ff" },
  { key: "num",    label: "Numerologie",           color: "#61dafb" },
  { key: "tarot",  label: "Tarot",                 color: "#ffd48a" },
  { key: "iching", label: "I-Ging",                color: "#8ef3ff" },
  { key: "cn",     label: "Chinesisch",            color: "#a5f59b" },
  { key: "tree",   label: "Baumkreis",             color: "#b3e1ff" },
];

const PRESETS = {
  Balance:  { astro:34, num:13, tarot:17, iching:14, cn:11, tree:11 },
  Rational: { astro:55, num:20, tarot: 8, iching: 7, cn: 5, tree: 5 },
  Mystisch: { astro:35, num:10, tarot:25, iching:15, cn: 8, tree: 7 },
};

const MODES = [
  { key: "mystic_coach", label: "Mystic Coach" },
  { key: "mystic", label: "Mystisch" },
  { key: "coach",  label: "Coach" },
  { key: "skeptic",label: "Skeptisch" },
];

const TIMEFRAMES = [
  { key: "day",   label: "Heute" },
  { key: "week",  label: "Woche" },
  { key: "month", label: "Monat" },
];

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

function Segmented({ label, value, onChange, options }){
  return (
    <div>
      <div className="mb-1 text-sm" style={{color:"#9fb2d9"}}>{label}</div>
      <div className="inline-flex overflow-hidden rounded-xl" style={{border:"1px solid #1a2c5a"}}>
        {options.map((opt,i)=>{
          const active = opt.value===value;
          return (
            <button key={opt.value}
              onClick={()=>onChange(opt.value)}
              className={active ? "px-3 py-1.5 text-sm" : "px-3 py-1.5 text-sm"}
              style={{background: active? "#103061":"#0c1c3e", color:"#e7ecff",
                      borderLeft: i? "1px solid #1a2c5a":"none"}} aria-pressed={active}>
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function KosmischerMixer(){
  const [mode, setMode] = useState("mystic_coach");
  const [timeframe, setTimeframe] = useState("week");
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

  useEffect(()=>{
    const detail = { mode, timeframe,
      weights: Object.fromEntries(METHODS.map(m=>[m.key, round2(weights[m.key])])) };
    window.dispatchEvent(new CustomEvent("horoskop:mixer", { detail }));
  }, [mode, timeframe, weights]);

  // Inbound sync (Heute-Shortcut etc.)
  useEffect(()=>{
    const handler = (e)=>{
      const d = e.detail || {};
      if (d.mode) setMode(d.mode);
      if (d.timeframe) setTimeframe(d.timeframe);
      if (d.weights) setWeights(d.weights);
    };
    window.addEventListener("horoskop:set", handler);
    return ()=> window.removeEventListener("horoskop:set", handler);
  }, []);

  return (
    <div className="mx-auto max-w-3xl" style={{color:"#e7ecff"}}>
      <div className="rounded-2xl p-5"
           style={{background:"linear-gradient(180deg,#0f1933,#0b1328)",border:"1px solid #1a2c5a"}}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-xl font-semibold">Kosmischer Mixer<span style={{color:"#9fb2d9"}}>™</span></h2>
          <div className="flex flex-wrap gap-2">
            {Object.keys(PRESETS).map(p=>(
              <button key={p} onClick={()=>setPreset(p)}
                className="rounded-xl px-3 py-1.5 text-sm"
                style={{background:"#0c1c3e",border:"1px solid #1a2c5a"}}>{p}</button>
            ))}
            <button onClick={()=>setPreset("Balance")}
              className="rounded-xl px-3 py-1.5 text-sm" style={{background:"#0c1c3e",border:"1px solid #1a2c5a"}}>Zurücksetzen</button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Segmented label="Ton" value={mode}
            onChange={(v)=>setMode(v)}
            options={MODES.map(m=>({value:m.key,label:m.label}))}/>
          <Segmented label="Zeitraum" value={timeframe}
            onChange={(v)=>setTimeframe(v)}
            options={TIMEFRAMES.map(t=>({value:t.key,label:t.label}))}/>
        </div>

        <div className="mt-5 flex flex-col items-center gap-6 sm:flex-row">
          <div className="flex items-center justify-center">
            <div className="h-40 w-40 rounded-full" style={{ background: gradient }} aria-label="Gewichtungs-Donut"/>
            <div className="-ml-32 h-28 w-28 rounded-full" style={{ background:"rgba(10,16,34,.95)", border:"1px solid #1a2c5a" }}/>
          </div>
          <div className="grid flex-1 grid-cols-1 gap-2 sm:grid-cols-2">
            {METHODS.map(m=>(
              <div key={m.key} className="flex items-center justify-between gap-3 rounded-xl p-3"
                   style={{background:"#0c1c3e",border:"1px solid #1a2c5a"}}>
                <div className="flex items-center gap-2">
                  <span className="inline-block h-3 w-3 rounded-full" style={{background:m.color}}></span>
                  <span className="text-sm">{m.label}</span>
                </div>
                <span className="tabular-nums text-sm" style={{color:"#bdd0ff"}}>{round2(weights[m.key])}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-5 text-sm" style={{color:"#9fb2d9"}}>Summe: <span className="tabular-nums" style={{color:"#e7ecff"}}>{total.toFixed(2)}%</span> · bleibt automatisch bei 100%</div>
      </div>
    </div>
  );
}
window.KosmischerMixer = KosmischerMixer;
