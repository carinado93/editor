import { useEffect, useRef, useState } from "react";
import { api, formatSize, formatTime, type Mode, type Project, type SystemInfo } from "./api";
import { dismiss, queueFiles, subscribe, type UploadState } from "./uploads";

const MODE_CARDS: { mode: Mode; title: string; text: string; ready: boolean }[] = [
  { mode: "youtube", title: "YouTube", text: "Long raw video. Pauses, slips, retakes and filler words get marked.", ready: true },
  { mode: "reel", title: "Enhance a reel", text: "Your clip stays exactly as it is. Texts, highlights and animations get added.", ready: true },
  { mode: "idee", title: "Reel from an idea", text: "Build a reel from a prompt or photos.", ready: false },
];

const STATUS: Record<Project["status"], string> = {
  hochladen: "Uploading",
  warteschlange: "Waiting",
  arbeitet: "Processing",
  fertig: "Done",
  fehler: "Error",
};

export function ProjectList({ system }: { system: SystemInfo | null }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [uploads, setUploads] = useState<UploadState[]>([]);
  const [mode, setMode] = useState<Mode>("youtube");
  const [model, setModel] = useState("auto");
  const [language, setLanguage] = useState("auto");
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => subscribe(setUploads), []);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api.projects().then((p) => alive && (setProjects(p), setError(null))).catch((e) => alive && setError(e.message));
    load();
    const t = setInterval(load, 1500);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const addFiles = (list: FileList | null) => {
    if (!list || !list.length) return;
    const files = Array.from(list).filter((f) => f.type.startsWith("video/") || /\.(mp4|mov|m4v|mkv|avi|webm|mts)$/i.test(f.name));
    if (!files.length) {
      setError("That is not a video. Please choose a video file (e.g. MP4 or MOV).");
      return;
    }
    queueFiles(files, mode, model, language);
  };

  const remove = async (p: Project) => {
    if (!confirm(`Delete project "${p.name}"? Your original video on your PC stays untouched.`)) return;
    try {
      await api.remove(p.id);
      setProjects((list) => list.filter((x) => x.id !== p.id));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const activeUploads = uploads.filter((u) => !u.done || u.error);

  return (
    <div className="page">
      <section className="card upload-card">
        <h2>New video</h2>
        <div className="modes" role="radiogroup" aria-label="Mode">
          {MODE_CARDS.map((m) => (
            <button
              key={m.mode}
              role="radio"
              aria-checked={mode === m.mode}
              className={`mode ${mode === m.mode ? "selected" : ""}`}
              disabled={!m.ready}
              onClick={() => setMode(m.mode)}
            >
              <strong>{m.title}</strong>
              <span>{m.text}</span>
              {!m.ready && <em>coming in milestone 6</em>}
            </button>
          ))}
        </div>

        <div
          className={`drop ${drag ? "drag" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            addFiles(e.dataTransfer.files);
          }}
          onClick={() => input.current?.click()}
        >
          <input ref={input} type="file" accept="video/*" multiple hidden onChange={(e) => addFiles(e.target.files)} />
          <div className="drop-icon">⬆</div>
          <p>
            <strong>Drag a video here</strong> or click to choose
          </p>
          <p className="muted">Several videos at once work too. Your original is never changed.</p>
        </div>

        <details className="settings">
          <summary>Speech recognition settings</summary>
          <label>
            Language
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="auto">detect automatically</option>
              <option value="de">German</option>
              <option value="en">English</option>
            </select>
          </label>
          <label>
            Model
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {Object.entries(system?.models ?? { auto: "Automatic" }).map(([k, v]) => (
                <option key={k} value={k}>
                  {k === "auto" && system ? `${v}: ${system.default_model}` : v}
                </option>
              ))}
            </select>
          </label>
        </details>

        {activeUploads.map((u) => (
          <div key={u.key} className={`upload-row ${u.error ? "has-error" : ""}`}>
            <span className="name">{u.name}</span>
            {u.error ? (
              <>
                <span className="error-text">{u.error}</span>
                <button className="link" onClick={() => dismiss(u.key)}>
                  dismiss
                </button>
              </>
            ) : (
              <>
                <progress value={u.sent} max={u.size} />
                <span className="muted">
                  {formatSize(u.sent)} / {formatSize(u.size)}
                </span>
              </>
            )}
          </div>
        ))}
      </section>

      {error && <div className="banner error">{error}</div>}

      <section>
        <h2>Projects</h2>
        {!projects.length && <p className="muted">No projects yet. Upload your first video above.</p>}
        <ul className="project-list">
          {projects.map((p) => (
            <li key={p.id} className="card project">
              <a href={`#/p/${p.id}`} className="project-link">
                <div className="thumb">{p.info ? (
                    <img src={api.thumbUrl(p.id)} alt="" loading="lazy" onError={(e) => (e.currentTarget.style.visibility = "hidden")} />
                  ) : (
                    <span>🎬</span>
                  )}</div>
                <div className="project-body">
                  <div className="project-title">
                    <strong>{p.name}</strong>
                    <span className={`pill mode-${p.mode}`}>{system?.modes[p.mode] ?? p.mode}</span>
                  </div>
                  <div className="muted small">
                    {p.info ? `${formatTime(p.info.duration)} · ${p.info.width}×${p.info.height} · ` : ""}
                    {formatSize(p.size)} · {new Date(p.created * 1000).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" })}
                  </div>
                  {p.status === "fertig" ? (
                    <div className="status ok">
                      ✓ Done{p.transcript ? ` · ${p.transcript.words} words · ${p.transcript.language.toUpperCase()}` : ""}
                    </div>
                  ) : p.status === "fehler" ? (
                    <div className="status error-text">⚠ {p.error}</div>
                  ) : (
                    <div className="status">
                      <progress value={p.progress} max={1} />
                      <span className="small">
                        {STATUS[p.status]}: {p.message} · gesamt {Math.round(p.progress * 100)} %
                      </span>
                    </div>
                  )}
                </div>
              </a>
              <div className="project-actions">
                {p.status === "fehler" && (
                  <button className="link" onClick={() => api.retry(p.id).catch((e) => setError(e.message))}>
                    try again
                  </button>
                )}
                <button className="link danger" onClick={() => remove(p)} disabled={p.status === "arbeitet"}>
                  delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
