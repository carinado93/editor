import { useEffect, useState } from "react";
import { api, formatTime, type CutView, type EffectType, type Overlay, type SpeedRange } from "./api";
import { Status } from "./ReelPackage";

const GROUP_LABEL: Record<string, string> = {
  A: "Boxes & cards",
  B: "Text over the video",
  C: "You cut out (needs more render time)",
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
};

const SPEED_LABEL: Record<number, string> = { 0.25: "¼× slow", 0.5: "½× slow", 2: "2× fast", 4: "4× fast", 8: "8× fast" };

/** Große Effekte (Kästen, Text hinter dir, Puff …) und Zeitraffer/Zeitlupe. Du wählst, Claude schlägt vor. */
export function EffectsPanel({ id, cuts, onCuts, time, onSeek }: {
  id: string; cuts: CutView; onCuts: (c: CutView) => void; time: number; onSeek: (t: number) => void;
}) {
  const [types, setTypes] = useState<EffectType[]>([]);
  const [allowed, setAllowed] = useState<string[]>(cuts.cutlist.fx_allowed ?? []);
  const fromCuts = () => (cuts.cutlist.overlays ?? []).filter((o) => o.kind === "fx");
  const [items, setItems] = useState<Overlay[]>(fromCuts);
  const [dirty, setDirty] = useState(false);
  const [addType, setAddType] = useState("headline");
  const [wish, setWish] = useState("");
  const [preview, setPreview] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api.effectTypes().then((r) => {
      setTypes(r.types);
      setAllowed((a) => (a.length ? a : r.types.filter((t) => t.group !== "C").map((t) => t.key)));
    }).catch(() => {});
  }, []);
  useEffect(() => {
    if (!dirty) setItems(fromCuts());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cuts]);

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
      const others = (cuts.cutlist.overlays ?? []).filter((o) => o.kind !== "fx");
      const v = await api.setOverlays(id, [...others, ...list]);
      setDirty(false);
      onCuts(v);
      setMsg("Saved ✓ – the effects are built in when you render.");
    });

  const suggest = (engine: "claude" | "ollama") =>
    act(engine, async () => {
      const v = await api.suggestEffects(id, engine, allowed, wish);
      setDirty(false);
      onCuts(v);
      const n = (v.cutlist.overlays ?? []).filter((o) => o.kind === "fx").length;
      setMsg(`${n} effects suggested ✓ – check them below, change the type or remove what doesn't fit.`);
    });

  const upd = (i: number, patch: Partial<Overlay>) => {
    setDirty(true);
    setItems(items.map((o, j) => (j === i ? { ...o, ...patch } : o)));
  };

  const add = () => {
    const t = types.find((x) => x.key === addType);
    const dur = addType === "poof" ? 1 : 4;
    const start = Math.max(0, addType === "poof" ? time - 0.25 : time);
    setDirty(true);
    setItems([...items, {
      id: `fx-${Date.now()}`, kind: "fx", type: addType, place: t?.places[0] ?? "scene", on: true,
      title: "", text: addType, items: [], item_t: [], start, end: start + dur,
    }].sort((a, b) => a.start - b.start));
  };

  const speed = cuts.cutlist.speed ?? [];
  const removeSpeed = (r: SpeedRange) =>
    act("speed", async () => onCuts(await api.setSpeed(id, speed.filter((x) => x !== r))));

  const groups = ["A", "B", "C"];
  const typeOf = (k?: string) => types.find((t) => t.key === k);

  return (
    <section className="card fx-card">
      <h3>Effects</h3>
      <p className="small muted">
        Big effects in the style of the reel you liked, in your purple, sage and gold. First tick which effects may be
        used, then let Claude suggest moments – or add one yourself at the current video position.
      </p>

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

      <label className="small idea-box">
        Wish (optional), e.g. "a checklist when I list the limits of a coach, BURNOUT behind me at the start"
        <textarea rows={2} value={wish} onChange={(e) => setWish(e.target.value)} />
      </label>
      <div className="row-buttons">
        <button className="btn" disabled={!!busy || !allowed.length} onClick={() => suggest("claude")}>
          {busy === "claude" ? "Claude is planning … (about 30–90 s)" : "Suggest with Claude"}
        </button>
        <button className="btn ghost" disabled={!!busy || !allowed.length} onClick={() => suggest("ollama")}>
          {busy === "ollama" ? "Local AI is planning … (several minutes)" : "Free with Ollama"}
        </button>
        <span className="fx-add">
          <select value={addType} onChange={(e) => setAddType(e.target.value)}>
            {types.map((t) => (
              <option key={t.key} value={t.key}>{t.label}</option>
            ))}
          </select>
          <button className="btn ghost" onClick={add}>+ Add at {formatTime(time)}</button>
        </span>
        {dirty && (
          <button className="btn" disabled={!!busy} onClick={() => save()}>
            Save effects
          </button>
        )}
      </div>
      <Status busy={busy} err={err} msg={msg} />
      {err?.includes("Settings") && <a className="small" href="#/einstellungen">→ go to Settings</a>}

      <div className="fx-list">
        {items.map((o, i) => {
          const t = typeOf(o.type);
          const listType = ["steps", "cards", "tags", "scores", "checklist", "endcard", "bigwords"].includes(o.type ?? "");
          return (
            <div key={o.id} className={`fx-row ${o.on ? "" : "off"}`}>
              <div className="fx-row-head">
                <input type="checkbox" checked={o.on} onChange={(e) => upd(i, { on: e.target.checked })} />
                <button className="time" title="Jump here" onClick={() => onSeek(o.start)}>{formatTime(o.start)}</button>
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
                <span className="small muted">
                  {((o.end - o.start)).toFixed(1)} s
                  {" "}<button className="link" onClick={() => upd(i, { end: Math.max(o.start + 0.8, o.end - 0.5) })}>shorter</button>{" "}
                  <button className="link" onClick={() => upd(i, { end: o.end + 0.5 })}>longer</button>
                </span>
                <button className="link danger" onClick={() => { setDirty(true); setItems(items.filter((_, j) => j !== i)); }}>
                  remove
                </button>
              </div>
              {o.type !== "poof" && o.type !== "glow" && o.type !== "bigwords" && (
                <input
                  className="fx-title"
                  placeholder={o.type === "headline" || o.type === "card" ? "Headline – lines with | , *word* = gold italic" : "Title (optional)"}
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
              {o.why && <div className="small muted">{o.why}</div>}
              <div className="small">
                {preview[o.id] ? (
                  <img className="fx-preview" src={api.effectPreviewUrl(id, o.id, preview[o.id])} alt="Effect preview" />
                ) : null}
                <button
                  className="link"
                  disabled={dirty}
                  title={dirty ? "Save first" : ""}
                  onClick={() => setPreview({ ...preview, [o.id]: Date.now() })}
                >
                  {dirty ? "save to see a preview" : preview[o.id] ? "refresh preview" : "show preview image"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

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
          <button className="link danger" disabled={!!busy} onClick={() => removeSpeed(r)}>remove</button>
        </div>
      ))}
    </section>
  );
}
