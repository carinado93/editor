import { useEffect, useRef, useState } from "react";
import { api, formatSize, formatTime, type Clip } from "./api";
import { Status } from "./ReelPackage";

function copy(text: string, done: (m: string) => void) {
  navigator.clipboard.writeText(text).then(
    () => done("Kopiert ✓"),
    () => done("Kopieren ging nicht – bitte Text markieren und Strg+C."),
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
      setMsg(`${d.clips.filter((c) => c.status === "vorschlag").length} Reel-Vorschläge ✓ – unten ansehen.`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const vorschlaege = clips.filter((c) => c.status === "vorschlag").length;

  return (
    <div className="card clips-card">
      <h3>Reels aus diesem Video</h3>
      <p className="small muted">
        Claude sucht die stärksten 15–20-Sekunden-Momente, mit Hook in Sekunde 0. Stücke dürfen aus verschiedenen Stellen kommen.
        Querformat-Videos werden ohne Zoom mittig ins Hochformat gesetzt (schwarze Balken, Hook-Text oben).
      </p>
      <div className="row-buttons">
        <button className="btn" disabled={!!busy} onClick={() => suggest("claude", false)}>
          {busy === "suggest" && engine === "claude" ? "Claude sucht … (ca. 30–90 s)" : "Mit Claude vorschlagen"}
        </button>
        <button className="btn ghost" disabled={!!busy} onClick={() => suggest("ollama", false)}>
          {busy === "suggest" && engine === "ollama" ? "Lokale KI sucht … (2–5 Min)" : "Kostenlos mit Ollama"}
        </button>
      </div>
      {vorschlaege > 0 && (
        <div className="feedback-box">
          <label className="small">
            Wünsche zur Verfeinerung (z. B. „provokantere Hooks“, „mehr über Grenzen“, „kürzer, 15 s“)
            <textarea rows={2} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
          </label>
          <button className="btn ghost" disabled={!!busy || !feedback.trim()} onClick={() => suggest(engine, true)}>
            Neu vorschlagen mit diesen Wünschen
          </button>
        </div>
      )}
      <Status busy={busy} err={err} msg={msg} />
      {err?.includes("Einstellungen") && <a className="small" href="#/einstellungen">→ zu den Einstellungen</a>}
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
          {playing ? "❚❚ Stopp" : "▶ Vorschau"}
        </button>
      </div>
      <div className="clip-body">
        <div className="clip-title">
          <strong>{clip.title}</strong>
          <span className="pill">{formatTime(clip.duration)}</span>
          {clip.status === "fertig" && <span className="pill ok-pill">fertig</span>}
        </div>
        {clip.why && <div className="small muted">{clip.why}</div>}
        {clip.warnings?.map((w) => (
          <div key={w} className="small error-text">⚠ {w}</div>
        ))}
        <label className="small">
          Hook-Text oben (*Wort* = lila)
          <input
            value={hook}
            onChange={(e) => setHook(e.target.value)}
            onBlur={() => hook !== clip.hook_text && run(() => api.editClip(id, clip.id, { hook_text: hook }))}
          />
        </label>
        <details className="small">
          <summary>Was gesagt wird</summary>
          <p>{clip.text}</p>
        </details>
        <details className="small">
          <summary>Caption, 5 Hashtags, Shorts-Titel</summary>
          <p className="pre">{clip.caption}</p>
          <p>{clip.hashtags.join(" ")}</p>
          <p>
            <em>{clip.shorts_title}</em>
          </p>
          <button className="link" onClick={() => copy(clip.caption + "\n\n" + clip.hashtags.join(" "), onMsg)}>
            Caption + Hashtags kopieren
          </button>{" "}
          <button className="link" onClick={() => copy(clip.shorts_title, onMsg)}>
            Shorts-Titel kopieren
          </button>
        </details>
        <div className="row-buttons">
          <button className="btn" disabled={rendering} onClick={() => run(() => api.renderClip(id, clip.id))}>
            {clip.status === "fertig" ? "Nochmal rendern" : "Passt – Reel rendern"}
          </button>
          <button className="link danger" disabled={rendering} onClick={() => confirm("Diesen Vorschlag verwerfen?") && run(() => api.deleteClip(id, clip.id))}>
            verwerfen
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
              ⬇ Reel herunterladen
            </a>
            {clip.size ? <span className="muted"> · {formatSize(clip.size)}</span> : null}
            {clip.srt && (
              <>
                {" · "}
                <a href={api.exportUrl(id, clip.srt)} download>
                  Untertitel (.srt)
                </a>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
