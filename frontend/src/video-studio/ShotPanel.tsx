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
  const [tab, setTab] = useState<"filters" | "adjust" | "hsl" | "curves" | "wheels" | "mask" | "effects" | "frame" | "ai" | "text">("filters");
  const [curveCh, setCurveCh] = useState<"rgb" | "r" | "g" | "b">("rgb");
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
          {(["filters", "adjust", "hsl", "curves", "wheels", "mask", "effects", "frame", "ai", "text"] as const).map((t) => (
            <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
              {{ filters: "Filters", adjust: "Adjust", hsl: "HSL", curves: "Curves", wheels: "Colour wheels", mask: "Mask",
                effects: "Effects", frame: "Crop & zoom", ai: "AI tools", text: "Text" }[t]}
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

      {tab === "curves" && (() => {
        const curves = (sh.adjust?.curves as unknown as Record<string, number[]>) ?? {};
        const pts = curves[curveCh] ?? [0, 0, 0, 0, 0];
        const setPt = (i: number, v: number | null) => {
          const np = [...pts]; np[i] = v ?? 0;
          void send("set", { adjust: { ...adj, curves: { ...curves, [curveCh]: np } } });
        };
        return (
          <div className="vs-knobs">
            <span className="seg">{(["rgb", "r", "g", "b"] as const).map((c) => (
              <button key={c} className={curveCh === c ? "on" : ""} onClick={() => setCurveCh(c)}>{c.toUpperCase()}</button>))}</span>
            <svg viewBox="0 0 100 100" className="vs-curve">
              <line x1="0" y1="100" x2="100" y2="0" stroke="#ccc" strokeDasharray="2" />
              <polyline fill="none" stroke={{ rgb: "#6a4c9c", r: "#d33", g: "#3a3", b: "#36d" }[curveCh]} strokeWidth="2"
                points={pts.map((v, i) => `${i * 25},${100 - Math.max(0, Math.min(100, i * 25 + v * 0.25))}`).join(" ")} />
            </svg>
            {["Blacks", "Shadows", "Midtones", "Lights", "Whites"].map((l, i) => (
              <Knob key={l} label={`${l} point`} value={pts[i] ?? 0} min={-100} max={100} step={1} onCommit={(v) => setPt(i, v)} />
            ))}
          </div>
        );
      })()}

      {tab === "wheels" && (() => {
        const wheels = (sh.adjust?.wheels as unknown as Record<string, number[]>) ?? {};
        const setW = (zone: string, i: number, v: number | null) => {
          const cur = [...(wheels[zone] ?? [30, 0, 0])]; cur[i] = v ?? (i === 0 ? 30 : 0);
          void send("set", { adjust: { ...adj, wheels: { ...wheels, [zone]: cur } } });
        };
        return (
          <div className="vs-knobs">
            {["shadows", "midtones", "highlights"].map((z) => (
              <div key={z} className="vs-hsl">
                <span><span className="vs-dot" style={{ background: `hsl(${(wheels[z] ?? [30])[0]},80%,55%)` }} /> {z}</span>
                <Knob label="colour (hue °)" value={(wheels[z] ?? [30, 0, 0])[0]} min={0} max={360} step={1} onCommit={(v) => setW(z, 0, v)} />
                <Knob label="amount" value={(wheels[z] ?? [30, 0, 0])[1]} min={0} max={100} step={1} onCommit={(v) => setW(z, 1, v)} />
                <Knob label="brightness" value={(wheels[z] ?? [30, 0, 0])[2]} min={-100} max={100} step={1} onCommit={(v) => setW(z, 2, v)} />
              </div>
            ))}
          </div>
        );
      })()}

      {tab === "mask" && (() => {
        const m = sh.mask ?? {};
        const setM = (patch: Record<string, unknown>) => void send("set", { mask: { ...m, ...patch } });
        const madj = (m.adjust ?? {}) as Record<string, number>;
        return (
          <div className="vs-knobs">
            <label>Shape
              <select value={m.shape ?? ""} onChange={(e) => setM({ shape: e.target.value })}>
                <option value="">no mask</option><option value="sky">Sky (top down to horizon)</option><option value="linear">Linear</option>
                <option value="mirror">Mirror (band)</option><option value="circle">Circle</option><option value="rectangle">Rectangle</option>
                <option value="heart">Heart</option><option value="star">Star</option>
              </select>
            </label>
            {m.shape && <>
              <Knob label="Position x %" value={Math.round((m.x ?? 0.5) * 100)} min={0} max={100} step={1} onCommit={(v) => setM({ x: (v ?? 50) / 100 })} />
              <Knob label="Position y % (horizon)" value={Math.round((m.y ?? 0.45) * 100)} min={0} max={100} step={1} onCommit={(v) => setM({ y: (v ?? 45) / 100 })} />
              <Knob label="Size %" value={Math.round((m.size ?? 0.5) * 100)} min={5} max={150} step={1} onCommit={(v) => setM({ size: (v ?? 50) / 100 })} />
              <Knob label="Rotation °" value={m.rot ?? 0} min={-180} max={180} step={1} onCommit={(v) => setM({ rot: v ?? 0 })} />
              <Knob label="Feather (soft edge) %" value={Math.round((m.feather ?? 0.3) * 100)} min={0} max={100} step={1} onCommit={(v) => setM({ feather: (v ?? 30) / 100 })} />
              <label className="check-line"><input type="checkbox" checked={!!m.invert} onChange={(e) => setM({ invert: e.target.checked })} /> Invert</label>
              <p className="muted">Colour only inside the mask:</p>
              {[["exposure", "Exposure", -2, 2, 0.05], ["contrast", "Contrast", -100, 100, 1], ["temp", "Temperature", -100, 100, 1],
                ["sat", "Saturation", -100, 100, 1], ["highlights", "Highlights", -100, 100, 1]].map(([k2, l, mn, mx, st2]) => (
                <Knob key={k2 as string} label={l as string} value={Number(madj[k2 as string] ?? 0)} min={mn as number} max={mx as number} step={st2 as number}
                  onCommit={(v) => setM({ adjust: { ...madj, [k2 as string]: v ?? 0 } })} />
              ))}
            </>}
          </div>
        );
      })()}

      {tab === "ai" && (() => {
        const ai = sh.ai ?? {};
        const setAi = (patch: Record<string, unknown>) => void send("set", { ai: { ...ai, ...patch } });
        const r = ai.remove ?? null;
        return (
          <div className="vs-knobs">
            <label>Background (people in the shot)
              <select value={ai.bg ?? ""} onChange={(e) => setAi({ bg: e.target.value })}>
                <option value="">keep</option><option value="blur">blur the background (portrait look)</option>
                <option value="color">replace with a colour</option>
              </select>
            </label>
            <label className="check-line"><input type="checkbox" checked={!!fx.enhance} onChange={(e) => setFx("enhance", e.target.checked)} /> Enhance quality (adaptive sharpening)</label>
            <label className="check-line"><input type="checkbox" checked={!!r} onChange={(e) => setAi({ remove: e.target.checked ? [0.4, 0.4, 0.2, 0.2] : null })} /> Remove an object (box)</label>
            {r && ["left %", "top %", "width %", "height %"].map((l, i) => (
              <Knob key={l} label={`Box ${l}`} value={Math.round(r[i] * 100)} min={0} max={100} step={1}
                onCommit={(v) => { const nr = [...r]; nr[i] = (v ?? 0) / 100; setAi({ remove: nr }); }} />
            ))}
            <p className="muted">Works on your PC, free. Object removal is best for small, still things (a logo, a drone leg). Bigger AI tools
              (AI styles, extend the picture, relight, lip-sync) need an external AI service – not included yet.</p>
          </div>
        );
      })()}

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
