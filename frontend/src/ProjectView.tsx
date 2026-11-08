import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, formatSize, formatTime, type CutType, type CutView, type Detection, type Project, type Transcript, type Word } from "./api";

interface FlatWord extends Word {
  i: number;
  seg: number;
}

const TYPE_LABEL: Record<CutType, string> = {
  retake: "Retake",
  signal: "Signalwort",
  doppelt: "Doppelt",
  fragment: "Abgebrochen",
  fuellwort: "Füllwort",
  blick: "Blick weg",
  manuell: "Von dir gelöscht",
};

const QUALITIES: Record<string, string> = {
  "1080": "1080p (empfohlen)",
  "2160": "4K (wenn das Original so groß ist)",
  original: "Original-Auflösung",
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
  const [suggesting, setSuggesting] = useState(false);
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
          if (p.mode === "youtube") {
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

  // Wort → Erkennung (für Tooltip und "Schnitt zurücknehmen")
  const detOf = useMemo(() => {
    const m = new Map<number, Detection>();
    cuts?.cutlist.detections.forEach((d) => {
      for (let k = d.start; k < d.end; k++) if (!m.has(k) || d.active) m.set(k, d);
    });
    return m;
  }, [cuts]);

  const buzzOf = useMemo(() => {
    const m = new Map<number, { start: number; end: number }>();
    cuts?.cutlist.buzzwords.forEach((b) => {
      for (let k = b.start; k < b.end; k++) m.set(k, b);
    });
    return m;
  }, [cuts]);

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
  const selDetExact = selDet && sel && sel[0] >= selDet.start && sel[1] < selDet.end ? selDet : undefined;

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
    const d = detOf.get(w.i);
    if (d && cutMode) setSel([d.start, d.end - 1]);
    else setSel([w.i, w.i]);
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
  if (!project) return <div className="page muted">Lädt …</div>;

  const ready = project.status === "fertig";
  const portrait = project.info ? project.info.height > project.info.width : false;
  const counts: Partial<Record<CutType, number>> = {};
  cuts?.cutlist.detections.forEach((d) => d.active && (counts[d.type] = (counts[d.type] ?? 0) + 1));
  if (cuts?.cutlist.manual.cut.length) counts.manuell = cuts.cutlist.manual.cut.length;
  const suggestions = cuts?.cutlist.detections.filter((d) => !d.active).length ?? 0;
  const pausesCut = cuts?.evaluation.pauses.filter((p) => !p.kept).length ?? 0;
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
          ← Alle Projekte
        </a>
        <h2>{project.name}</h2>
        {project.info && (
          <span className="muted small">
            {formatTime(project.info.duration)} · {project.info.width}×{project.info.height} · {Math.round(project.info.fps)} fps
          </span>
        )}
      </div>

      {error && <div className="banner error">{error}</div>}

      {!ready && (
        <div className={`banner ${project.status === "fehler" ? "error" : ""}`}>
          {project.status === "fehler" ? (
            <>
              ⚠ {project.error}{" "}
              <button className="link" onClick={() => api.retry(id).then(setProject)}>
                nochmal versuchen
              </button>
            </>
          ) : (
            <>
              <progress value={project.progress} max={1} /> {project.message} · gesamt {Math.round(project.progress * 100)} %
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
            <span className="muted small">{oldDur ? `${Math.round((1 - newDur / oldDur) * 100)} % kürzer` : ""}</span>
          </div>
          <div className="legend small">
            {(Object.keys(TYPE_LABEL) as CutType[]).map((t) =>
              counts[t] ? (
                <span key={t} className={`chip cut-${t}`}>
                  {TYPE_LABEL[t]}: {counts[t]}
                </span>
              ) : null,
            )}
            {pausesCut > 0 && <span className="chip cut-pause">Pausen gekürzt: {pausesCut}</span>}
            {suggestions > 0 && <span className="chip suggestion">Vorschläge: {suggestions}</span>}
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
                {t}
              </button>
            ))}
          </div>
          <div className="cut-actions">
            <button className="btn ghost" disabled={!cuts.can_undo || busy} onClick={() => run(() => api.undo(id))} title="Strg+Z">
              ↶ Rückgängig
            </button>
          </div>
        </div>
      )}

      <div className={`review-grid ${portrait ? "portrait" : ""}`}>
        <div className="player card">
          {project.step !== "pruefen" && project.step !== "ton" && project.step !== "vorschau" && project.info ? (
            <div className="video-wrap">
              <video ref={video} src={api.proxyUrl(id)} controls preload="auto" playsInline />
              {cutMode && preview && cuts && <TextOverlay time={time} cuts={cuts} words={words} subLines={subLines} faceBox={faceBox} portrait={portrait} />}
            </div>
          ) : (
            <div className="player-placeholder muted">Vorschau-Video wird erstellt …</div>
          )}

          {cutMode && keep && duration > 0 && (
            <>
              <label className="preview-toggle small">
                <input type="checkbox" checked={preview} onChange={(e) => setPreview(e.target.checked)} /> Vorschau mit Schnitten
                abspielen
                <span className="muted"> · {preview ? `${formatTime(newTime)} / ${formatTime(newDur)}` : `${formatTime(time)} / ${formatTime(duration)}`}</span>
              </label>
              <div
                className="timeline"
                title="Grau = wird geschnitten. Klick springt dorthin."
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
            <dl className="facts small">
              <div>
                <dt>Sprache</dt>
                <dd>{transcript.language === "de" ? "Deutsch" : transcript.language === "en" ? "Englisch" : transcript.language}</dd>
              </div>
              <div>
                <dt>Wörter</dt>
                <dd>{words.length}</dd>
              </div>
              <div>
                <dt>Modell</dt>
                <dd>
                  {transcript.model} ({transcript.device})
                </dd>
              </div>
              <div>
                <dt>Unsicher erkannt</dt>
                <dd>{words.filter((w) => w.p < 0.5).length}</dd>
              </div>
            </dl>
          )}

          {cutMode && (
            <div className="render-box">
              <h3>Final rendern</h3>
              <p className="small muted">Erst wenn du hier klickst, entsteht das fertige Video. Dein Original bleibt unverändert.</p>
              {cuts && (
                <div className="render-options small">
                  <label>
                    <input type="checkbox" checked={cuts.cutlist.render_options.zoom} disabled={busy} onChange={(e) => run(() => api.renderOptions(id, { zoom: e.target.checked }))} />{" "}
                    Zoom-Wechsel bei Schnitten (100/108/115 %)
                  </label>
                  <label>
                    <input type="checkbox" checked={cuts.cutlist.render_options.loudness} disabled={busy} onChange={(e) => run(() => api.renderOptions(id, { loudness: e.target.checked }))} />{" "}
                    Lautstärke angleichen (−14 LUFS für YouTube)
                  </label>
                  <label>
                    <input type="checkbox" checked={cuts.cutlist.render_options.denoise} disabled={busy} onChange={(e) => run(() => api.renderOptions(id, { denoise: e.target.checked }))} />{" "}
                    Rauschen mindern
                  </label>
                  <label>
                    Untertitel{" "}
                    <select value={cuts.cutlist.render_options.subtitles} disabled={busy} onChange={(e) => run(() => api.renderOptions(id, { subtitles: e.target.value as "aus" }))}>
                      <option value="aus">keine</option>
                      <option value="srt">nur als SRT-Datei</option>
                      <option value="einbrennen">ins Video einbrennen (+ SRT)</option>
                    </select>
                  </label>
                  {cuts.cutlist.render_options.subtitles === "einbrennen" && (
                    <label>
                      <input type="checkbox" checked={cuts.cutlist.render_options.karaoke} disabled={busy} onChange={(e) => run(() => api.renderOptions(id, { karaoke: e.target.checked }))} />{" "}
                      Karaoke (gesprochenes Wort wird lila)
                    </label>
                  )}
                  <div className="buzz-row">
                    <span>★ Buzzwords: {cuts.cutlist.buzzwords.length}</span>
                    <button
                      className="link"
                      disabled={suggesting || busy}
                      onClick={async () => {
                        setSuggesting(true);
                        await run(() => api.suggestBuzz(id));
                        setSuggesting(false);
                      }}
                    >
                      {suggesting ? "lokale KI denkt nach …" : "vorschlagen lassen (Ollama)"}
                    </button>
                  </div>
                </div>
              )}
              <div className="render-row">
                <select value={quality} onChange={(e) => setQuality(e.target.value)} disabled={!!rendering}>
                  {Object.entries(QUALITIES).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
                <button className="btn" onClick={startRender} disabled={!!rendering || busy || !newDur}>
                  Final rendern
                </button>
              </div>
              {rendering && r && (
                <div className="small">
                  <progress value={r.progress} max={1} /> {r.message}
                </div>
              )}
              {r?.status === "fehler" && <div className="small error-text">⚠ {r.error}</div>}
              {!!project.exports?.length && (
                <ul className="exports small">
                  {[...project.exports].reverse().map((x) => (
                    <li key={x.file}>
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
                      Export-Ordner öffnen
                    </button>
                  </li>
                </ul>
              )}
            </div>
          )}
        </div>

        <div className="card transcript-card">
          <div className="transcript-toolbar">
            <h3>Transkript</h3>
            <label className="small">
              <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> mitscrollen
            </label>
          </div>
          {cutMode ? (
            <p className="muted small hint">
              <span className="demo cut-retake">Durchgestrichen</span> = wird geschnitten, <span className="demo suggestion">gestrichelt</span> = Vorschlag.
              Klick auf ein Wort wählt es aus (Umschalt+Klick für mehrere). <kbd>Entf</kbd> löscht, <kbd>Strg+Z</kbd> macht rückgängig.
            </p>
          ) : (
            <p className="muted small hint">
              Klick auf ein Wort springt im Video dorthin. <span className="unsure">Gepunktet</span> = Spracherkennung war unsicher.
            </p>
          )}

          {cutMode && sel && (
            <div className="action-bar">
              <div className="small">
                <strong>„{selWords.slice(0, 12).map((k) => words[k]?.w).join(" ")}{selWords.length > 12 ? " …" : ""}“</strong>
                {selDetExact && <div className="muted">{selDetExact.active ? selDetExact.reason : `Vorschlag: ${selDetExact.reason}`}</div>}
              </div>
              <div className="action-buttons">
                {selDetExact && !selDetExact.active ? (
                  <button className="btn" disabled={busy} onClick={() => run(() => api.toggleCut(id, selDetExact.id, true))}>
                    Vorschlag übernehmen (schneiden)
                  </button>
                ) : selHasCut ? (
                  <button className="btn" disabled={busy} onClick={restoreSel}>
                    Schnitt zurücknehmen
                  </button>
                ) : (
                  <button className="btn danger" disabled={busy} onClick={deleteSel}>
                    Löschen
                  </button>
                )}
                {!selHasCut && (
                  <button
                    className="btn ghost"
                    disabled={busy}
                    onClick={() => run(() => api.buzzword(id, sel[0], sel[1] + 1, !buzzOf.has(sel[0])))}
                    title="Wird im Video als animierte Text-Einblendung gezeigt"
                  >
                    {buzzOf.has(sel[0]) ? "★ Buzzword entfernen" : "★ Als Buzzword"}
                  </button>
                )}
                <button className="btn ghost" onClick={() => seek(words[sel[0]].s)}>
                  ▶ Anhören
                </button>
                <button className="link" onClick={() => setSel(null)}>
                  schließen
                </button>
              </div>
            </div>
          )}

          <div className={`transcript ${cutMode ? "editing" : ""}`} ref={textBox}>
            {!transcript && <p className="muted">Das Transkript erscheint hier, sobald es fertig ist.</p>}
            {transcript?.segments.map((s, si) => (
              <p key={si} className="segment">
                <button className="time" onClick={() => seek(s.s)} title="Hierher springen">
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
                    ].join(" ");
                    const title = f
                      ? f === "manuell"
                        ? "Von dir gelöscht"
                        : d?.reason ?? TYPE_LABEL[f]
                      : isSugg
                        ? `Vorschlag: ${d!.reason}`
                        : `${formatTime(w.s)} · sicher erkannt: ${Math.round(w.p * 100)} %`;
                    return (
                      <Fragment key={w.i}>
                        <span data-i={w.i} className={cls} onClick={(e) => onWordClick(w, e)} title={title}>
                          {w.w}
                        </span>{" "}
                        {cutMode && pause && (
                          <button
                            className={`pause ${pause.kept ? "kept" : ""}`}
                            disabled={busy}
                            title={pause.kept ? "Pause bleibt. Klick: kürzen" : "Pause wird gekürzt. Klick: behalten"}
                            onClick={() => run(() => api.setPause(id, pause.after, !pause.kept))}
                          >
                            ⏸ {pause.length.toFixed(1).replace(".", ",")} s
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
              onReset={() => confirm("Alle deine Änderungen verwerfen und neu erkennen?") && run(() => api.resetCuts(id))}
            />
          )}
        </div>
      </div>
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
  const buzzStyle: React.CSSProperties = portrait
    ? { left: "50%", top: `${Math.min(62, Math.max((fb[3] + 0.04) * 100, 50))}%` }
    : { left: (fb[0] + fb[2]) / 2 < 0.5 ? "76%" : "24%", top: "42%" };
  const buzzText = buzz ? words.slice(buzz.start, buzz.end).map((w) => w.w.replace(/[.,!?;:…]+$/, "")).join(" ") : "";
  return (
    <div className="text-overlay" aria-hidden>
      {buzz && (
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
      <summary>Einstellungen für die Schnitt-Erkennung</summary>
      <div className="settings-grid">
        <div>
          <h4>Füllwörter</h4>
          <p className="small muted">Angehakt = wird geschnitten.</p>
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
          <h4>Signalwörter für Retakes</h4>
          <p className="small muted">Wenn du eins davon allein sagst, fliegt der Satz davor raus. Mit Komma trennen.</p>
          <textarea value={signal} onChange={(e) => setSignal(e.target.value)} rows={3} />
          <h4>Retake-Abstand</h4>
          <p className="small muted">So viele Sekunden Sprechen dürfen höchstens zwischen erstem Versuch und Neuanfang liegen (Denkpausen zählen nicht).</p>
          <input type="number" min={1} max={15} step={0.5} value={gap} onChange={(e) => setGap(Number(e.target.value))} /> Sekunden
          <div className="settings-buttons">
            <button className="btn" disabled={busy} onClick={() => onSave({ signal_words: signal.split(","), max_gap: gap })}>
              Übernehmen
            </button>
            <button className="link danger" disabled={busy} onClick={onReset}>
              Alles zurücksetzen
            </button>
          </div>
        </div>
      </div>
    </details>
  );
}
