import { useEffect, useState } from "react";
import { api, formatTime, type StudioClip, type StudioProject } from "../api";

type Sug = { start: number; end: number; score: number; hero: boolean; direction: string };

const parse = (v: string) => {   // "1:23" oder "83" → Sekunden
  const p = v.trim().split(":").map(Number);
  if (p.some((x) => Number.isNaN(x))) return NaN;
  return p.length === 2 ? p[0] * 60 + p[1] : p[0];
};

/** "Diese Sekunden nehmen": Vorschläge der App mit Bild + eigene Bereiche (unbedingt nehmen / nie nehmen). */
export function MomentPicker({ sid, clip, busy, onState, onErr }: {
  sid: string; clip: StudioClip; busy: boolean; onState: (s: StudioProject) => void; onErr: (m: string) => void;
}) {
  const [sugs, setSugs] = useState<Sug[] | null>(null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const must = clip.must ?? [], never = clip.never ?? [];
  useEffect(() => {
    if (!clip.analysed) return;
    api.studioSuggestions(sid, clip.id).then((r) => setSugs(r.suggestions)).catch((e) => onErr(e.message));
  }, [sid, clip.id, clip.analysed]);
  const save = async (m: number[][], n: number[][]) => {
    try { onState(await api.studioRanges(sid, clip.id, m, n)); } catch (e) { onErr((e as Error).message); }
  };
  const has = (list: number[][], a: number, b: number) => list.some(([x, y]) => Math.abs(x - a) < 0.3 && Math.abs(y - b) < 0.3);
  const toggle = (kind: "must" | "never", a: number, b: number) => {
    const list = kind === "must" ? must : never;
    const other = kind === "must" ? never : must;
    const next = has(list, a, b) ? list.filter(([x, y]) => !(Math.abs(x - a) < 0.3 && Math.abs(y - b) < 0.3)) : [...list, [a, b]];
    const cleaned = other.filter(([x, y]) => !(Math.abs(x - a) < 0.3 && Math.abs(y - b) < 0.3));
    void (kind === "must" ? save(next, cleaned) : save(cleaned, next));
  };
  const addManual = (kind: "must" | "never") => {
    const a = parse(from), b = parse(to);
    if (!(b > a) || Number.isNaN(a)) { onErr("Please enter from–to, e.g. 1:05 and 1:12."); return; }
    void (kind === "must" ? save([...must, [a, b]], never) : save(must, [...never, [a, b]]));
    setFrom(""); setTo("");
  };
  return (
    <div className="vs-picker small">
      <strong>Choose seconds · {clip.name}</strong>
      {!clip.analysed && <p className="muted">The app has not looked at this clip yet. Press “Analyse clips” above – then you get suggestions.</p>}
      {sugs && (
        <>
          <p className="muted">Suggestions (the steadiest, sharpest moments). ✓ = always use, ✗ = never use. Click the picture to see it bigger.</p>
          <div className="vs-sugs">
            {sugs.map((g) => {
              const isMust = has(must, g.start, g.end), isNever = has(never, g.start, g.end);
              return (
                <div key={g.start} className={`vs-sug ${isMust ? "must" : ""} ${isNever ? "never" : ""}`}>
                  <a href={api.studioFrameUrl(sid, clip.id, (g.start + g.end) / 2)} target="_blank" rel="noreferrer">
                    <img src={api.studioFrameUrl(sid, clip.id, (g.start + g.end) / 2)} alt="" loading="lazy" />
                  </a>
                  <span>{formatTime(g.start)}–{formatTime(g.end)} · {"★".repeat(Math.max(1, Math.round(g.score * 3)))}</span>
                  <span className="vs-sug-btns">
                    <button disabled={busy} className={isMust ? "on" : ""} onClick={() => toggle("must", g.start, g.end)}>✓ use</button>
                    <button disabled={busy} className={isNever ? "on" : ""} onClick={() => toggle("never", g.start, g.end)}>✗ never</button>
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
      <div className="row-buttons">
        <span className="muted">My own part:</span>
        <input className="vs-time" value={from} onChange={(e) => setFrom(e.target.value)} placeholder="from 1:05" />
        <input className="vs-time" value={to} onChange={(e) => setTo(e.target.value)} placeholder="to 1:12" />
        <button className="btn small-btn" disabled={busy} onClick={() => addManual("must")}>✓ always use</button>
        <button className="btn ghost small-btn" disabled={busy} onClick={() => addManual("never")}>✗ never use</button>
      </div>
      {(!!must.length || !!never.length) && (
        <p>
          {must.map(([a, b], i) => <span key={`m${i}`} className="chip on">✓ {formatTime(a)}–{formatTime(b)} <button className="link" onClick={() => save(must.filter((_, j) => j !== i), never)}>×</button></span>)}
          {never.map(([a, b], i) => <span key={`n${i}`} className="chip">✗ {formatTime(a)}–{formatTime(b)} <button className="link" onClick={() => save(must, never.filter((_, j) => j !== i))}>×</button></span>)}
        </p>
      )}
      <p className="muted">Then press “Make new preview”.</p>
    </div>
  );
}
