import { useEffect, useState } from "react";
import { api, type StudioMeta, type StudioPlan, type StudioProject } from "../api";

const LOOK_LABEL = (l: string) => (l.startsWith("file:") ? `My LUT: ${l.slice(5).replace(/\.cube$/, "")}` : l.replace(/_/g, " "));
const COLORS = ["red", "orange", "yellow", "green", "cyan", "blue", "purple", "magenta"];
const ADJ: [string, string, number, number, number][] = [
  ["exposure", "Exposure (stops)", -1, 1, 0.05], ["contrast", "Contrast", -100, 100, 1], ["highlights", "Highlights", -100, 100, 1],
  ["shadows", "Shadows", -100, 100, 1], ["lights", "Whites", -100, 100, 1], ["darks", "Blacks", -100, 100, 1],
  ["brightness", "Brightness", -100, 100, 1], ["temp", "Temperature", -100, 100, 1], ["tint", "Tint", -100, 100, 1],
  ["sat", "Saturation", -100, 100, 1], ["vibrance", "Vibrance", -100, 100, 1], ["fade", "Fade", 0, 100, 1],
];
const FX: [string, string][] = [["sharpen", "Sharpen"], ["clarity", "Clarity"], ["vignette", "Vignette"], ["grain", "Grain"]];

/** Ein Regler wie in CapCut: Schieber + Zahl + Zurücksetzen. Speichert beim Loslassen. */
function Knob({ label, value, min, max, step, onCommit }: {
  label: string; value: number; min: number; max: number; step: number; onCommit: (v: number | null) => void;
}) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  return (
    <label className="vs-knob">
      <span>{label}</span>
      <input type="range" min={min} max={max} step={step} value={v} onChange={(e) => setV(Number(e.target.value))}
        onPointerUp={() => onCommit(v)} onKeyUp={() => onCommit(v)} />
      <input type="number" min={min} max={max} step={step} value={v} onChange={(e) => setV(Number(e.target.value))} onBlur={() => onCommit(v)} />
      <button type="button" title="reset" onClick={() => { setV(0); onCommit(null); }}>↺</button>
    </label>
  );
}

/** Bearbeiten einer Aufnahme: Farbe, HSL, Effekte, Ausschnitt/Zoom, Filter mit Vorschau, Texte. */
export function ShotPanel({ sid, fmt, k, plan, st, meta, onState, onErr }: {
  sid: string; fmt: string; k: number; plan: StudioPlan; st: StudioProject; meta: StudioMeta;
  onState: (s: StudioProject) => void; onErr: (m: string) => void;
}) {
  const [tab, setTab] = useState<"filters" | "adjust" | "hsl" | "effects" | "frame" | "text">("filters");
  const [looks, setLooks] = useState<{ look: string; file: string }[]>([]);
  const [strength, setStrength] = useState(1);
  const [compare, setCompare] = useState(50);
  const [hover, setHover] = useState<string | null>(null);
  const [tpl, setTpl] = useState("location_pin");
  const [txt, setTxt] = useState(st.settings.location || "");
  const sh = plan.shots[k];
  const adj = (sh.adjust ?? {}) as Record<string, number>;
  const fx = (sh.fx ?? {}) as Record<string, number | boolean>;
  const thumb = api.studioShotThumb(sid, fmt, k, `${sh.clip}${sh.src_in}`);

  const send = async (action: string, value?: string | number | Record<string, unknown>) => {
    try { onState(await api.studioShot(sid, fmt, k, action, value)); } catch (e) { onErr((e as Error).message); }
  };
  const setAdj = (key: string, v: number | null) => {
    const next: Record<string, unknown> = { ...adj };
    if (v === null || v === 0) delete next[key]; else next[key] = v;
    void send("set", { adjust: next });
  };
  const setDict = (dictKey: "sat_by" | "hue_shift", color: string, v: number | null) => {
    const cur = { ...((sh.adjust?.[dictKey] as Record<string, number>) ?? {}) };
    if (v === null || v === 0) delete cur[color]; else cur[color] = v;
    void send("set", { adjust: { ...adj, [dictKey]: cur } });
  };
  const setFx = (key: string, v: number | boolean | null) => {
    const next: Record<string, unknown> = { ...fx };
    if (v === null || v === 0 || v === false) delete next[key]; else next[key] = v;
    void send("set", { fx: next });
  };
  useEffect(() => {
    if (tab !== "filters") return;
    api.studioLooks(sid, fmt, k, strength).then((r) => setLooks(r.looks)).catch((e) => onErr(e.message));
  }, [sid, fmt, k, strength, tab, st.settings.grade.look]);
  const current = sh.look ?? st.settings.grade.look;
  const shown = looks.find((l) => l.look === (hover ?? current));

  return (
    <div className="vs-panel small">
      <div className="vs-panel-head">
        <strong>Shot {k + 1}</strong>
        <span className="seg">
          {(["filters", "adjust", "hsl", "effects", "frame", "text"] as const).map((t) => (
            <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
              {{ filters: "Filters", adjust: "Adjust", hsl: "HSL", effects: "Effects", frame: "Crop & zoom", text: "Text" }[t]}
            </button>
          ))}
        </span>
        <button className="link" onClick={() => send("apply_all")}>apply colour + effects of this shot to all shots</button>
      </div>

      {tab === "filters" && (
        <div className="vs-filters">
          <div className="vs-compare" title="drag the slider: left = original, right = with filter">
            <img src={thumb} alt="original" />
            {shown && <img className="after" src={api.studioFile(sid, "looks", shown.file)} alt="with filter" style={{ clipPath: `inset(0 0 0 ${compare}%)` }} />}
            <input type="range" min={0} max={100} value={compare} onChange={(e) => setCompare(Number(e.target.value))} />
            <span className="muted">before ◀ ▶ after: {LOOK_LABEL(hover ?? current)}</span>
          </div>
          <label className="vs-knob"><span>Strength {Math.round(strength * 100)} %</span>
            <input type="range" min={0} max={1.5} step={0.05} value={strength} onChange={(e) => setStrength(Number(e.target.value))} />
          </label>
          <div className="vs-look-grid">
            {looks.map((l) => (
              <button key={l.look} className={`vs-look ${l.look === current ? "on" : ""}`} onMouseEnter={() => setHover(l.look)} onMouseLeave={() => setHover(null)}
                onClick={() => send("set", { look: l.look, strength })}>
                <img src={api.studioFile(sid, "looks", l.file)} alt={l.look} loading="lazy" />
                <span>{LOOK_LABEL(l.look)}</span>
              </button>
            ))}
          </div>
          <div className="row-buttons">
            <button className="link" onClick={() => send("set", { look: "", strength: "" })}>use the project look for this shot</button>
            <label className="btn ghost small-btn">Import .cube LUT
              <input type="file" accept=".cube" hidden onChange={async (e) => {
                const f = e.target.files?.[0]; e.target.value = "";
                if (f) { try { onState(await api.studioLut(sid, f)); setLooks([]); setStrength(strength + 0); } catch (er) { onErr((er as Error).message); } }
              }} />
            </label>
          </div>
        </div>
      )}

      {tab === "adjust" && (
        <div className="vs-knobs">
          {sh.auto?.exposure ? <p className="muted">Auto-match brightened/darkened this shot by {sh.auto.exposure.toFixed(2)} stops (switch off under Style).</p> : null}
          {ADJ.map(([key, label, mn, mx, stp]) => (
            <Knob key={key} label={label} value={Number(adj[key] ?? 0)} min={mn} max={mx} step={stp} onCommit={(v) => setAdj(key, v)} />
          ))}
        </div>
      )}

      {tab === "hsl" && (
        <div className="vs-knobs">
          {COLORS.map((c) => (
            <div key={c} className="vs-hsl">
              <span className={`vs-dot c-${c}`} /> {c}
              <Knob label="saturation" value={Number((sh.adjust?.sat_by as Record<string, number>)?.[c] ?? 0)} min={-100} max={100} step={1} onCommit={(v) => setDict("sat_by", c, v)} />
              <Knob label="hue" value={Number((sh.adjust?.hue_shift as Record<string, number>)?.[c] ?? 0)} min={-30} max={30} step={1} onCommit={(v) => setDict("hue_shift", c, v)} />
            </div>
          ))}
        </div>
      )}

      {tab === "effects" && (
        <div className="vs-knobs">
          {FX.map(([key, label]) => (
            <Knob key={key} label={`${label} (this shot)`} value={Number(fx[key] ?? 0)} min={0} max={100} step={1} onCommit={(v) => setFx(key, v)} />
          ))}
          <label className="check-line"><input type="checkbox" checked={!!fx.denoise} onChange={(e) => setFx("denoise", e.target.checked)} /> Denoise</label>
          <label className="check-line"><input type="checkbox" checked={!!fx.deflicker} onChange={(e) => setFx("deflicker", e.target.checked)} /> Remove flicker</label>
          <label>Stabilize
            <select value={sh.stabilize ?? ""} onChange={(e) => send("set", { stabilize: e.target.value })}>
              <option value="">off (or project setting)</option><option value="minimal">minimal</option>
              <option value="recommended">recommended</option><option value="most">most stable</option>
            </select>
          </label>
        </div>
      )}

      {tab === "frame" && (
        <div className="vs-knobs">
          {fmt === "reel" && <p className="muted">For vertical videos the app picks the most interesting part of the wide frame automatically. Move it here.</p>}
          <Knob label="Position left ↔ right" value={Math.round((sh.xpos ?? 0.5) * 100)} min={0} max={100} step={1} onCommit={(v) => send("set", { xpos: v === null ? 0.5 : v / 100 })} />
          <Knob label="Position up ↕ down" value={Math.round((sh.ypos ?? 0.5) * 100)} min={0} max={100} step={1} onCommit={(v) => send("set", { ypos: v === null ? 0.5 : v / 100 })} />
          <Knob label="Zoom at start %" value={Math.round(((sh.zoom ?? 1) - 1) * 100)} min={0} max={60} step={1} onCommit={(v) => send("set", { zoom: 1 + (v ?? 0) / 100 })} />
          <Knob label="Zoom at end % (slow push-in)" value={Math.round(((sh.zoom_end ?? sh.zoom ?? 1) - 1) * 100)} min={0} max={60} step={1} onCommit={(v) => send("set", { zoom_end: v === null ? "" : 1 + v / 100 })} />
        </div>
      )}

      {tab === "text" && (
        <div className="vs-knobs">
          <label>Template
            <select value={tpl} onChange={(e) => setTpl(e.target.value)}>
              {Object.entries(meta.templates).map(([id, l]) => <option key={id} value={id}>{l}</option>)}
            </select>
          </label>
          <label>Text<input value={txt} onChange={(e) => setTxt(e.target.value)} placeholder="Text" /></label>
          <button className="btn small-btn" onClick={() => send("add_text", { tpl, text: txt, t0: sh.t0, dur: Math.min(3, Math.max(1.5, sh.dur * 1.5)) })}>+ Add at this shot</button>
          {(plan.texts ?? []).map((t, i) => (
            <div key={i} className="muted">{meta.templates[t.tpl] ?? t.tpl}: “{t.text}” at {t.t0.toFixed(1)} s for {t.dur.toFixed(1)} s
              <button className="link" onClick={() => send("remove_text", i)}>remove</button></div>
          ))}
        </div>
      )}
      <p className="muted">Changes show in the video after “Update preview”.</p>
    </div>
  );
}
