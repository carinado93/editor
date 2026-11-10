import { useEffect, useRef, useState } from "react";
import { api, formatSize, formatTime, type Clip } from "./api";
import { Status } from "./ReelPackage";

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
  const [playing, setPlaying] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  useEffect(() => setHook(clip.hook_text), [clip.hook_text]);

  // Vorschau: die Stücke nacheinander aus dem Vorschau-Video abspielen
  const preview = () => {
    const v = video.current;
    if (!v) return;
    let k = 0;
    const segs = clip.segments;
    setPlaying(true);
    v.currentTime = segs[0][0];
    void v.play();
    const tick = () => {
      if (!v || v.paused) return;
      if (v.currentTime >= segs[k][1]) {
        k += 1;
        if (k >= segs.length) {
          v.pause();
          setPlaying(false);
          return;
        }
        v.currentTime = segs[k][0];
      }
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
        <video ref={video} src={api.proxyUrl(id)} preload="metadata" playsInline onPause={() => setPlaying(false)} />
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
        <details className="small">
          <summary>What is said</summary>
          <p>{clip.text}</p>
        </details>
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
            <progress value={clip.progress ?? 0} max={1} /> {clip.message}
          </div>
        )}
        {clip.status === "fehler" && <div className="small error-text">⚠ {clip.error}</div>}
        {clip.file && (
          <div className="small">
            <a href={api.exportUrl(id, clip.file)} download>
              ⬇ Download reel
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
