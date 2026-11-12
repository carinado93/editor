import { useEffect, useState } from "react";
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
  const save = (parts: number[][]) => run(() => api.setClipParts(id, clip.id, parts.filter((p) => p.length)));
  const parts = clip.parts;
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
          {p.map((sid) => (
            <div key={sid} className="reel-sentence">
              <span>{byId.get(sid)?.text ?? `Sentence ${sid}`}</span>
              <span className="muted small">{byId.get(sid)?.dur ?? ""} s</span>
              <button className="link danger" title="Cut this sentence out of the reel" disabled={busy || (parts.length === 1 && p.length === 1)}
                onClick={() => save(parts.map((q, j) => (j === k ? q.filter((x) => x !== sid) : q)))}>✕</button>
            </div>
          ))}
        </div>
      ))}
      <div className="reel-add small">
        <select value={extra} onChange={(e) => setExtra(e.target.value)}>
          <option value="">+ add a sentence from anywhere in the video …</option>
          {sent.map((s) => (
            <option key={s.id} value={s.id}>{formatTime(s.t)} · {s.text.slice(0, 80)}</option>
          ))}
        </select>
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
