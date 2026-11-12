import { useEffect, useRef, useState } from "react";
import { api, formatSize, formatTime, type Clip } from "./api";
import { Status } from "./ReelPackage";
import { EffectsEditor } from "./EffectsPanel";
import { ReelParts, ReelWish } from "./ReelEdit";

function copy(text: string, done: (m: string) => void) {
  navigator.clipboard.writeText(text).then(
    () => done("Copied ✓"),
    () => done("Copying did not work – please select the text and press Ctrl+C."),
  );
}

/** Reels aus einem langen YouTube-Video: Vorschläge (Claude/Ollama), Wünsche, Vorschau, Rendern. */
export function ClipsPanel({ id }: { id: string }) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [feedback, setFeedback] = useState("");
  const [engine, setEngine] = useState<"claude" | "ollama">("claude");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api.clips(id).then((d) => setClips(d.clips)).catch((e) => setErr(e.message));
  }, [id]);

  // Während gerendert wird, regelmäßig nachsehen
  useEffect(() => {
    if (!clips.some((c) => c.status === "warteschlange" || c.status === "arbeitet")) return;
    const t = setInterval(() => api.clips(id).then((d) => setClips(d.clips)).catch(() => {}), 1500);
    return () => clearInterval(t);
  }, [clips, id]);

  // Fertig gerenderte Reels gleich herunterladen (landen im Download-Ordner) – abschaltbar
  const [autoDl, setAutoDl] = useState(() => {
    try { return localStorage.getItem("reel-auto-download") !== "0"; } catch { return true; }
  });
  const lastStatus = useRef<Record<string, string>>({});
  useEffect(() => {
    for (const c of clips) {
      const before = lastStatus.current[c.id];
      if ((before === "warteschlange" || before === "arbeitet") && c.status === "fertig" && c.file && !autoDl) {
        setMsg(`"${c.title}" is ready ✓ – press "Download this reel" below it.`);
      } else if ((before === "warteschlange" || before === "arbeitet") && c.status === "fertig" && c.file) {
        const a = document.createElement("a");
        a.href = api.exportUrl(id, c.file);
        a.download = c.file;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setMsg(`"${c.title}" is ready ✓ – downloaded to your Downloads folder.`);
      }
      lastStatus.current[c.id] = c.status;
    }
  }, [clips, id, autoDl]);

  const suggest = async (eng: "claude" | "ollama", withFeedback: boolean) => {
    setEngine(eng);
    setBusy("suggest");
    setErr(null);
    setMsg(null);
    try {
      const d = await api.suggestClips(id, eng, withFeedback ? feedback : "");
      setClips(d.clips);
      if (withFeedback) setFeedback("");
      setMsg(`${d.clips.filter((c) => c.status === "vorschlag").length} reel suggestions ✓ – see below.`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const vorschlaege = clips.filter((c) => c.status === "vorschlag").length;

  return (
    <div className="card clips-card">
      <h3>Reels from this video</h3>
      <p className="small muted">
        Claude finds the strongest 15–20-second moments, with a hook at second 0. Pieces may come from different parts of the video.
        Landscape videos are placed in the middle of the portrait frame without zoom (black bars, hook text at the top).
      </p>
      <div className="row-buttons">
        <button className="btn" disabled={!!busy} onClick={() => suggest("claude", false)}>
          {busy === "suggest" && engine === "claude" ? "Claude is searching … (about 30–90 s)" : "Suggest with Claude"}
        </button>
        <button className="btn ghost" disabled={!!busy} onClick={() => suggest("ollama", false)}>
          {busy === "suggest" && engine === "ollama" ? "Local AI is searching … (2–5 min)" : "Free with Ollama"}
        </button>
      </div>
      {vorschlaege > 0 && (
        <div className="feedback-box">
          <label className="small">
            Wishes to refine (e.g. "more provocative hooks", "more about boundaries", "shorter, 15 s")
            <textarea rows={2} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
          </label>
          <button className="btn ghost" disabled={!!busy || !feedback.trim()} onClick={() => suggest(engine, true)}>
            Suggest again with these wishes
          </button>
        </div>
      )}
      <Status busy={busy} err={err} msg={msg} />
      {err?.includes("Settings") && <a className="small" href="#/einstellungen">→ go to Settings</a>}
      <label className="small" style={{ display: "block", margin: "8px 0" }}>
        <input type="checkbox" checked={autoDl} onChange={(e) => {
          setAutoDl(e.target.checked);
          try { localStorage.setItem("reel-auto-download", e.target.checked ? "1" : "0"); } catch { /* egal */ }
        }} />{" "}
        Download each reel automatically when it is ready (off = only when you press its download button)
      </label>
      <div className="clip-list">
        {clips.map((c) => (
          <ClipCard key={c.id} id={id} clip={c} onChange={setClips} onMsg={setMsg} onErr={setErr} />
        ))}
      </div>
    </div>
  );
}

function ClipCard({ id, clip, onChange, onMsg, onErr }: {
  id: string; clip: Clip; onChange: (c: Clip[]) => void; onMsg: (m: string) => void; onErr: (m: string) => void;
}) {
  const [hook, setHook] = useState(clip.hook_text);
  const [texts, setTexts] = useState((clip.texts ?? []).join("\n"));
  useEffect(() => setHook(clip.hook_text), [clip.hook_text]);
  useEffect(() => setTexts((clip.texts ?? []).join("\n")), [JSON.stringify(clip.texts)]);
  const [playing, setPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const video = useRef<HTMLVideoElement>(null);
  // Wie im fertigen Reel: Hook ab Sekunde 0, danach die weiteren Texte gleichmäßig verteilt
  const plan = (() => {
    const out: { s: number; e: number; text: string; hook: boolean }[] = [];
    const total = clip.duration;
    const hookEnd = Math.min(total, 4.6);
    if (hook.trim()) out.push({ s: 0, e: hookEnd, text: hook, hook: true });
    const rest = (clip.texts ?? []).filter((t) => t.trim());
    if (rest.length && total - hookEnd > 2.5) {
      const slot = (total - hookEnd) / rest.length;
      rest.forEach((t, i) => out.push({ s: hookEnd + i * slot + 0.15, e: hookEnd + (i + 1) * slot - 0.1, text: t, hook: false }));
    }
    return out;
  })();
  const shown = plan.find((p) => elapsed >= p.s && elapsed <= p.e) ?? (playing ? undefined : plan[0]);
  useEffect(() => setHook(clip.hook_text), [clip.hook_text]);

  // Vorschau: die Stücke nacheinander aus dem Vorschau-Video abspielen
  const preview = () => {
    const v = video.current;
    if (!v) return;
    let k = 0;
    let done = 0; // Länge der schon gespielten Stücke
    const segs = clip.segments;
    setPlaying(true);
    setElapsed(0);
    v.currentTime = segs[0][0];
    void v.play();
    const tick = () => {
      if (!v || v.paused) return;
      if (v.currentTime >= segs[k][1]) {
        done += segs[k][1] - segs[k][0];
        k += 1;
        if (k >= segs.length) {
          v.pause();
          setPlaying(false);
          setElapsed(0);
          return;
        }
        v.currentTime = segs[k][0];
      }
      setElapsed(done + Math.max(0, v.currentTime - segs[k][0]));
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };

  const run = async (fn: () => Promise<{ clips: Clip[] }>) => {
    try {
      onChange((await fn()).clips);
    } catch (e) {
      onErr((e as Error).message);
    }
  };

  const rendering = clip.status === "warteschlange" || clip.status === "arbeitet";
  return (
    <div className={`clip ${clip.status}`}>
      <div className="clip-video">
        <div className="clip-frame">
          <video ref={video} src={api.proxyUrl(id)} preload="metadata" playsInline disablePictureInPicture
            onPause={() => setPlaying(false)} />
          {shown && (
            <span key={shown.text} className={`clip-ov ${shown.hook ? "hook" : ""}`}>
              {shown.text.split(/(\*[^*]+\*)/).map((part, k) =>
                part.startsWith("*") && part.endsWith("*") ? <em key={k}>{part.slice(1, -1)}</em> : <span key={k}>{part}</span>,
              )}
            </span>
          )}
        </div>
        <button className="btn ghost small-btn" onClick={() => (playing ? video.current?.pause() : preview())}>
          {playing ? "❚❚ Stop" : "▶ Preview"}
        </button>
      </div>
      <div className="clip-body">
        <div className="clip-title">
          <strong>{clip.title}</strong>
          <span className="pill">{formatTime(clip.duration)}</span>
          {clip.status === "fertig" && <span className="pill ok-pill">done</span>}
        </div>
        {clip.why && <div className="small muted">{clip.why}</div>}
        {clip.warnings?.map((w) => (
          <div key={w} className="small error-text">⚠ {w}</div>
        ))}
        <label className="small">
          Hook text at the top (*word* = purple)
          <input
            value={hook}
            onChange={(e) => setHook(e.target.value)}
            onBlur={() => hook !== clip.hook_text && run(() => api.editClip(id, clip.id, { hook_text: hook }))}
          />
        </label>
        <label className="small field">
          Extra texts on screen (one per line, shown one after another)
          <textarea rows={2} value={texts} onChange={(e) => setTexts(e.target.value)}
            onBlur={() => texts !== (clip.texts ?? []).join("\n") &&
              run(() => api.editClip(id, clip.id, { texts: texts.split("\n").map((x) => x.trim()).filter(Boolean) }))} />
        </label>
        <label className="small check">
          <input type="checkbox" checked={clip.subs ?? true} disabled={rendering}
            onChange={(e) => run(() => api.editClip(id, clip.id, { subs: e.target.checked }))} />{" "}
          Subtitles in the reel (word by word, burned in)
        </label>
        <details className="small">
          <summary>What is said – cut sentences or add more ({formatTime(clip.duration)})</summary>
          <ReelParts id={id} clip={clip} run={run} busy={rendering} />
        </details>
        <ReelWish id={id} clip={clip} run={run} />
        <details className="small">
          <summary>Caption, 5 hashtags, Shorts title</summary>
          <p className="pre">{clip.caption}</p>
          <p>{clip.hashtags.join(" ")}</p>
          <p>
            <em>{clip.shorts_title}</em>
          </p>
          <button className="link" onClick={() => copy(clip.caption + "\n\n" + clip.hashtags.join(" "), onMsg)}>
            Copy caption + hashtags
          </button>{" "}
          <button className="link" onClick={() => copy(clip.shorts_title, onMsg)}>
            Copy Shorts title
          </button>
        </details>
        <details className="small clip-fx">
          <summary>Effects in this reel ({(clip.fx ?? []).filter((o) => o.on).length})</summary>
          <EffectsEditor
            compact
            exclude={["vanish", "flash", "speed"]}
            items={clip.fx ?? []}
            endAt={clip.duration}
            time={elapsed}
            onSeek={() => preview()}
            preview={(item, signal) => api.clipEffectPreview(id, clip.id, item, signal)}
            onSave={async (list) => onChange((await api.setClipEffects(id, clip.id, list)).clips)}
            onSuggest={async (engine, allowed, wish) => {
              const d = await api.suggestClipEffects(id, clip.id, engine, allowed, wish);
              onChange(d.clips);
              return d.clips.find((c) => c.id === clip.id)?.fx?.length ?? 0;
            }}
          />
        </details>
        <div className="row-buttons">
          <button className="btn" disabled={rendering} onClick={() => run(() => api.renderClip(id, clip.id))}>
            {clip.status === "fertig" ? "Render again" : "Looks good – render reel"}
          </button>
          <button className="link danger" disabled={rendering} onClick={() => confirm("Discard this suggestion?") && run(() => api.deleteClip(id, clip.id))}>
            discard
          </button>
        </div>
        {rendering && (
          <div className="small">
            <progress value={clip.progress ?? 0} max={1} /> {clip.message}{" "}
            <button className="link danger" onClick={() => confirm("Cancel rendering this reel?") && run(() => api.cancelClip(id, clip.id))}>
              ✕ Cancel
            </button>
          </div>
        )}
        {clip.status === "fehler" && <div className="small error-text">⚠ {clip.error}</div>}
        {clip.file && (
          <video className="watch-video" src={api.exportWatchUrl(id, clip.file)} controls preload="metadata" playsInline
            style={{ maxWidth: 220, maxHeight: 390 }} />
        )}
        {clip.file && (
          <div className="small">
            <a className="btn" href={api.exportUrl(id, clip.file)} download={clip.file} style={{ display: "inline-block", margin: "8px 8px 4px 0" }}>
              ⬇ Download this reel
            </a>
            {clip.size ? <span className="muted"> · {formatSize(clip.size)}</span> : null}
            {clip.srt && (
              <>
                {" · "}
                <a href={api.exportUrl(id, clip.srt)} download>
                  Subtitles (.srt)
                </a>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
