import { useEffect, useRef, useState } from "react";
import { api, formatTime, type Clip } from "./api";

type Sentence = { id: number; text: string; dur: number; t: number };
const cache: Record<string, Promise<Sentence[]>> = {};
const loadSentences = (id: string) =>
  (cache[id] ??= api.clipSentences(id).then((r) => r.sentences).catch((e) => {
    delete cache[id];
    throw e;
  }));

type Run = (fn: () => Promise<{ clips: Clip[] }>) => Promise<void>;

/** Was im Reel gesagt wird: Sätze entfernen, davor/danach einen dazunehmen, ein Stück von woanders anhängen. */
export function ReelParts({ id, clip, run, busy }: { id: string; clip: Clip; run: Run; busy: boolean }) {
  const [sent, setSent] = useState<Sentence[]>([]);
  const [extra, setExtra] = useState("");
  useEffect(() => {
    loadSentences(id).then(setSent).catch(() => {});
  }, [id]);
  const byId = new Map(sent.map((s) => [s.id, s]));
  const parts = clip.parts;
  const pads = parts.map((_, k) => clip.pads?.[k] ?? [0, 0]);
  // pads follow their part when parts are added/removed (new parts start with 0/0)
  const save = (next: number[][], nextPads?: number[][]) => {
    const keepPads = nextPads ?? next.map((q) => { const j = parts.findIndex((p) => p.join() === q.join()); return j >= 0 ? pads[j] : [0, 0]; });
    const ok = next.map((q, k) => [q, keepPads[k]] as const).filter(([q]) => q.length);
    return run(() => api.setClipParts(id, clip.id, ok.map(([q]) => q), ok.map(([, pd]) => pd)));
  };
  const nudge = (k: number, side: 0 | 1, sec: number) =>
    save(parts, pads.map((pd, j) => (j === k ? (side === 0 ? [pd[0] + sec, pd[1]] : [pd[0], pd[1] + sec]) : pd)));
  const fmtPad = (x: number) => (x > 0 ? `+${x} s` : x < 0 ? `${x} s` : "");
  const maxId = sent.length ? sent[sent.length - 1].id : 0;

  return (
    <div className="reel-parts">
      {parts.map((p, k) => (
        <div key={k} className="reel-part">
          <div className="reel-part-head small muted">
            Part {k + 1}{byId.get(p[0]) ? ` · from ${formatTime(byId.get(p[0])!.t)}` : ""}
            {p[0] > 1 && (
              <button className="link" disabled={busy} onClick={() => save(parts.map((q, j) => (j === k ? [q[0] - 1, ...q] : q)))}>
                + sentence before
              </button>
            )}
            {p[p.length - 1] < maxId && (
              <button className="link" disabled={busy} onClick={() => save(parts.map((q, j) => (j === k ? [...q, q[q.length - 1] + 1] : q)))}>
                + sentence after
              </button>
            )}
            {parts.length > 1 && (
              <button className="link danger" disabled={busy} onClick={() => save(parts.filter((_, j) => j !== k))}>
                remove part
              </button>
            )}
          </div>
          <div className="reel-pad small">
            <span>Start:</span>
            <button className="link" disabled={busy} onClick={() => nudge(k, 0, 5)} title="start 5 seconds earlier">◀ 5 s more</button>
            <button className="link" disabled={busy} onClick={() => nudge(k, 0, 1)}>+1 s</button>
            <button className="link" disabled={busy} onClick={() => nudge(k, 0, -1)}>−1 s</button>
            <button className="link" disabled={busy} onClick={() => nudge(k, 0, -5)} title="start 5 seconds later">5 s less ▶</button>
            <strong>{fmtPad(pads[k][0])}</strong>
          </div>
          {p.map((sid) => (
            <div key={sid} className="reel-sentence">
              <span>{byId.get(sid)?.text ?? `Sentence ${sid}`}</span>
              <span className="muted small">{byId.get(sid)?.dur ?? ""} s</span>
              <button className="link danger" title="Cut this sentence out of the reel" disabled={busy || (parts.length === 1 && p.length === 1)}
                onClick={() => save(parts.map((q, j) => (j === k ? q.filter((x) => x !== sid) : q)))}>✕</button>
            </div>
          ))}
          <div className="reel-pad small">
            <span>End:</span>
            <button className="link" disabled={busy} onClick={() => nudge(k, 1, -5)} title="end 5 seconds earlier">◀ 5 s less</button>
            <button className="link" disabled={busy} onClick={() => nudge(k, 1, -1)}>−1 s</button>
            <button className="link" disabled={busy} onClick={() => nudge(k, 1, 1)}>+1 s</button>
            <button className="link" disabled={busy} onClick={() => nudge(k, 1, 5)} title="end 5 seconds later">5 s more ▶</button>
            <strong>{fmtPad(pads[k][1])}</strong>
          </div>
        </div>
      ))}
      <div className="reel-add small">
        <select value={extra} onChange={(e) => setExtra(e.target.value)}>
          <option value="">+ add a sentence from anywhere in the video …</option>
          {sent.map((s) => (
            <option key={s.id} value={s.id}>{formatTime(s.t)} · {s.text.slice(0, 80)}</option>
          ))}
        </select>
        <button className="btn ghost small-btn" disabled={!extra || busy} onClick={() => { void save([[Number(extra)], ...parts]); setExtra(""); }}>
          Add at the start (as hook)
        </button>
        <button className="btn ghost small-btn" disabled={!extra || busy} onClick={() => { void save([...parts, [Number(extra)]]); setExtra(""); }}>
          Add at the end
        </button>
      </div>
    </div>
  );
}

/** Wunsch an Claude für genau dieses Reel. */
export function ReelWish({ id, clip, run }: { id: string; clip: Clip; run: Run }) {
  const [wish, setWish] = useState("");
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    await run(() => api.refineClip(id, clip.id, "claude", wish));
    setBusy(false);
    setWish("");
  };
  return (
    <div className="reel-wish">
      <textarea rows={2} value={wish} placeholder={'Tell Claude what to change in this reel, e.g. "stronger hook", "add the part about sleep", "end with the question"'}
        onChange={(e) => setWish(e.target.value)} />
      <button className="btn ghost" disabled={busy || !wish.trim()} onClick={go}>
        {busy ? "Claude is reworking this reel …" : "✨ Change this reel"}
      </button>
    </div>
  );
}

/** CapCut-style reel timeline: every piece of the reel as a block – move, trim, split, duplicate, delete, add.
 *  Saved right away; "▶ Play" shows it in the big video at the top without rendering. */
export function ReelTimeline({ id, clip, run, busy }: { id: string; clip: Clip; run: Run; busy: boolean }) {
  const segs = clip.segments;
  const [sel, setSel] = useState(0);
  const bigTime = useRef(0);
  useEffect(() => {
    const on = (e: Event) => { bigTime.current = Number((e as CustomEvent).detail) || 0; };
    window.addEventListener("cc-time", on);
    return () => window.removeEventListener("cc-time", on);
  }, []);
  const total = segs.reduce((a, [s, e]) => a + (e - s), 0) || 1;
  const k = Math.min(sel, segs.length - 1);
  const save = (next: number[][], nextSel = k) => {
    setSel(Math.max(0, Math.min(nextSel, next.length - 1)));
    return run(() => api.setClipSegments(id, clip.id, next));
  };
  const play = (list: number[][]) => window.dispatchEvent(new CustomEvent("cc-play-segments", { detail: { segments: list } }));
  const r1 = (x: number) => Math.round(x * 100) / 100;
  const edit = (fn: (s: number[]) => number[]) => save(segs.map((s, j) => (j === k ? fn(s).map(r1) : s)));
  const move = (d: number) => {
    const j = k + d;
    if (j < 0 || j >= segs.length) return;
    const next = [...segs];
    [next[k], next[j]] = [next[j], next[k]];
    void save(next, j);
  };
  const split = (at?: number) => {
    const [a, b] = segs[k];
    const t = at ?? (a + b) / 2;
    if (t <= a + 0.2 || t >= b - 0.2) return alert("Move the big video into this piece first (the split point must be inside it).");
    void save([...segs.slice(0, k), [a, r1(t)], [r1(t), b], ...segs.slice(k + 1)], k + 1);
  };
  const addFromBig = () => {
    const t = r1(bigTime.current);
    void save([...segs.slice(0, k + 1), [t, r1(t + 5)], ...segs.slice(k + 1)], k + 1);
  };
  const cur = segs[k];
  return (
    <div className="reel-tl">
      <div className="reel-tl-strip">
        {segs.map(([s, e], j) => (
          <button key={j} className={`reel-tl-block ${j === k ? "on" : ""}`} style={{ flexGrow: Math.max(0.6, e - s) }}
            onClick={() => setSel(j)} onDoubleClick={() => play([[s, e]])} title={`${formatTime(s)} – ${formatTime(e)}`}>
            <b>{j + 1}</b><span>{(e - s).toFixed(1)} s</span>
          </button>
        ))}
      </div>
      <div className="reel-tl-info small muted">
        Reel {total.toFixed(1)} s · {segs.length} pieces · piece {k + 1}: {formatTime(cur[0])} – {formatTime(cur[1])} in your video
      </div>
      <div className="reel-tl-tools small">
        <button className="btn small-btn" onClick={() => play(segs)}>▶ Play reel in the big video</button>
        <button className="link" onClick={() => play([cur])}>▶ this piece</button>
        <span className="sep" />
        <span>Start</span>
        <button className="link" disabled={busy} onClick={() => edit(([a, b]) => [Math.max(0, a - 5), b])}>−5 s</button>
        <button className="link" disabled={busy} onClick={() => edit(([a, b]) => [Math.max(0, a - 1), b])}>−1</button>
        <button className="link" disabled={busy} onClick={() => edit(([a, b]) => [Math.min(b - 0.3, a + 1), b])}>+1</button>
        <button className="link" disabled={busy} onClick={() => edit(([a, b]) => [Math.min(b - 0.3, a + 5), b])}>+5 s</button>
        <span>End</span>
        <button className="link" disabled={busy} onClick={() => edit(([a, b]) => [a, Math.max(a + 0.3, b - 5)])}>−5 s</button>
        <button className="link" disabled={busy} onClick={() => edit(([a, b]) => [a, Math.max(a + 0.3, b - 1)])}>−1</button>
        <button className="link" disabled={busy} onClick={() => edit(([a, b]) => [a, b + 1])}>+1</button>
        <button className="link" disabled={busy} onClick={() => edit(([a, b]) => [a, b + 5])}>+5 s</button>
      </div>
      <div className="reel-tl-tools small">
        <button className="link" disabled={busy || k === 0} onClick={() => move(-1)}>◀ move</button>
        <button className="link" disabled={busy || k === segs.length - 1} onClick={() => move(1)}>move ▶</button>
        <button className="link" disabled={busy} onClick={() => split(bigTime.current)} title="pause the big video where you want to cut">✂ split at the big video</button>
        <button className="link" disabled={busy} onClick={() => split()}>✂ split in the middle</button>
        <button className="link" disabled={busy} onClick={() => save([...segs.slice(0, k + 1), [...cur], ...segs.slice(k + 1)], k + 1)}>⧉ duplicate</button>
        <button className="link danger" disabled={busy || segs.length <= 1} onClick={() => save(segs.filter((_, j) => j !== k))}>🗑 delete piece</button>
        <button className="link" disabled={busy} onClick={addFromBig} title="pause the big video at the moment you want, then click">＋ add 5 s from the big video here</button>
      </div>
    </div>
  );
}
