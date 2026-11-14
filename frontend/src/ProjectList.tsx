import { Fragment, useEffect, useRef, useState } from "react";
import { api, formatSize, formatTime, type Mode, type Project, type SystemInfo } from "./api";
import { dismiss, queueFiles, subscribe, type UploadState } from "./uploads";

const MODE_CARDS: { mode: Mode; title: string; text: string; ready: boolean }[] = [
  { mode: "youtube", title: "YouTube", text: "Long raw video. Pauses, slips, retakes and filler words get marked.", ready: true },
  { mode: "reel", title: "Enhance a reel", text: "Your clip stays exactly as it is. Texts, highlights and animations get added.", ready: true },
  { mode: "kombi", title: "Join several videos", text: "2 or more clips → one video. You cut it yourself, then add effects.", ready: true },
  { mode: "idee", title: "Reel from an idea", text: "No filming: your photos (or your lavender background) + your idea → a reel.", ready: true },
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
  const [mode, setMode] = useState<Mode>(() => {
    try {  // aus dem Plan: "Reel from an idea" gleich offen (oder umschalten auf "Enhance a reel", wenn gefilmt)
      const m = localStorage.getItem("home-mode");
      if (m) { localStorage.removeItem("home-mode"); return m as Mode; }
    } catch { /* egal */ }
    return "youtube";
  });
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

        {mode === "kombi" ? <CombineForm onError={setError} language={language} model={model} /> : mode === "idee" ? <IdeaReelForm onError={setError} /> : (
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
        )}

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

/** Reel aus einer Idee: Fotos (optional) + Idee → ruhiges 9:16-Video → weiter wie bei "Enhance a reel". */
function IdeaReelForm({ onError }: { onError: (m: string | null) => void }) {
  const [name, setName] = useState("");
  const [idea, setIdea] = useState(() => {
    try {  // aus dem Plan gestartet
      const p = JSON.parse(localStorage.getItem("plan-start") || "null");
      if (p) { localStorage.removeItem("plan-start"); return [p.title, p.idea].filter(Boolean).join("\n"); }
    } catch { /* egal */ }
    return "";
  });
  const [photos, setPhotos] = useState<File[]>([]);
  const [seconds, setSeconds] = useState(3);
  const [language, setLanguage] = useState("en");
  const [busy, setBusy] = useState<string | null>(null);
  const urls = photos.map((f) => URL.createObjectURL(f));
  const [over, setOver] = useState(false);
  const dropPhotos = (list: FileList | null) => {
    const fs = Array.from(list ?? []).filter((f) => f.type.startsWith("image/"));
    if (fs.length) setPhotos((cur) => [...cur, ...fs].slice(0, 20));
    else if (list?.length) onError("That is not a photo. Please drop images (JPG or PNG).");
  };
  useEffect(() => () => urls.forEach((u) => URL.revokeObjectURL(u)));

  const go = async () => {
    onError(null);
    try {
      setBusy("Preparing …");
      const { draft } = await api.ideaReelNew();
      for (let k = 0; k < photos.length; k++) {
        setBusy(`Uploading photo ${k + 1} of ${photos.length} …`);
        await api.ideaReelPhoto(draft, k, photos[k]);
      }
      setBusy("Making the video (a few seconds per photo) …");
      const p = await api.ideaReelBuild(draft, { name, idea, seconds, language });
      window.location.hash = `#/p/${p.id}`;
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={`idea-reel ${over ? "drag" : ""}`}
      onDragOver={(e) => { if (e.dataTransfer.types.includes("Files")) { e.preventDefault(); setOver(true); } }}
      onDragLeave={(e) => { if (e.currentTarget === e.target) setOver(false); }}
      onDrop={(e) => { if (e.dataTransfer.files.length) { e.preventDefault(); setOver(false); dropPhotos(e.dataTransfer.files); } }}>
      <label className="small">Your idea (Claude writes the texts on the reel from it)
        <textarea rows={4} value={idea} onChange={(e) => setIdea(e.target.value)}
          placeholder={'e.g. "3 signs your rest is not real rest – calm, soft, end with a question"'} />
      </label>
      <div className="idea-reel-row small">
        <label>Name<input value={name} placeholder="Reel from an idea" onChange={(e) => setName(e.target.value)} /></label>
        <label>Seconds per photo
          <input type="number" min={1.5} max={8} step={0.5} value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} />
        </label>
        <label>Language
          <select value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="en">English</option>
            <option value="de">German</option>
          </select>
        </label>
      </div>
      <div className="idea-photos">
        {urls.map((u, k) => (
          <div key={u} className="idea-photo">
            <img src={u} alt={`Photo ${k + 1}`} />
            <span className="small">{k + 1}</span>
            <button className="link danger small" onClick={() => setPhotos(photos.filter((_, j) => j !== k))}>remove</button>
          </div>
        ))}
        <label className="btn ghost idea-add">
          + Add photos (optional) – or drag them here
          <input type="file" accept="image/*" multiple hidden onChange={(e) => {
            dropPhotos(e.target.files);
            e.target.value = "";
          }} />
        </label>
      </div>
      <p className="small muted">
        {photos.length
          ? `${photos.length} photo${photos.length > 1 ? "s" : ""} → about ${Math.round(photos.length * seconds)} s, each with a slow calm zoom. The order is the order you added them.`
          : "Without photos the reel uses your soft lavender background (12 s) – the texts are the star."}
        {" "}Afterwards everything works like “Enhance a reel”: Claude writes the texts, you add effects, render, done.
      </p>
      <button className="btn" disabled={!!busy || !idea.trim()} onClick={go}>{busy ?? "✨ Make the reel"}</button>
    </div>
  );
}

const TRANS_LABEL: Record<string, string> = {
  cut: "Cut", fade: "Soft fade", smoke: "Appear / disappear in smoke", cover: "Cover transition (glass / hand in front of the lens)",
  flash: "Flash", zoom: "Zoom", whip: "Whip",
};
const TRANS_HINT: Record<string, string> = {
  cut: "",
  fade: "the two videos blend softly",
  smoke: "film on a tripod: one video of the empty room, one with you in the same spot – you appear/disappear in a smoke puff",
  cover: "end video 1 by covering the lens (glass, hand, jacket), start video 2 covered too – the app cuts exactly in the covered moment",
  flash: "a short white flash",
  zoom: "zooms into the next video",
  whip: "fast swipe with motion blur",
};

/** Mehrere Videos verbinden: Reihenfolge festlegen, hochladen, verbinden → selbst schneiden + Effekte. */
function CombineForm({ onError, language, model }: { onError: (m: string | null) => void; language: string; model: string }) {
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState("");
  const [manual, setManual] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [trans, setTrans] = useState<string[]>([]);
  const [describe, setDescribe] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const CHUNK = 8 * 1024 * 1024;
  const tr = (k: number) => trans[k] ?? "cut";
  const [over, setOver] = useState(false);
  const [dragK, setDragK] = useState<number | null>(null);
  const isVideo = (f: File) => f.type.startsWith("video/") || /\.(mp4|mov|m4v|mkv|avi|webm|mts)$/i.test(f.name);
  const dropFiles = (list: FileList | null) => {
    const fs = Array.from(list ?? []).filter(isVideo);
    if (fs.length) setFiles((cur) => [...cur, ...fs]);
    else if (list?.length) onError("That is not a video. Please drop video files (e.g. MP4 or MOV).");
  };
  const reorder = (from: number, to: number) => {
    if (from === to) return;
    const next = [...files];
    const [x] = next.splice(from, 1);
    next.splice(to, 0, x);
    setFiles(next);
  };
  const planWithClaude = async () => {
    onError(null);
    setBusy("Claude is choosing the transitions …");
    try {
      const r = await api.combinePlan(describe, files.map((f) => f.name));
      setTrans(r.transitions);
      setNote(r.note);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  const move = (k: number, dir: -1 | 1) => {
    const j = k + dir;
    if (j < 0 || j >= files.length) return;
    const next = [...files];
    [next[k], next[j]] = [next[j], next[k]];
    setFiles(next);
  };
  const go = async () => {
    onError(null);
    try {
      setBusy("Preparing …");
      const { draft } = await api.combineNew();
      const total = files.reduce((a, f) => a + f.size, 0);
      let done = 0;
      for (let k = 0; k < files.length; k++) {
        const f = files[k];
        let offset = 0;
        while (offset < f.size) {
          const r = await api.combineChunk(draft, k, f.name, offset, f.slice(offset, offset + CHUNK));
          done += r.uploaded - offset;
          offset = r.uploaded;
          setBusy(`Uploading video ${k + 1} of ${files.length} … ${Math.round((done / total) * 100)} %`);
        }
      }
      setBusy("Joining the videos … (about as long as the videos)");
      const p = await api.combineBuild(draft, { name, manual, language, model, transitions: files.slice(1).map((_, k) => tr(k)) });
      window.location.hash = `#/p/${p.id}`;
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  return (
    <div className={`idea-reel ${over ? "drag" : ""}`}
      onDragOver={(e) => { if (dragK == null && e.dataTransfer.types.includes("Files")) { e.preventDefault(); setOver(true); } }}
      onDragLeave={(e) => { if (e.currentTarget === e.target) setOver(false); }}
      onDrop={(e) => { if (dragK == null && e.dataTransfer.files.length) { e.preventDefault(); setOver(false); dropFiles(e.dataTransfer.files); } }}>
      {!files.length && (
        <div className="drop-hint" onClick={() => document.getElementById("combine-pick")?.click()}>
          <div className="drop-icon">⬆</div>
          <p><strong>Drag your videos here</strong> or click to choose – several at once. Then drag them into the right order.</p>
        </div>
      )}
      <div className="combine-list">
        {files.map((f, k) => (
          <Fragment key={`${f.name}-${k}`}>
          {k > 0 && (
            <div className="combine-trans small">
              <span>↓ transition</span>
              <select value={tr(k - 1)} onChange={(e) => setTrans(files.slice(1).map((_, j) => (j === k - 1 ? e.target.value : tr(j))))}>
                {Object.entries(TRANS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <span className="muted">{TRANS_HINT[tr(k - 1)]}</span>
            </div>
          )}
          <div className={`combine-row small ${dragK === k ? "dragging" : ""}`} draggable
            onDragStart={(e) => { setDragK(k); e.dataTransfer.effectAllowed = "move"; }}
            onDragOver={(e) => { if (dragK != null) { e.preventDefault(); } }}
            onDrop={(e) => { if (dragK != null) { e.preventDefault(); e.stopPropagation(); reorder(dragK, k); setDragK(null); } }}
            onDragEnd={() => setDragK(null)}
            title="Drag to change the order">
            <span className="grip">⋮⋮</span>
            <strong>{k + 1}.</strong>
            <span className="grow">{f.name}</span>
            <span className="muted">{formatSize(f.size)}</span>
            <button className="link" disabled={k === 0} onClick={() => move(k, -1)} title="earlier">↑</button>
            <button className="link" disabled={k === files.length - 1} onClick={() => move(k, 1)} title="later">↓</button>
            <button className="link danger" onClick={() => setFiles(files.filter((_, j) => j !== k))}>remove</button>
          </div>
          </Fragment>
        ))}
        <label className="btn ghost idea-add">
          + Add videos
          <input id="combine-pick" type="file" accept="video/*" multiple hidden onChange={(e) => {
            dropFiles(e.target.files);
            e.target.value = "";
          }} />
        </label>
      </div>
      {files.length > 1 && (
        <div className="combine-describe small">
          <label>Or describe what should happen – Claude picks the transitions
            <textarea rows={2} value={describe} onChange={(e) => setDescribe(e.target.value)}
              placeholder={'e.g. "in video 2 I appear in the room in smoke" or "I hold a glass in front of the camera, then I wear another outfit"'} />
          </label>
          <button className="btn ghost small-btn" disabled={!!busy || !describe.trim()} onClick={planWithClaude}>✨ Let Claude choose</button>
          {note && <div className="banner small">{note}</div>}
        </div>
      )}
      <div className="idea-reel-row small">
        <label>Name<input value={name} placeholder="Combined video" onChange={(e) => setName(e.target.value)} /></label>
      </div>
      <label className="small check-line">
        <input type="checkbox" checked={manual} onChange={(e) => setManual(e.target.checked)} />{" "}
        I cut it myself (nothing is cut automatically – suggestions are only marked, pauses stay)
      </label>
      <p className="small muted">
        The videos are joined in this order (size and frame rate of the first video; a portrait first video → portrait result).
        Your originals stay untouched. Then: cut in the transcript or by time, add effects, render.
      </p>
      <button className="btn" disabled={!!busy || files.length < 2} onClick={go}>
        {busy ?? (files.length < 2 ? "Add at least 2 videos" : `✨ Join ${files.length} videos`)}
      </button>
    </div>
  );
}
