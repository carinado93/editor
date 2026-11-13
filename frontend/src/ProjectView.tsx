import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { YoutubePackage } from "./YoutubePackage";
import { ReelPackage } from "./ReelPackage";
import { EffectsPanel } from "./EffectsPanel";
import { api, formatSize, formatTime, type CutType, type CutView, type Detection, type Project, type Transcript, type Word } from "./api";

interface FlatWord extends Word {
  i: number;
  seg: number;
}

const TYPE_LABEL: Record<CutType, string> = {
  retake: "Retake",
  signal: "Signal word",
  doppelt: "Doubled",
  fragment: "Broken off",
  fuellwort: "Filler word",
  blick: "Looking away",
  manuell: "Deleted by you",
};

const TEMPO_LABEL: Record<string, string> = { locker: "relaxed", normal: "normal", straff: "tight" };

const QUALITIES: Record<string, string> = {
  "1080": "1080p (recommended)",
  "2160": "4K (if the original is that big)",
  original: "Original resolution",
};

/** Index des letzten Elements mit start <= t (binäre Suche). */
function findAt<T>(list: T[], t: number, start: (x: T) => number): number {
  let lo = 0;
  let hi = list.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (start(list[mid]) <= t) {
      found = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return found;
}

/** Zu einem Schritt scrollen (ohne die #/p/…-Adresse der App zu ändern). */
function jump(e: React.MouseEvent<HTMLAnchorElement>) {
  e.preventDefault();
  const id = e.currentTarget.getAttribute("href")?.slice(1);
  if (id) document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function ProjectView({ id }: { id: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [cuts, setCuts] = useState<CutView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState(-1);
  const [time, setTime] = useState(0);
  const [follow, setFollow] = useState(true);
  const [preview, setPreview] = useState(true);
  const [sel, setSel] = useState<[number, number] | null>(null);
  const [busy, setBusy] = useState(false);
  const [quality, setQuality] = useState("1080");
  const [faceBox, setFaceBox] = useState<number[] | null>(null);
  const [watch, setWatch] = useState<string | null>(null);
  // Fertiges Video gleich herunterladen (wie bei den Reels) – abschaltbar
  const [autoDl, setAutoDl] = useState(() => {
    try { return localStorage.getItem("final-auto-download") !== "0"; } catch { return true; }
  });
  const [doneMsg, setDoneMsg] = useState<string | null>(null);
  const [makingReel, setMakingReel] = useState(false);
  const lastRender = useRef<string | undefined>(undefined);
  useEffect(() => {
    const r = project?.render;
    const before = lastRender.current;
    lastRender.current = r?.status;
    if ((before === "warteschlange" || before === "arbeitet") && r?.status === "fertig" && r.file) {
      if (autoDl) {
        const a = document.createElement("a");
        a.href = api.exportUrl(id, r.file);
        a.download = r.file;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setDoneMsg("Your video is ready ✓ – it was downloaded to your Downloads folder.");
      } else {
        setDoneMsg("Your video is ready ✓ – download it below.");
      }
      setWatch(r.file);
    }
  }, [project?.render?.status, project?.render?.file, autoDl, id]);
  const [busyWith, setBusyWith] = useState<string | null>(null);
  // Beim Warten zeigen, womit die App gerade beschäftigt ist
  useEffect(() => {
    const waiting = project?.status === "warteschlange" || project?.render?.status === "warteschlange";
    if (!waiting) {
      setBusyWith(null);
      return;
    }
    const KIND: Record<string, string> = { rendern: "rendering", clip: "rendering a reel of", vorbereiten: "preparing" };
    const load = () =>
      api.queue().then((q) => {
        const main = q.running.find((r) => r.lane === "main" && r.project !== id);
        setBusyWith(main ? `${KIND[main.kind] ?? main.kind} "${main.name}" (since ${Math.floor(main.seconds / 60)} min)` : null);
      }).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [project?.status, project?.render?.status, id]);
  const video = useRef<HTMLVideoElement>(null);
  const textBox = useRef<HTMLDivElement>(null);
  const previewRef = useRef(preview);
  previewRef.current = preview;

  // ---------- Laden ----------
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    let haveTranscript = false;
    const load = async () => {
      try {
        const p = await api.project(id);
        if (!alive) return;
        setProject(p);
        if (p.status === "fertig" && !haveTranscript) {
          haveTranscript = true;
          setTranscript(await api.transcript(id));
          if (p.mode === "youtube" || p.mode === "reel") {
            setCuts(await api.cuts(id));
            api.blick(id).then((b) => setFaceBox(b.face_box)).catch(() => {});
          }
        }
        const rendering = p.render && (p.render.status === "warteschlange" || p.render.status === "arbeitet");
        if (p.status !== "fertig" && p.status !== "fehler") timer = setTimeout(load, 1500);
        else if (rendering) timer = setTimeout(load, 1000);
      } catch (e) {
        if (alive) setError((e as Error).message);
        timer = setTimeout(load, 3000);
      }
    };
    load();
    const kick = () => {
      clearTimeout(timer);
      load();
    };
    window.addEventListener("projekt-neu-laden", kick);
    return () => {
      alive = false;
      clearTimeout(timer);
      window.removeEventListener("projekt-neu-laden", kick);
    };
  }, [id]);

  const words = useMemo<FlatWord[]>(() => {
    if (!transcript) return [];
    const out: FlatWord[] = [];
    transcript.segments.forEach((s, seg) => s.words.forEach((w) => out.push({ ...w, i: out.length, seg })));
    return out;
  }, [transcript]);

  const flags = cuts?.evaluation.flags;
  const keep = cuts?.evaluation.keep;
  const cutMode = project?.mode === "youtube" && !!cuts;
  const reelMode = project?.mode === "reel" && !!cuts;
  const editMode = cutMode || reelMode;

  // Wort → Erkennung (für Tooltip und "Schnitt zurücknehmen")
  const detOf = useMemo(() => {
    const m = new Map<number, Detection>();
    cuts?.cutlist.detections.forEach((d) => {
      for (let k = d.start; k < d.end; k++) if (!m.has(k) || d.active) m.set(k, d);
    });
    return m;
  }, [cuts]);

  // Buzzwords sind jetzt Effekte: Wörter markieren, die in einem Buzzword-Effekt stehen
  const buzzOf = useMemo(() => {
    const m = new Map<number, { start: number; end: number }>();
    const bz = (cuts?.cutlist.overlays ?? []).filter((o) => o.kind === "fx" && o.type === "buzzword");
    words.forEach((w) => {
      if (bz.some((o) => w.s >= o.start - 0.05 && w.s < o.start + 0.6)) m.set(w.i, { start: w.i, end: w.i + 1 });
    });
    return m;
  }, [cuts, words]);

  // Untertitel-Zeilen für die Vorschau (gleiche Regeln wie beim Rendern)
  const subLines = useMemo(() => {
    if (!flags || !words.length) return [] as { start: number; end: number; text: string }[];
    const maxChars = project?.info && project.info.height > project.info.width ? 26 : 42;
    const out: { start: number; end: number; text: string }[] = [];
    let cur: FlatWord[] = [];
    const push = () => {
      if (cur.length) out.push({ start: cur[0].s, end: cur[cur.length - 1].e + 0.15, text: cur.map((w) => w.w).join(" ") });
      cur = [];
    };
    for (const w of words) {
      if (flags[w.i]) continue;
      const text = [...cur, w].map((x) => x.w).join(" ");
      if (cur.length && text.length > maxChars) push();
      cur.push(w);
      if (/[.!?…]$/.test(w.w) || (/[,;:]$/.test(w.w) && text.length > maxChars * 0.6)) push();
    }
    push();
    return out;
  }, [flags, words, project?.info]);

  const pauseAfter = useMemo(() => {
    const m = new Map<number, CutView["evaluation"]["pauses"][number]>();
    cuts?.evaluation.pauses.forEach((p) => m.set(p.after, p));
    return m;
  }, [cuts]);

  // ---------- Abspielen: aktuelles Wort, Schnitte überspringen ----------
  useEffect(() => {
    const v = video.current;
    if (!v) return;
    let raf = 0;
    const tick = () => {
      let t = v.currentTime;
      if (previewRef.current && keep && keep.length && !v.paused) {
        const k = findAt(keep, t + 0.001, (x) => x[0]);
        const inside = k >= 0 && t < keep[k][1];
        if (!inside) {
          const next = keep[k + 1];
          if (next) {
            v.currentTime = next[0];
            t = next[0];
          } else {
            v.pause();
          }
        }
      }
      setTime(t);
      if (words.length) {
        const f = findAt(words, t, (w) => w.s);
        setCurrent(f >= 0 && t <= words[f].e + 0.3 ? f : -1);
      }
      if (!v.paused) raf = requestAnimationFrame(tick);
    };
    const start = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(tick);
    };
    v.addEventListener("play", start);
    v.addEventListener("seeked", tick);
    v.addEventListener("timeupdate", tick);
    return () => {
      cancelAnimationFrame(raf);
      v.removeEventListener("play", start);
      v.removeEventListener("seeked", tick);
      v.removeEventListener("timeupdate", tick);
    };
  }, [words, keep, project?.step]);

  useEffect(() => {
    if (!follow || current < 0 || !textBox.current) return;
    const el = textBox.current.querySelector<HTMLElement>(`[data-i="${current}"]`);
    if (!el) return;
    const box = textBox.current.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    if (r.top < box.top + 40 || r.bottom > box.bottom - 40) el.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [current, follow]);

  const seek = (t: number, play = true) => {
    const v = video.current;
    if (!v) return;
    v.currentTime = Math.max(0, t - 0.05);
    if (play) void v.play();
  };

  // ---------- Schnitte ändern ----------
  const run = useCallback(
    async (fn: () => Promise<CutView>) => {
      setBusy(true);
      try {
        setCuts(await fn());
        setError(null);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const selWords = sel ? Array.from({ length: sel[1] - sel[0] + 1 }, (_, k) => sel[0] + k) : [];
  const selHasCut = !!flags && selWords.some((k) => flags[k]);
  const selDet = sel && sel[0] === sel[1] ? detOf.get(sel[0]) : sel ? detOf.get(sel[0]) : undefined;
  // nur wenn genau der ganze Vorschlag markiert ist – ein einzelnes Wort darin wird nur als Wort behandelt
  const selDetExact = selDet && sel && sel[0] === selDet.start && sel[1] === selDet.end - 1 ? selDet : undefined;

  const deleteSel = () => sel && run(() => api.cutWords(id, selWords, true));
  const restoreSel = () => {
    if (!sel) return;
    if (selDetExact && selDetExact.active) return run(() => api.toggleCut(id, selDetExact.id, false));
    return run(() => api.cutWords(id, selWords, false));
  };

  const onWordClick = (w: FlatWord, ev: React.MouseEvent) => {
    if (ev.shiftKey && sel) {
      setSel([Math.min(sel[0], w.i), Math.max(sel[1], w.i)]);
      return;
    }
    setSel([w.i, w.i]);  // immer nur dieses eine Wort; ganze Vorschläge über den Link in der Leiste
    seek(w.s, false);
  };

  // Tastatur: Entf = löschen, Strg+Z = rückgängig, Leertaste = abspielen
  useEffect(() => {
    if (!cutMode) return;
    const on = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if ((e.key === "Delete" || e.key === "Backspace") && sel) {
        e.preventDefault();
        if (selHasCut) void restoreSel();
        else void deleteSel();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (cuts?.can_undo) void run(() => api.undo(id));
      } else if (e.key === " " && video.current) {
        e.preventDefault();
        if (video.current.paused) void video.current.play();
        else video.current.pause();
      } else if (e.key === "Escape") setSel(null);
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  });

  // ---------- Rendern ----------
  const startRender = async () => {
    if (reelMode && !(cuts?.cutlist.overlays ?? []).some((o) => o.on)) {
      if (!confirm("No hook and no text in the video. Tip: \"Create with Claude\" in the reel package below. Render anyway?")) return;
    }
    try {
      const p = await api.render(id, quality);
      setProject(p);
      window.dispatchEvent(new Event("projekt-neu-laden"));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  if (error && !project)
    return (
      <div className="page">
        <div className="banner error">{error}</div>
      </div>
    );
  if (!project) return <div className="page muted">Loading …</div>;

  const ready = project.status === "fertig";
  const portrait = project.info ? project.info.height > project.info.width : false;
  const counts: Partial<Record<CutType, number>> = {};
  cuts?.cutlist.detections.forEach((d) => d.active && (counts[d.type] = (counts[d.type] ?? 0) + 1));
  if (cuts?.cutlist.manual.cut.length) counts.manuell = cuts.cutlist.manual.cut.length;
  const suggestions = cuts?.cutlist.detections.filter((d) => !d.active).length ?? 0;
  const pausesCut = cuts?.evaluation.pauses.filter((p) => !p.kept && !p.noise).length ?? 0;
  const noisesCut = cuts?.evaluation.pauses.filter((p) => !p.kept && p.noise).length ?? 0;
  const oldDur = cuts?.evaluation.old_duration ?? project.info?.duration ?? 0;
  const newDur = cuts?.evaluation.new_duration ?? 0;
  const duration = project.info?.duration ?? 0;
  const r = project.render;
  const rendering = r && (r.status === "warteschlange" || r.status === "arbeitet");

  // Position in der neuen (geschnittenen) Zeit
  let newTime = 0;
  if (keep) {
    for (const [a, b] of keep) {
      if (time >= b) newTime += b - a;
      else {
        if (time > a) newTime += time - a;
        break;
      }
    }
  }

  return (
    <div className="page review">
      <div className="review-head">
        <a href="#/" className="link">
          ← All projects
        </a>
        <h2>{project.name}</h2>
        {project.info && (
          <span className="muted small">
            {formatTime(project.info.duration)} · {project.info.width}×{project.info.height} · {Math.round(project.info.fps)} fps
          </span>
        )}
      </div>
      {editMode && cuts && (
        <nav className="step-nav" aria-label="Steps">
          <a href="#step-cut" onClick={jump}>{cutMode ? "1 · Cut" : "1 · Texts"}</a>
          <a href="#step-effects" onClick={jump}>2 · Effects</a>
          <a href="#step-render" onClick={jump}>3 · Render</a>
          {cutMode && <a href="#step-reels" onClick={jump}>4 · Reels</a>}
          {cutMode && <a href="#step-texts" onClick={jump}>5 · Title &amp; texts</a>}
          {cutMode && <a href="#step-thumb" onClick={jump}>6 · Thumbnail</a>}
        </nav>
      )}

      {error && <div className="banner error">{error}</div>}

      {!ready && (
        <div className={`banner ${project.status === "fehler" ? "error" : ""}`}>
          {project.status === "fehler" ? (
            <>
              ⚠ {project.error}{" "}
              <button className="link" onClick={() => api.retry(id).then(setProject)}>
                try again
              </button>
            </>
          ) : (
            <>
              <progress value={project.progress} max={1} /> {project.message} · total {Math.round(project.progress * 100)} %
              {busyWith && <div className="small">The app is first finishing: {busyWith}. Your video starts right after.</div>}
            </>
          )}
        </div>
      )}

      {cutMode && cuts && (
        <div className="card cut-bar">
          <div className="cut-stats">
            <span className="big">
              {formatTime(oldDur)} → <strong>{formatTime(newDur)}</strong>
            </span>
            <span className="muted small">{oldDur ? `${Math.round((1 - newDur / oldDur) * 100)} % shorter` : ""}</span>
          </div>
          <div className="legend small">
            {(Object.keys(TYPE_LABEL) as CutType[]).map((t) =>
              counts[t] ? (
                <span key={t} className={`chip cut-${t}`}>
                  {TYPE_LABEL[t]}: {counts[t]}
                </span>
              ) : null,
            )}
            {pausesCut > 0 && <span className="chip cut-pause">Pauses shortened: {pausesCut}</span>}
            {noisesCut > 0 && <span className="chip cut-fuellwort">Sounds without words: {noisesCut}</span>}
            {suggestions > 0 && <span className="chip suggestion">Suggestions: {suggestions}</span>}
          </div>
          <div className="tempo" role="radiogroup" aria-label="Tempo">
            <span className="small muted">Tempo</span>
            {(["locker", "normal", "straff"] as const).map((t) => (
              <button
                key={t}
                role="radio"
                aria-checked={cuts.cutlist.settings.tempo === t}
                className={cuts.cutlist.settings.tempo === t ? "on" : ""}
                disabled={busy}
                onClick={() => run(() => api.cutSettings(id, { tempo: t }))}
              >
                {TEMPO_LABEL[t]}
              </button>
            ))}
          </div>
          <div className="cut-actions">
            <button className="btn ghost" disabled={!cuts.can_undo || busy} onClick={() => run(() => api.undo(id))} title="Ctrl+Z">
              ↶ Undo
            </button>
          </div>
        </div>
      )}

      <div className={`review-grid ${portrait ? "portrait" : ""}`}>
        <div className="player card">
          {project.step !== "pruefen" && project.step !== "ton" && project.step !== "vorschau" && project.info ? (
            <div className="video-wrap">
              <video ref={video} src={api.proxyUrl(id)} controls preload="auto" playsInline />
              {editMode && (preview || reelMode) && cuts && <TextOverlay time={time} cuts={cuts} words={words} subLines={subLines} faceBox={faceBox} portrait={portrait} />}
            </div>
          ) : (
            <div className="player-placeholder muted">Creating preview video …</div>
          )}

          {cutMode && keep && duration > 0 && (
            <>
              <label className="preview-toggle small">
                <input type="checkbox" checked={preview} onChange={(e) => setPreview(e.target.checked)} /> Play preview with cuts
                <span className="muted"> · {preview ? `${formatTime(newTime)} / ${formatTime(newDur)}` : `${formatTime(time)} / ${formatTime(duration)}`}</span>
              </label>
              <div
                className="timeline"
                title="Grey = gets cut. Click jumps there."
                onClick={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  seek(((e.clientX - rect.left) / rect.width) * duration, false);
                }}
              >
                {keep.map(([a, b], k) => (
                  <span key={k} className="keep" style={{ left: `${(a / duration) * 100}%`, width: `${((b - a) / duration) * 100}%` }} />
                ))}
                <span className="playhead" style={{ left: `${(time / duration) * 100}%` }} />
              </div>
            </>
          )}

          {transcript && (
            <p className="small muted facts-line">
              {transcript.language === "de" ? "German" : transcript.language === "en" ? "English" : transcript.language}
              {" · "}{words.length} words{" · "}{words.filter((w) => w.p < 0.5).length} unsure
              {" · "}speech recognition: {transcript.model} ({transcript.device})
            </p>
          )}

          {editMode && (
            <div className="render-box" id="step-render">
              <h3>{reelMode ? "Render reel" : "Final render"}</h3>
              <p className="small muted">
                {reelMode
                  ? "Length, pace, format and sound stay exactly as in the original. Only your texts are added. Under 30 MB."
                  : "The finished video is only created when you click here. Your original stays unchanged."}
              </p>
              {cuts && (
                <div className="render-options small">
                  {!reelMode && (
                  <>
                  <label>
                    <input type="checkbox" checked={cuts.cutlist.render_options.zoom} disabled={busy} onChange={(e) => run(() => api.renderOptions(id, { zoom: e.target.checked }))} />{" "}
                    Zoom change at cuts (100/108/115 %)
                  </label>
                  <label>
                    <input type="checkbox" checked={cuts.cutlist.render_options.loudness} disabled={busy} onChange={(e) => run(() => api.renderOptions(id, { loudness: e.target.checked }))} />{" "}
                    Even out loudness (−14 LUFS for YouTube)
                  </label>
                  <label>
                    <input type="checkbox" checked={cuts.cutlist.render_options.denoise} disabled={busy} onChange={(e) => run(() => api.renderOptions(id, { denoise: e.target.checked }))} />{" "}
                    Reduce noise
                  </label>
                  <label>
                    <input type="checkbox" checked={!!cuts.cutlist.render_options.declick} disabled={busy} onChange={(e) => run(() => api.renderOptions(id, { declick: e.target.checked }))} />{" "}
                    Remove mouth clicks (lip smacks, "Schmatzen")
                  </label>
                  </>
                  )}
                  <label>
                    Subtitles{" "}
                    <select value={cuts.cutlist.render_options.subtitles} disabled={busy} onChange={(e) => run(() => api.renderOptions(id, { subtitles: e.target.value as "aus" }))}>
                      <option value="aus">none</option>
                      <option value="srt">only as SRT file</option>
                      <option value="einbrennen">burn into the video (+ SRT)</option>
                    </select>
                  </label>
                  {cuts.cutlist.render_options.subtitles === "einbrennen" && (
                    <label>
                      <input type="checkbox" checked={cuts.cutlist.render_options.karaoke} disabled={busy} onChange={(e) => run(() => api.renderOptions(id, { karaoke: e.target.checked }))} />{" "}
                      Karaoke (spoken word turns purple)
                    </label>
                  )}
                </div>
              )}
              <div className="render-row">
                {!reelMode && (
                <select value={quality} onChange={(e) => setQuality(e.target.value)} disabled={!!rendering}>
                  {Object.entries(QUALITIES).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
                )}
                <button className="btn" onClick={startRender} disabled={!!rendering || busy || !newDur}>
                  {reelMode ? "Render reel" : "Final render"}
                </button>
              </div>
              {rendering && r && (
                <div className="small">
                  <progress value={r.progress} max={1} /> {r.message}{" "}
                  <button className="link danger" onClick={async () => {
                    if (!confirm("Cancel this render? The half-finished video is deleted.")) return;
                    try { setProject(await api.cancelRender(id)); } catch (e) { setError((e as Error).message); }
                  }}>✕ Cancel</button>
                </div>
              )}
              {r?.status === "abgebrochen" && <div className="small muted">Render cancelled.</div>}
              {doneMsg && !rendering && <div className="banner small">{doneMsg}</div>}
              <label className="small check-line">
                <input type="checkbox" checked={autoDl} onChange={(e) => {
                  setAutoDl(e.target.checked);
                  try { localStorage.setItem("final-auto-download", e.target.checked ? "1" : "0"); } catch { /* egal */ }
                }} />{" "}
                Download the finished video automatically
              </label>
              {r?.status === "fehler" && <div className="small error-text">⚠ {r.error}</div>}
              {!!project.exports?.length && !rendering && (() => {
                const shown = watch ?? project.exports[project.exports.length - 1].file;
                return (
                  <div className="watch">
                    <h4>Your finished video</h4>
                    <video key={shown} className="watch-video" src={api.exportWatchUrl(id, shown)} controls preload="metadata" playsInline />
                    <div className="small muted">{shown}</div>
                  </div>
                );
              })()}
              {!!project.exports?.length && (
                <ul className="exports small">
                  {[...project.exports].reverse().map((x) => (
                    <li key={x.file}>
                      <button className="link" onClick={() => setWatch(x.file)}>▶ watch</button>{" "}
                      <a href={api.exportUrl(id, x.file)} download>
                        ⬇ {x.file}
                      </a>
                      <span className="muted">
                        {" "}
                        · {formatTime(x.duration)} · {formatSize(x.size)}
                      </span>
                    </li>
                  ))}
                  <li>
                    <button className="link" onClick={() => api.openFolder(id).catch((e) => setError(e.message))}>
                      Open export folder
                    </button>
                  </li>
                </ul>
              )}
            </div>
          )}
        </div>

        <div className="card transcript-card" id="step-cut">
          <div className="transcript-toolbar">
            <h3>Transcript</h3>
            <label className="small">
              <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> follow along
            </label>
          </div>
          {cutMode ? (
            <p className="muted small hint">
              <span className="demo cut-retake">Struck through</span> = gets cut, <span className="demo suggestion">dashed</span> = suggestion.
              Click a word to select it (Shift+click for several). <kbd>Del</kbd> deletes, <kbd>Ctrl+Z</kbd> undoes.
            </p>
          ) : reelMode ? (
            <p className="muted small hint">
              Nothing gets cut here. Click a word → <strong>"★ Make buzzword"</strong>: it pops up in the reel.
              You set the hook card in the "Reel package" below.
            </p>
          ) : (
            <p className="muted small hint">
              Click a word to jump there in the video. <span className="unsure">Dotted</span> = speech recognition was unsure.
            </p>
          )}

          {editMode && sel && (
            <div className="action-bar">
              <div className="small">
                <strong>"{selWords.slice(0, 12).map((k) => words[k]?.w).join(" ")}{selWords.length > 12 ? " …" : ""}"</strong>
                {selDetExact && <div className="muted">{selDetExact.active ? selDetExact.reason : `Suggestion: ${selDetExact.reason}`}</div>}
                {!selDetExact && selDet && cutMode && selDet.end - selDet.start > 1 && (
                  <div className="muted">
                    Part of a {selDet.active ? "cut" : "suggestion"} ({selDet.end - selDet.start} words).{" "}
                    <button className="link" onClick={() => setSel([selDet.start, selDet.end - 1])}>select the whole part</button>
                  </div>
                )}
              </div>
              <div className="action-buttons">
                {!cutMode ? null : selDetExact && !selDetExact.active ? (
                  <button className="btn" disabled={busy} onClick={() => run(() => api.toggleCut(id, selDetExact.id, true))}>
                    Accept suggestion (cut)
                  </button>
                ) : selHasCut ? (
                  <button className="btn" disabled={busy} onClick={restoreSel}>
                    Undo this cut
                  </button>
                ) : (
                  <button className="btn danger" disabled={busy} onClick={deleteSel}>
                    Delete
                  </button>
                )}
                {!selHasCut && (
                  <button
                    className="btn ghost"
                    disabled={busy}
                    onClick={() => run(() => api.buzzword(id, sel[0], sel[1] + 1, !buzzOf.has(sel[0])))}
                    title="Shown in the video as an animated text pop-up"
                  >
                    {buzzOf.has(sel[0]) ? "★ Remove buzzword" : "★ Make buzzword"}
                  </button>
                )}
                <button className="btn ghost" onClick={() => seek(words[sel[0]].s)}>
                  ▶ Listen
                </button>
                {cutMode && (
                  <button className="btn ghost" disabled={busy || makingReel}
                    title="A reel from exactly this part (rounded to whole sentences). Claude writes hook, texts and caption."
                    onClick={async () => {
                      setMakingReel(true);
                      try {
                        const r = await api.ownClip(id, sel[0], sel[1]);
                        window.dispatchEvent(new CustomEvent("clips-updated", { detail: r.new }));
                        setTimeout(() => document.getElementById(`clip-${r.new}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 400);
                        if (r.note) setError(`The reel is made, but Claude could not write the texts: ${r.note}`);
                      } catch (e) {
                        setError((e as Error).message);
                      } finally {
                        setMakingReel(false);
                      }
                    }}>
                    {makingReel ? "Making the reel …" : `🎬 Make a reel from this (${Math.round(words[sel[1]].e - words[sel[0]].s)} s)`}
                  </button>
                )}
                <span className="speed-btns small" title="Time-lapse / slow motion for the selected words">
                  Speed:
                  {[0.25, 0.5, 2, 4, 8].map((f) => (
                    <button key={f} className="link" disabled={busy} onClick={() => {
                      const a = words[sel[0]].s, b = words[sel[1]].e;
                      const rest = (cuts?.cutlist.speed ?? []).filter((r) => r.end <= a || r.start >= b);
                      run(() => api.setSpeed(id, [...rest, { start: a, end: b, factor: f, mute: f > 2 }]));
                    }}>{f < 1 ? (f === 0.25 ? "¼×" : "½×") : `${f}×`}</button>
                  ))}
                </span>
                <button className="link" onClick={() => setSel(null)}>
                  close
                </button>
              </div>
            </div>
          )}

          <div className={`transcript ${cutMode ? "editing" : ""}`} ref={textBox}>
            {!transcript && <p className="muted">The transcript appears here as soon as it is ready.</p>}
            {transcript && !transcript.segments.length && (
              <p className="muted">Nobody speaks in this clip. Write your idea in the reel package below – the texts are made from it.</p>
            )}
            {transcript?.segments.map((s, si) => (
              <p key={si} className="segment">
                <button className="time" onClick={() => seek(s.s)} title="Jump here">
                  {formatTime(s.s)}
                </button>
                {words
                  .filter((w) => w.seg === si)
                  .map((w) => {
                    const f = flags?.[w.i] ?? null;
                    const d = detOf.get(w.i);
                    const isSugg = !f && d && !d.active;
                    const pause = pauseAfter.get(w.i);
                    const cls = [
                      "word",
                      w.i === current ? "current" : "",
                      !cutMode && w.p < 0.5 ? "unsure" : "",
                      f ? `cut cut-${f}` : "",
                      isSugg ? "suggestion" : "",
                      sel && w.i >= sel[0] && w.i <= sel[1] ? "selected" : "",
                      buzzOf.has(w.i) && !f ? "buzz" : "",
                      (cuts?.cutlist.speed ?? []).some((r) => w.s >= r.start - 0.01 && w.e <= r.end + 0.01) ? "speed" : "",
                    ].join(" ");
                    const title = f
                      ? f === "manuell"
                        ? "Deleted by you"
                        : d?.reason ?? TYPE_LABEL[f]
                      : isSugg
                        ? `Suggestion: ${d!.reason}`
                        : `${formatTime(w.s)} · confidence: ${Math.round(w.p * 100)} %`;
                    return (
                      <Fragment key={w.i}>
                        <span data-i={w.i} className={cls} onClick={(e) => onWordClick(w, e)} title={title}>
                          {w.w}
                        </span>{" "}
                        {cutMode && pause && (
                          <button
                            className={`pause ${pause.kept ? "kept" : ""}`}
                            disabled={busy}
                            title={
                              pause.noise
                                ? pause.kept
                                  ? "Sound (e.g. \"mh\") stays. Click: cut it out"
                                  : "Sound without a word (e.g. \"mh\", \"meah\") gets cut out. Click: keep"
                                : pause.kept
                                  ? "Pause stays. Click: shorten"
                                  : "Pause gets shortened. Click: keep"
                            }
                            onClick={() => run(() => api.setPause(id, pause.after, !pause.kept))}
                          >
                            {pause.noise ? "🔊 Sound" : "⏸"} {pause.length.toFixed(1)} s
                          </button>
                        )}
                      </Fragment>
                    );
                  })}
              </p>
            ))}
          </div>

          {cutMode && cuts && (
            <CutSettingsPanel
              settings={cuts.cutlist.settings}
              busy={busy}
              onSave={(s) => run(() => api.cutSettings(id, s))}
              onReset={() => confirm("Discard all your changes and detect again?") && run(() => api.resetCuts(id))}
            />
          )}
        </div>
      </div>
      {editMode && cuts && <EffectsPanel id={id} cuts={cuts} onCuts={setCuts} time={time} onSeek={(t) => seek(t, false)}
        keep={cutMode ? cuts.evaluation.keep : undefined} />}
      {cutMode && <YoutubePackage id={id} />}
      {reelMode && cuts && <ReelPackage id={id} cuts={cuts} onCuts={setCuts} time={time} duration={duration} />}
    </div>
  );
}

function TextOverlay({
  time,
  cuts,
  words,
  subLines,
  faceBox,
  portrait,
}: {
  time: number;
  cuts: CutView;
  words: FlatWord[];
  subLines: { start: number; end: number; text: string }[];
  faceBox: number[] | null;
  portrait: boolean;
}) {
  const o = cuts.cutlist.render_options;
  const sub = o.subtitles === "einbrennen" ? subLines.find((l) => time >= l.start && time <= l.end) : undefined;
  const buzz = cuts.cutlist.buzzwords.find((b) => {
    const s = words[b.start]?.s ?? 0;
    const e = Math.max(s + 1.8, (words[b.end - 1]?.e ?? 0) + 0.8);
    return time >= s && time <= e;
  });
  const fb = faceBox ?? [0.3, 0.1, 0.7, 0.5];
  const hook = (cuts.cutlist.overlays ?? []).find((h) => h.on && h.kind !== "yt" && h.kind !== "fx" && time >= h.start && time <= h.end);
  const yt = (cuts.cutlist.overlays ?? []).find((h) => h.on && h.kind === "yt" && time >= h.start && time <= h.end);
  const fxNow = (cuts.cutlist.overlays ?? []).find((h) => h.on && h.kind === "fx" && time >= h.start && time <= h.end);
  const right = (fb[0] + fb[2]) / 2 < 0.55;
  const sideStyle: React.CSSProperties = right
    ? { left: `${Math.min(80, (fb[2] + 0.05) * 100)}%`, top: `${Math.max(18, ((fb[1] + fb[3]) / 2) * 100)}%` }
    : { right: `${100 - Math.max(20, (fb[0] - 0.05) * 100)}%`, top: `${Math.max(18, ((fb[1] + fb[3]) / 2) * 100)}%`, alignItems: "flex-end" };
  const chestStyle: React.CSSProperties = { left: `${((fb[0] + fb[2]) / 2) * 100}%`, top: `${Math.min(80, Math.max(56, (fb[3] + 0.26) * 100))}%` };
  const accent = (t: string) =>
    t.split(/(\*[^*]+\*)/).map((part, k) =>
      part.startsWith("*") && part.endsWith("*") ? <em key={k}>{part.slice(1, -1)}</em> : <span key={k}>{part}</span>,
    );
  const hookTop = !faceBox || fb[1] * 1920 > 280 + 300 ? 300 / 19.2 : Math.min(1250 - 300, fb[3] * 1920 + 40) / 19.2;
  const buzzStyle: React.CSSProperties = portrait
    ? { left: "50%", top: `${Math.min(62, Math.max((fb[3] + 0.04) * 100, 50))}%` }
    : { left: (fb[0] + fb[2]) / 2 < 0.5 ? "76%" : "24%", top: "42%" };
  const buzzText = buzz ? words.slice(buzz.start, buzz.end).map((w) => w.w.replace(/[.,!?;:…]+$/, "")).join(" ") : "";
  return (
    <div className="text-overlay" aria-hidden>
      {hook && (
        <span key={hook.id} className={`ov-hook anim-${hook.anim ?? "karte"}`} style={{ top: `${hookTop}%` }}>
          {hook.text.split(/(\*[^*]+\*)/).map((part, k) =>
            part.startsWith("*") && part.endsWith("*") ? <em key={k}>{part.slice(1, -1)}</em> : <span key={k}>{part}</span>,
          )}
        </span>
      )}
      {fxNow && (
        <span className="ov-fx-badge" title="Only a note while editing – the effect itself is in the final video. See its preview video in Effects.">
          ✦ effect here: {fxNow.type} (only a note – see preview in Effects)
        </span>
      )}
      {yt && (yt.style === "label" || yt.style === "quote") && (
        <span key={yt.id} className={`ov-yt ov-yt-${yt.style}`} style={chestStyle}>
          {yt.style === "label" ? yt.text.toUpperCase() : accent(yt.text)}
        </span>
      )}
      {yt && yt.style !== "label" && yt.style !== "quote" && (
        <div key={yt.id} className="ov-yt-side" style={sideStyle}>
          {yt.style === "number" && (
            <>
              <span className="ov-yt ov-yt-label">{yt.text.toUpperCase()}</span>
              <span className="ov-yt ov-yt-number">{yt.number}</span>
            </>
          )}
          {yt.style === "name" && (
            <>
              <span className="ov-yt ov-yt-name">{yt.text.split("|")[0]}</span>
              {yt.text.includes("|") && <span className="ov-yt ov-yt-title">{yt.text.split("|")[1]}</span>}
            </>
          )}
          {(yt.style === "sticker" || yt.style === "check") &&
            (yt.list ?? [])
              .filter((p) => time >= p.t)
              .map((p, k) => (
                <span key={k} className={`ov-yt ov-yt-sticker ${yt.style === "check" ? "check" : ""}`} style={{ rotate: k % 2 ? "1.5deg" : "-2deg" }}>
                  {yt.style === "sticker" ? p.text.toUpperCase() : p.text}
                </span>
              ))}
        </div>
      )}
      {buzz && !hook && !yt && (
        <span key={buzz.start} className="ov-buzz" style={buzzStyle}>
          {buzzText}
        </span>
      )}
      {sub && (
        <span className="ov-sub" style={{ top: portrait ? "70%" : "90%" }}>
          {sub.text}
        </span>
      )}
    </div>
  );
}

function CutSettingsPanel({
  settings,
  busy,
  onSave,
  onReset,
}: {
  settings: CutView["cutlist"]["settings"];
  busy: boolean;
  onSave: (s: Partial<CutView["cutlist"]["settings"]>) => void;
  onReset: () => void;
}) {
  const [signal, setSignal] = useState(settings.signal_words.join(", "));
  const [gap, setGap] = useState(settings.max_gap);
  useEffect(() => {
    setSignal(settings.signal_words.join(", "));
    setGap(settings.max_gap);
  }, [settings]);

  return (
    <details className="settings cut-settings">
      <summary>Settings for cut detection</summary>
      <div className="settings-grid">
        <div>
          <h4>Filler words</h4>
          <p className="small muted">Ticked = gets cut.</p>
          <div className="filler-list">
            {Object.entries(settings.fillers).map(([f, on]) => (
              <label key={f} className="small">
                <input type="checkbox" checked={on} disabled={busy} onChange={(e) => onSave({ fillers: { ...settings.fillers, [f]: e.target.checked } })} />{" "}
                {f}
              </label>
            ))}
          </div>
        </div>
        <div>
          <h4>Signal words for retakes</h4>
          <p className="small muted">If you say one of these on its own, the sentence before it gets removed. Separate with commas.</p>
          <textarea value={signal} onChange={(e) => setSignal(e.target.value)} rows={3} />
          <h4>Retake distance</h4>
          <p className="small muted">At most this many seconds of speaking may lie between the first attempt and the restart (thinking pauses do not count).</p>
          <input type="number" min={1} max={15} step={0.5} value={gap} onChange={(e) => setGap(Number(e.target.value))} /> seconds
          <div className="settings-buttons">
            <button className="btn" disabled={busy} onClick={() => onSave({ signal_words: signal.split(","), max_gap: gap })}>
              Apply
            </button>
            <button className="link danger" disabled={busy} onClick={onReset}>
              Reset everything
            </button>
          </div>
        </div>
      </div>
    </details>
  );
}
