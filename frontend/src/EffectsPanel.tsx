import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, formatTime, type CutView, type EffectType, type FxStyle, type Overlay, type RenderOptions, type SpeedRange } from "./api";
import { Status } from "./ReelPackage";
import { TimeRange } from "./TimeRange";

const GROUP_LABEL: Record<string, string> = {
  A: "Boxes & cards",
  B: "Text over the video",
  C: "You cut out (needs more render time)",
  D: "Tripod tricks (film on a tripod + a few seconds of the empty room)",
};

const PLACE_LABEL = { scene: "Full screen", side: "Next to you" };

const HINT: Record<string, string> = {
  steps: "one step per line",
  cards: "one card per line, optional: Title|small line",
  tags: "one tag per line",
  scores: "one per line: Text|score 1-10",
  checklist: "one point per line",
  endcard: "the big call to action, e.g. Comment CALM",
  bigwords: "key words that turn purple, one per line",
  clothesline: "one card per line, optional: Big word|small line",
  repeat: "the repeating phrase, e.g. & again (empty = '&' + your last word)",
  wordswap: "the changing words, one per line (heavy, slow, uncertain …)",
  switch: "small line in the pill below (optional, your words)",
  stickers: "one sticker per line",
  outro: "optional, one per line: Like | Subscribe | Subscribed (empty = these words)",
};

/** Vorschau-Bild, das sich bei jeder Änderung selbst neu zeichnet (kurz warten, dann neu laden). */
type PreviewFn = (item: Overlay, signal: AbortSignal) => Promise<string>;

function FxPreview({ preview, item }: { preview: PreviewFn; item: Overlay }) {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const last = useRef<string | null>(null);
  const key = JSON.stringify([item.type, item.place, item.title, item.items, item.start, item.end, item.scale]);
  useEffect(() => {
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      setFailed(false);
      try {
        const url = await preview(item, ctrl.signal);
        if (last.current) URL.revokeObjectURL(last.current);
        last.current = url;
        setSrc(url);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setFailed(true);
      } finally {
        setLoading(false);
      }
    }, 900);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return (
    <div className="fx-preview-box">
      {src && <video className={`fx-preview ${loading ? "loading" : ""}`} src={src} autoPlay loop muted playsInline />}
      {!src && <div className="fx-preview placeholder small muted">{failed ? "No preview" : "Building preview video …"}</div>}
      {src && loading && <span className="fx-preview-busy small">updating …</span>}
    </div>
  );
}

const SPEED_LABEL: Record<number, string> = { 0.25: "¼× slow", 0.5: "½× slow", 2: "2× fast", 4: "4× fast", 8: "8× fast" };

/** Große Effekte im ganzen Video (YouTube / Reel veredeln) plus Zeitraffer/Zeitlupe. */
export function EffectsPanel({ id, cuts, onCuts, time, onSeek, keep }: {
  id: string; cuts: CutView; onCuts: (c: CutView) => void; time: number; onSeek: (t: number) => void;
  keep?: [number, number][];
}) {
  const [busy, setBusy] = useState(false);
  const fxItems = (cuts.cutlist.overlays ?? []).filter((o) => o.kind === "fx");
  const speed = cuts.cutlist.speed ?? [];
  const removeSpeed = async (r: SpeedRange) => {
    setBusy(true);
    try {
      onCuts(await api.setSpeed(id, speed.filter((x) => x !== r)));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="card fx-card" id="step-effects">
      <h3>Effects</h3>
      <EffectsEditor
        renderOptions={cuts.cutlist.render_options as unknown as Record<string, unknown>}
        onRenderOptions={async (r) => onCuts(await api.renderOptions(id, r as Partial<RenderOptions>))}
        keep={keep}
        endAt={keep?.length ? keep[keep.length - 1][1] : cuts.evaluation.old_duration}
        items={fxItems}
        allowedInit={cuts.cutlist.fx_allowed}
        time={time}
        onSeek={onSeek}
        preview={(item, signal) => api.effectPreviewLive(id, item, signal)}
        onSave={async (list) => {
          const others = (cuts.cutlist.overlays ?? []).filter((o) => o.kind !== "fx");
          onCuts(await api.setOverlays(id, [...others, ...list]));
        }}
        onSuggest={async (engine, allowed, wish) => {
          const v = await api.suggestEffects(id, engine, allowed, wish);
          onCuts(v);
          return (v.cutlist.overlays ?? []).filter((o) => o.kind === "fx").length;
        }}
      >
        <h4 style={{ marginTop: 20 }}>Fast & slow motion</h4>
        <p className="small muted">
          In the transcript, select the words (click, Shift+click) and choose a speed in the bar that appears. Time-lapse
          is muted, slow motion keeps your voice.
        </p>
        {!speed.length && <p className="small muted">No speed changes yet.</p>}
        {speed.map((r, k) => (
          <div key={k} className="small fx-speed">
            <button className="time" onClick={() => onSeek(r.start)}>{formatTime(r.start)}</button>
            – {formatTime(r.end)} · <strong>{SPEED_LABEL[r.factor] ?? `${r.factor}×`}</strong>
            {r.mute ? " · muted" : ""}{" "}
            <button className="link danger" disabled={busy} onClick={() => removeSpeed(r)}>remove</button>
          </div>
        ))}
      </EffectsEditor>
    </section>
  );
}

/** Die Effekt-Liste selbst (für das ganze Video und für jedes Reel). Du wählst, Claude schlägt vor. */
/** Zeit im Original ↔ Zeit im geschnittenen Video (so wie der Player mit "Play preview with cuts" zählt). */
function toCut(keep: [number, number][] | undefined, t: number): number {
  if (!keep?.length) return t;
  let acc = 0;
  for (const [a, b] of keep) {
    if (t >= b) acc += b - a;
    else {
      if (t > a) acc += t - a;
      break;
    }
  }
  return acc;
}
function toOrig(keep: [number, number][] | undefined, n: number): number {
  if (!keep?.length) return n;
  let acc = 0;
  for (const [a, b] of keep) {
    if (n <= acc + (b - a)) return a + Math.max(0, n - acc);
    acc += b - a;
  }
  return keep[keep.length - 1][1];
}
function inCutPart(keep: [number, number][] | undefined, t: number): boolean {
  return !!keep?.length && !keep.some(([a, b]) => t >= a - 0.05 && t <= b + 0.05);
}

export function EffectsEditor({ items: source, allowedInit, time, onSeek, preview, onSave, onSuggest, children, compact, exclude, keep, endAt, renderOptions, onRenderOptions }: {
  items: Overlay[];
  allowedInit?: string[];
  time: number;
  onSeek: (t: number) => void;
  preview: PreviewFn;
  onSave: (list: Overlay[]) => Promise<void>;
  onSuggest: (engine: "claude" | "ollama", allowed: string[], wish: string) => Promise<number>;
  children?: ReactNode;
  compact?: boolean;
  exclude?: string[];
  keep?: [number, number][];
  /** Ende des Videos (Original-Zeit) – für "Like & Subscribe am Ende" */
  endAt?: number;
  /** Render-Einstellungen des Projekts (nur beim ganzen Video, nicht bei Reels) – für gespeicherte Stile */
  renderOptions?: Record<string, unknown>;
  onRenderOptions?: (r: FxStyle["render"]) => Promise<void>;
}) {
  const [types, setTypes] = useState<EffectType[]>([]);
  const [allowed, setAllowed] = useState<string[]>(allowedInit ?? []);
  const [items, setItems] = useState<Overlay[]>(source);
  const [dirty, setDirty] = useState(false);
  const [addType, setAddType] = useState("headline");
  const [addText, setAddText] = useState("");
  const [wish, setWish] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api.effectTypes().then((r) => {
      r.types = r.types.filter((t) => !(exclude ?? []).includes(t.key))
        .sort((x, y) => x.label.localeCompare(y.label, "en", { sensitivity: "base" }));  // A–Z in allen Listen
      setTypes(r.types);
      setAllowed((a) => (a.length ? a : r.types.filter((t) => t.group !== "C").map((t) => t.key)));
    }).catch(() => {});
  }, []);
  // ---------- gespeicherte Stile ----------
  const [styles, setStyles] = useState<FxStyle[]>([]);
  const [styleId, setStyleId] = useState<string>(() => {
    try { return localStorage.getItem("fx-style") ?? ""; } catch { return ""; }
  });
  const sizesAfterSuggest = useRef<Record<string, number> | null>(null);
  useEffect(() => {
    api.styles().then((r) => setStyles(r.styles)).catch(() => {});
  }, []);
  const withSizes = (list: Overlay[], sizes: Record<string, number>) =>
    list.map((o) => (o.type && sizes[o.type] ? { ...o, scale: sizes[o.type] } : o));

  useEffect(() => {
    if (sizesAfterSuggest.current) {  // neue Vorschläge von Claude gleich in den Größen des Stils
      const sz = sizesAfterSuggest.current;
      sizesAfterSuggest.current = null;
      const list = withSizes(source, sz);
      setItems(list);
      if (JSON.stringify(list) !== JSON.stringify(source)) void onSave(list);
      return;
    }
    if (!dirty) setItems(source);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(source)]);

  const act = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setErr(null);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const save = (list = items) =>
    act("save", async () => {
      await onSave(list);
      setDirty(false);
      setMsg("Saved ✓ – the effects are built in when you render.");
    });

  const suggest = (engine: "claude" | "ollama") =>
    act(engine, async () => {
      const st = styles.find((x) => x.id === styleId);
      if (st && Object.keys(st.sizes).length) sizesAfterSuggest.current = st.sizes;
      const n = await onSuggest(engine, allowed, wish);
      setDirty(false);
      setMsg(`${n} effects suggested ✓ – check them below, change the type or remove what doesn't fit.`);
    });

  const upd = (i: number, patch: Partial<Overlay>) => {
    setDirty(true);
    setItems(items.map((o, j) => (j === i ? { ...o, ...patch } : o)));
  };

  const LIST_TYPES = ["steps", "cards", "tags", "scores", "checklist", "endcard", "bigwords", "clothesline", "wordswap", "stickers"];
  const add = () => {
    const t = types.find((x) => x.key === addType);
    const dur = addType === "poof" ? 1 : addType === "whip" ? 0.6 : 4;
    const start = Math.max(0, addType === "poof" ? time - 0.25 : addType === "whip" ? time - 0.3 : time);
    // Dein Text macht den Effekt: bei Listen eine Zeile pro Punkt, sonst wird er zur Überschrift
    const lines = addText.split("\n").map((x) => x.trim()).filter(Boolean);
    const isList = LIST_TYPES.includes(addType);
    const title = isList ? "" : lines.join("|");
    setDirty(true);
    setItems([...items, {
      id: `fx-${Date.now()}`, kind: "fx", type: addType, place: t?.places[0] ?? "scene", on: true,
      title, text: title || addType, items: isList ? lines : [], item_t: [], start, end: start + dur,
      bg_t: null, pose_t: [], mode: "vanish" as const,
    }].sort((a, b) => a.start - b.start));
    setAddText("");
  };

  // Schluss: "Thank you for watching" + Like & Subscribe in den letzten 6 Sekunden (des geschnittenen Videos)
  const addOutro = () => {
    if (endAt == null) return;
    const endCut = toCut(keep, endAt);
    const start = Math.round(toOrig(keep, Math.max(0, endCut - 6)) * 100) / 100;
    const nid = `fx-${Date.now()}`;
    const list = [...items.filter((o) => o.type !== "outro"), {
      id: nid, kind: "fx", type: "outro", place: "side" as const, on: true,
      title: "Thank you for watching", text: "Thank you for watching", items: [], item_t: [],
      start, end: Math.round((start + 6) * 100) / 100, bg_t: null, pose_t: [], mode: "vanish" as const,
    }].sort((a, b) => a.start - b.start);
    setItems(list);
    setDirty(true);
    onSeek(start);
    // gleich speichern und zum neuen Effekt springen, damit man ihn sieht
    void act("save", async () => {
      await onSave(list);
      setDirty(false);
      setMsg("Like & Subscribe added at the end and saved ✓ – it's shown below (last effect in the list).");
    });
    setTimeout(() => document.getElementById(nid)?.scrollIntoView({ behavior: "smooth", block: "center" }), 300);
  };


  const applyStyle = (st: FxStyle) =>
    act("style", async () => {
      if (st.allowed.length) setAllowed(st.allowed.filter((k) => types.some((t) => t.key === k)));
      setWish(st.wish);
      let list = withSizes(items, st.sizes);
      if (st.outro && endAt != null && !list.some((o) => o.type === "outro")) {
        const endCut = toCut(keep, endAt);
        const start = Math.round(toOrig(keep, Math.max(0, endCut - 6)) * 100) / 100;
        list = [...list, {
          id: `fx-${Date.now()}`, kind: "fx", type: "outro", place: "side" as const, on: true,
          title: "Thank you for watching", text: "Thank you for watching", items: [], item_t: [],
          start, end: Math.round((start + 6) * 100) / 100, bg_t: null, pose_t: [], mode: "vanish" as const,
        }].sort((a, b) => a.start - b.start);
      }
      setItems(list);
      await onSave(list);
      setDirty(false);
      if (onRenderOptions && Object.keys(st.render).length) await onRenderOptions(st.render);
      setStyleId(st.id);
      try { localStorage.setItem("fx-style", st.id); } catch { /* egal */ }
      setMsg(`Style “${st.name}” applied ✓ – effect choice, wish, sizes${st.outro ? ", outro" : ""}${onRenderOptions && Object.keys(st.render).length ? " and render settings" : ""}. Now let Claude suggest, or add effects yourself.`);
    });

  const saveStyle = () => {
    const name = prompt("Name for this style (e.g. “My YouTube style”). The same name overwrites an existing style.",
      styles.find((x) => x.id === styleId)?.name ?? "");
    if (!name?.trim()) return;
    // Größe pro Effekt-Typ: wie Carina sie in diesem Video eingestellt hat (Durchschnitt)
    const acc: Record<string, number[]> = {};
    items.forEach((o) => { if (o.type && o.scale && o.scale !== 1) (acc[o.type] ??= []).push(o.scale); });
    const sizes = Object.fromEntries(Object.entries(acc).map(([k, v]) => [k, Math.round((v.reduce((a, b) => a + b, 0) / v.length) * 100) / 100]));
    const render: FxStyle["render"] = {};
    if (renderOptions) {
      for (const k of ["zoom", "loudness", "denoise", "declick", "karaoke"] as const) if (k in renderOptions) render[k] = !!renderOptions[k];
      if (typeof renderOptions.subtitles === "string") render.subtitles = renderOptions.subtitles;
    }
    act("style", async () => {
      const r = await api.styleSave({ name: name.trim(), allowed, wish, sizes, outro: items.some((o) => o.type === "outro"), render });
      setStyles(r.styles);
      const st = r.styles.find((x) => x.name.toLowerCase() === name.trim().toLowerCase());
      if (st) {
        setStyleId(st.id);
        try { localStorage.setItem("fx-style", st.id); } catch { /* egal */ }
      }
      setMsg(`Style “${name.trim()}” saved ✓ – use it on your next video with one click.`);
    });
  };

  const groups = ["A", "B", "C", "D"];
  const typeOf = (k?: string) => types.find((t) => t.key === k);

  return (
    <div className={compact ? "fx-editor compact" : "fx-editor"}>
      <p className="small muted">
        Big effects in your purple, sage and gold. Let Claude suggest moments, or add one yourself at the current
        video position. Every effect below can be changed: type, text, times and size.
      </p>

      <div className="fx-style-row small">
        <strong>Style</strong>
        <select value={styleId} onChange={(e) => setStyleId(e.target.value)}>
          <option value="">– choose a saved style –</option>
          {styles.map((st) => <option key={st.id} value={st.id}>{st.name}</option>)}
        </select>
        <button className="btn small-btn" disabled={!!busy || !styleId} onClick={() => {
          const st = styles.find((x) => x.id === styleId);
          if (st) applyStyle(st);
        }}>Apply</button>
        <button className="btn ghost small-btn" disabled={!!busy} onClick={saveStyle}
          title="Saves the ticked effects, your wish, the sizes you set, the outro and (for the whole video) the render settings">
          Save current as style
        </button>
        {styleId && (
          <button className="link danger" onClick={() => {
            const st = styles.find((x) => x.id === styleId);
            if (st && confirm(`Delete the style “${st.name}”?`)) act("style", async () => { setStyles((await api.styleDelete(st.id)).styles); setStyleId(""); });
          }}>delete style</button>
        )}
      </div>

      <div className="fx-tool">
        <div className="fx-tool-title">✨ Let Claude suggest</div>
        <textarea rows={2} value={wish} placeholder={'Wish (optional), e.g. "a checklist when I list the limits of a coach, BURNOUT behind me at the start"'}
          onChange={(e) => setWish(e.target.value)} />
        <div className="row-buttons">
          <button className="btn" disabled={!!busy || !allowed.length} onClick={() => suggest("claude")}>
            {busy === "claude" ? "Claude is planning … (about 30–90 s)" : "Suggest with Claude"}
          </button>
          <button className="btn ghost" disabled={!!busy || !allowed.length} onClick={() => suggest("ollama")}>
            {busy === "ollama" ? "Local AI is planning … (several minutes)" : "Free with Ollama"}
          </button>
        </div>
        <details className="fx-palette-box small">
          <summary>Which effects Claude may use ({allowed.length} of {types.length} ticked)</summary>
          <div className="fx-palette">
            {groups.map((g) => (
              <div key={g} className="fx-group">
                <strong className="small">{GROUP_LABEL[g]}</strong>
                <div className="fx-chips">
                  {types.filter((t) => t.group === g).map((t) => (
                    <label key={t.key} className={`fx-chip ${allowed.includes(t.key) ? "on" : ""}`}>
                      <input
                        type="checkbox"
                        checked={allowed.includes(t.key)}
                        onChange={(e) => setAllowed(e.target.checked ? [...allowed, t.key] : allowed.filter((x) => x !== t.key))}
                      />
                      {t.label}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </details>
      </div>

      <div className="fx-tool">
        <div className="fx-tool-title">＋ Add an effect yourself <span className="muted small">at {formatTime(time)} (pause the video where it should start)</span></div>
        <div className="fx-add-row">
          <select value={addType} onChange={(e) => setAddType(e.target.value)}>
            {types.map((t) => (
              <option key={t.key} value={t.key}>{t.label}</option>
            ))}
          </select>
          <textarea className="fx-add-text" rows={1} value={addText}
            placeholder={HINT[addType] ? `Your text (optional) – ${HINT[addType]}` : "Your text (optional)"}
            onChange={(e) => setAddText(e.target.value)} />
          <button className="btn" onClick={add}>+ Add at {formatTime(time)}</button>
        </div>
        {endAt != null && (
          <button className="btn ghost" onClick={addOutro} title="'Thank you for watching' + Like & Subscribe buttons in the last 6 seconds">
            + Like &amp; Subscribe at the end
          </button>
        )}
      </div>

      <div className="fx-save-row">
        <strong>{items.length ? `${items.length} effect${items.length > 1 ? "s" : ""}` : "No effects yet"}</strong>
        <button className={`btn ${dirty ? "" : "ghost"}`} disabled={!!busy || !dirty} onClick={() => save()}
          title={dirty ? "" : "Everything is saved"}>
          {dirty ? "Save effects" : "Saved ✓"}
        </button>
      </div>
      <Status busy={busy} err={err} msg={msg} />
      {err?.includes("Settings") && <a className="small" href="#/einstellungen">→ go to Settings</a>}

      <div className="fx-list">
        {items.map((o, i) => {
          const t = typeOf(o.type);
          const listType = ["steps", "cards", "tags", "scores", "checklist", "endcard", "bigwords", "clothesline", "repeat", "wordswap", "switch", "stickers"].includes(o.type ?? "");
          return (
            <div key={o.id} id={o.id} className={`fx-row ${o.on ? "" : "off"}`}>
              <FxPreview preview={preview} item={o} />
              <div className="fx-row-main">
              <div className="fx-row-head">
                <input type="checkbox" checked={o.on} onChange={(e) => upd(i, { on: e.target.checked })} />
                <select value={o.type} onChange={(e) => {
                  const nt = typeOf(e.target.value);
                  upd(i, { type: e.target.value, place: nt && !nt.places.includes(o.place ?? "scene") ? nt.places[0] : o.place });
                }}>
                  {types.map((x) => (
                    <option key={x.key} value={x.key}>{x.label}</option>
                  ))}
                </select>
                {t && t.places.length > 1 && (
                  <select value={o.place} onChange={(e) => upd(i, { place: e.target.value as "scene" | "side" })}>
                    {t.places.map((p) => (
                      <option key={p} value={p}>{PLACE_LABEL[p]}</option>
                    ))}
                  </select>
                )}
                <TimeRange start={toCut(keep, o.start)} end={toCut(keep, o.start) + (o.end - o.start)} now={toCut(keep, time)}
                  onSeek={() => onSeek(o.start)}
                  onChange={(st, en) => {
                    // eingegeben wird in der Zeit des geschnittenen Videos, gespeichert in Original-Zeit
                    const so = Math.round(toOrig(keep, st) * 100) / 100;
                    const d = so - o.start;  // Listenpunkte wandern mit
                    upd(i, { start: so, end: Math.round((so + (en - st)) * 100) / 100,
                             item_t: (o.item_t ?? []).map((x) => Math.round((x + d) * 10) / 10) });
                  }} />
                {inCutPart(keep, o.start) && <span className="small error-text">starts in a cut part – shown at the next kept spot</span>}
                <button className="link danger" onClick={() => { setDirty(true); setItems(items.filter((_, j) => j !== i)); }}>
                  remove
                </button>
              </div>
              {!["poof", "glow", "bigwords", "lighttrail", "ghost", "whip", "vanish", "flash", "sticker"].includes(o.type ?? "") && (
                <input
                  className="fx-title"
                  placeholder={
                    o.type === "headline" || o.type === "card" ? "Headline – lines with | , *word* = gold italic"
                      : o.type === "switch" ? "Big headline in the glowing box (your words)"
                      : o.type === "statement" ? "Your short line, e.g. But you didn't."
                      : o.type === "quote" ? "Your quote, e.g. \u201eIf I could go back …\u201c"
                      : o.type === "repeat" ? "Your sentence, e.g. Don't forget to try again"
                      : o.type === "wordswap" ? "The fixed part, e.g. trust the timing of your life even when it feels"
                      : o.type === "label" ? "Purple label text, e.g. BURNOUT = JUST TIRED?"
                      : o.type === "quotepill" ? "Quote, *word* = purple italic"
                      : o.type === "number" ? "Word|number, e.g. Burnout|×3"
                      : o.type === "name" ? "Name|title, e.g. Carina Dorca|Stress & Burnout Coach"
                      : o.type === "buzzword" ? "The word, e.g. Burnout"
                      : "Title (optional)"}
                  value={o.title ?? ""}
                  onChange={(e) => upd(i, { title: e.target.value, text: e.target.value || o.type || "fx" })}
                />
              )}
              {listType && (
                <textarea
                  rows={Math.max(2, (o.items ?? []).length)}
                  placeholder={HINT[o.type ?? ""]}
                  value={(o.items ?? []).join("\n")}
                  onChange={(e) => upd(i, { items: e.target.value.split("\n") })}
                />
              )}
              {o.type === "switch" && (
                <div className="small fx-tripod">
                  <span>
                    Tap moment (switch turns on): <strong>{o.item_t?.length ? formatTime(o.item_t[0]) : "after ~0.8 s"}</strong>{" "}
                    <button className="link" onClick={() => upd(i, { item_t: [time] })}>use current position ({formatTime(time)})</button>
                  </span>
                  <span className="muted">Move the video to the moment you tap the wall, then click the button.</span>
                </div>
              )}
              {(o.type === "vanish" || o.type === "flash") && (
                <div className="small fx-tripod">
                  {o.type === "vanish" && (
                    <select value={o.mode ?? "vanish"} onChange={(e) => upd(i, { mode: e.target.value as "vanish" | "appear" })}>
                      <option value="vanish">Disappear (you → smoke → empty room)</option>
                      <option value="appear">Appear (empty room → smoke → you)</option>
                    </select>
                  )}
                  <span>
                    Empty room: <strong>{o.bg_t != null ? formatTime(o.bg_t) : "not set"}</strong>{" "}
                    <button className="link" onClick={() => upd(i, { bg_t: time })}>use current position ({formatTime(time)})</button>
                    {o.bg_t != null && <> · <button className="link" onClick={() => onSeek(o.bg_t!)}>show</button></>}
                  </span>
                  {o.type === "flash" && (
                    <span>
                      Poses:{" "}
                      {(o.pose_t ?? []).map((pt, k) => (
                        <span key={k} className="pill">
                          <button className="link" onClick={() => onSeek(pt)}>{formatTime(pt)}</button>
                          <button className="link danger" onClick={() => {
                            const pose_t = (o.pose_t ?? []).filter((_, j) => j !== k);
                            upd(i, { pose_t, end: o.start + Math.max(0.9, pose_t.length * 0.45) });
                          }}>×</button>
                        </span>
                      ))}
                      <button className="link" onClick={() => {
                        const pose_t = [...(o.pose_t ?? []), time];
                        upd(i, { pose_t, end: o.start + Math.max(0.9, pose_t.length * 0.45) });
                      }}>+ pose at current position ({formatTime(time)})</button>
                    </span>
                  )}
                  <span className="muted">
                    Move the video to a moment where the room is empty (or where you hold a pose) and click the button.
                  </span>
                </div>
              )}
              <label className="small fx-size">
                Size
                <input type="range" min={0.5} max={2} step={0.1} value={o.scale ?? 1}
                  onChange={(e) => upd(i, { scale: Number(e.target.value) })} />
                <span className="muted">{Math.round((o.scale ?? 1) * 100)} %</span>
                {(o.scale ?? 1) !== 1 && <button className="link" onClick={() => upd(i, { scale: 1 })}>reset</button>}
              </label>
              {o.why && <div className="small muted">{o.why}</div>}
              </div>
            </div>
          );
        })}
      </div>

      {children}
    </div>
  );
}
