import { useEffect, useState } from "react";
import { api, formatTime, type CutView, type Overlay } from "./api";
import { Status } from "./ReelPackage";

const STYLE_LABEL: Record<NonNullable<Overlay["style"]>, string> = {
  label: "Purple label",
  sticker: "Sticker list",
  check: "Checklist",
  quote: "Quote pill",
  number: "Big number",
  name: "Name + title",
};

/** YouTube: Animationen im Stil von Carinas eigenem Schnitt. Werden automatisch gesetzt, hier ändern/entfernen. */
export function YoutubeAnimations({ id, cuts, onCuts, onSeek }: {
  id: string; cuts: CutView; onCuts: (c: CutView) => void; onSeek: (t: number) => void;
}) {
  const fromCuts = () => (cuts.cutlist.overlays ?? []).filter((o) => o.kind === "yt");
  const [items, setItems] = useState<Overlay[]>(fromCuts);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

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

  const suggest = (engine: "claude" | "ollama") =>
    act(engine, async () => {
      const v = await api.suggestAnimations(id, engine);
      setDirty(false);
      onCuts(v);
      const n = (v.cutlist.overlays ?? []).filter((o) => o.kind === "yt").length;
      setMsg(`${n} animations placed ✓ – the preview shows them. Remove what doesn't fit.`);
    });

  const save = () =>
    act("save", async () => {
      const others = (cuts.cutlist.overlays ?? []).filter((o) => o.kind !== "yt");
      const v = await api.setOverlays(id, [...others, ...items]);
      setDirty(false);
      onCuts(v);
      setMsg("Saved ✓");
    });

  const upd = (i: number, patch: Partial<Overlay>) => {
    setDirty(true);
    setItems(items.map((o, j) => (j === i ? { ...o, ...patch } : o)));
  };

  const active = items.filter((o) => o.on).length;

  return (
    <section className="card anim-card">
      <h3>Animations in the video</h3>
      <p className="small muted">
        Placed automatically in the style of your own edit: purple labels, sticker lists, checklists, quote pills, big
        numbers and your name. Untick or remove what doesn't fit, then click "Final render".
      </p>
      <div className="row-buttons">
        <button className="btn" disabled={!!busy} onClick={() => suggest("claude")}>
          {busy === "claude" ? "Claude is planning … (about 30–90 s)" : items.length ? "Plan again with Claude" : "Create with Claude"}
        </button>
        <button className="btn ghost" disabled={!!busy} onClick={() => suggest("ollama")}>
          {busy === "ollama" ? "Local AI is planning … (several minutes)" : "Free with Ollama"}
        </button>
        {dirty && (
          <button className="btn" disabled={!!busy} onClick={save}>
            Save changes
          </button>
        )}
      </div>
      <Status busy={busy} err={err} msg={msg} />
      {err?.includes("Settings") && <a className="small" href="#/einstellungen">→ go to Settings</a>}
      {!!items.length && <p className="small muted">{active} of {items.length} switched on</p>}
      <div className="anim-list">
        {items.map((o, i) => (
          <div key={o.id} className={`anim-row ${o.on ? "" : "off"}`}>
            <label className="small">
              <input type="checkbox" checked={o.on} onChange={(e) => upd(i, { on: e.target.checked })} />
            </label>
            <button className="time" title="Jump here" onClick={() => onSeek(o.start)}>
              {formatTime(o.start)}
            </button>
            <span className={`pill style-${o.style}`}>{STYLE_LABEL[o.style ?? "label"]}</span>
            <div className="anim-text">
              {o.style === "sticker" || o.style === "check" ? (
                <textarea
                  rows={Math.max(2, o.list?.length ?? 1)}
                  value={(o.list ?? []).map((p) => p.text).join("\n")}
                  onChange={(e) => {
                    const lines = e.target.value.split("\n");
                    const old = o.list ?? [];
                    upd(i, { list: lines.map((text, k) => ({ text, t: old[k]?.t ?? old[old.length - 1]?.t ?? o.start })) });
                  }}
                />
              ) : (
                <input value={o.text} onChange={(e) => upd(i, { text: e.target.value })} />
              )}
              {o.style === "number" && (
                <input className="num" value={o.number ?? ""} onChange={(e) => upd(i, { number: e.target.value })} />
              )}
            </div>
            <button className="link danger" onClick={() => { setDirty(true); setItems(items.filter((_, j) => j !== i)); }}>
              remove
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
