import { useEffect, useRef, useState } from "react";
import { api, formatTime, type StudioMeta, type StudioProject, type StudioSettings, type StudioTrack } from "../api";

const LOOK_NAMES: Record<string, string> = {
  none: "No grade", vivid_travel: "Vivid Travel (rich colours)", natural_plus: "Natural+ (subtle)", tropical_pop: "Tropical Pop", golden_hour: "Golden Hour",
  teal_orange: "Teal & Orange Cinema", epic_mountains: "Epic Mountains", deep_blue_ocean: "Deep Blue Ocean",
  emerald_jungle: "Emerald Jungle", moody_dusk: "Moody Dusk", bw_drama: "B&W Drama", vintage_film: "Vintage Film",
};
const CHUNK = 8 * 1024 * 1024;

/** Video Studio: Startseite (Projekte) oder ein Drone-Cutter-Projekt. */
export function StudioPage({ sid }: { sid?: string }) {
  const [meta, setMeta] = useState<StudioMeta | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.studioMeta().then(setMeta).catch((e) => setErr(e.message)); }, [sid]);
  if (sid) return meta ? <DroneCutter sid={sid} meta={meta} /> : <div className="page">{err ?? "Loading …"}</div>;
  return (
    <div className="page vs-page">
      <section className="card">
        <h2>Video Studio · Drone Cutter</h2>
        <p className="small muted">
          Upload one or more drone clips. The app finds the best moments, cuts them to the beat of the music, grades the colour and
          adds your location title – as a Reel (9:16) or a YouTube video (16:9).
        </p>
        {err && <div className="banner error small">{err}</div>}
        <div className="carousel-list small">
          <button className="btn" onClick={async () => {
            const name = prompt("Name of the video (e.g. Sri Lanka)") ?? "";
            const p = await api.studioNew(name);
            window.location.hash = `#/studio/${p.sid}`;
          }}>+ New drone video</button>
          {meta?.projects.map((p) => (
            <a key={p.sid} className="chip" href={`#/studio/${p.sid}`}>{p.name} · {p.clips} clip{p.clips === 1 ? "" : "s"}{p.has_final ? " · ✓" : ""}</a>
          ))}
        </div>
      </section>
    </div>
  );
}

function DroneCutter({ sid, meta }: { sid: string; meta: StudioMeta }) {
  const [st, setSt] = useState<StudioProject | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [uploads, setUploads] = useState<{ name: string; sent: number; size: number }[]>([]);
  const [tracks, setTracks] = useState<StudioTrack[]>([]);
  const [musicInfo, setMusicInfo] = useState<{ folder: string; note: string }>({ folder: "", note: "" });
  const [drag, setDrag] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ location: string; subtitle: string } | null>(null);
  const running = st?.job && (st.job.status === "waiting" || st.job.status === "running");

  useEffect(() => {
    api.studioGet(sid).then(setSt).catch((e) => setErr(e.message));
    api.studioMusic().then((m) => { setTracks(m.tracks); setMusicInfo({ folder: m.folder, note: m.content_id_note }); }).catch(() => {});
  }, [sid]);
  useEffect(() => {   // Fortschritt abfragen, solange gearbeitet wird
    if (!running) return;
    const t = setInterval(() => api.studioGet(sid).then(setSt).catch(() => {}), 1200);
    return () => clearInterval(t);
  }, [sid, running]);

  if (!st) return <div className="page">{err ?? "Loading …"}</div>;
  // Texte lokal halten (Server-Antworten anderer Felder überschreiben sie nicht beim Tippen)
  const loc = draft?.location ?? st.settings.location, sub = draft?.subtitle ?? st.settings.subtitle;
  const s = { ...st.settings, location: loc, subtitle: sub };
  const set = async (patch: Partial<StudioSettings> | Record<string, unknown>) => {
    setErr(null);
    try { setSt(await api.studioSettings(sid, patch as Record<string, unknown>)); } catch (e) { setErr((e as Error).message); }
  };
  const act = async (fn: () => Promise<StudioProject>) => {
    setErr(null);
    try { setSt(await fn()); } catch (e) { setErr((e as Error).message); }
  };

  const upload = async (files: FileList) => {
    for (const f of Array.from(files)) {
      const uid = `u${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
      setUploads((u) => [...u, { name: f.name, sent: 0, size: f.size }]);
      try {
        let off = 0;
        while (off < f.size) {
          const r = await api.studioChunk(sid, uid, off, f.slice(off, off + CHUNK));
          off = r.uploaded;
          setUploads((u) => u.map((x) => (x.name === f.name ? { ...x, sent: off } : x)));
        }
        setSt(await api.studioFinish(sid, uid, f.name));
      } catch (e) {
        setErr(`${f.name}: ${(e as Error).message}`);
      } finally {
        setUploads((u) => u.filter((x) => x.name !== f.name));
      }
    }
  };
  const dropOn = (target: string) => {
    if (!drag || drag === target) return;
    const ids = st.clips.map((c) => c.id).filter((i) => i !== drag);
    ids.splice(ids.indexOf(target), 0, drag);
    void act(() => api.studioOrder(sid, ids));
  };
  const prev = st.renders.preview, fin = st.renders.final;
  const isReel = s.format === "reel";
  const firstThumb = st.clips[0] ? api.studioFile(sid, "clips", st.clips[0].thumb) : "";

  return (
    <div className="page vs-page">
      <section className="card">
        <div className="letter-head">
          <a className="link" href="#/studio">← Video Studio</a>
          <h2 style={{ margin: 0 }}>{st.name}</h2>
        </div>
        {err && <div className="banner error small">⚠ {err}</div>}

        <h3>1 · Your clips</h3>
        <p className="small muted">mp4 / mov, up to 4K. One clip works too. Drag to change the order (for YouTube the order is kept roughly).</p>
        <div className="vs-clips">
          {st.clips.map((c) => (
            <div key={c.id} className={`vs-clip ${drag === c.id ? "dragging" : ""}`} draggable
              onDragStart={() => setDrag(c.id)} onDragEnd={() => setDrag(null)}
              onDragOver={(e) => e.preventDefault()} onDrop={() => dropOn(c.id)}>
              <img src={api.studioFile(sid, "clips", c.thumb)} alt={c.name} />
              <div className="small"><strong>{c.name}</strong><br />
                <span className="muted">{formatTime(c.info.duration)} · {c.info.width}×{c.info.height} · {Math.round(c.info.fps)} fps{c.analysed ? " · ✓ analysed" : ""}</span>
              </div>
              <button className="link small" disabled={!!running} onClick={() => confirm(`Remove ${c.name}?`) && act(() => api.studioDeleteClip(sid, c.id))}>remove</button>
            </div>
          ))}
          {uploads.map((u) => (
            <div key={u.name} className="vs-clip uploading small">
              <strong>{u.name}</strong>
              <div className="vs-bar"><span style={{ width: `${(100 * u.sent) / Math.max(1, u.size)}%` }} /></div>
              <span className="muted">{Math.round(u.sent / 1e6)} / {Math.round(u.size / 1e6)} MB</span>
            </div>
          ))}
          <label className="vs-clip vs-add">
            + Add clips
            <input type="file" accept="video/*,.mov,.mp4" multiple hidden onChange={(e) => { if (e.target.files) void upload(e.target.files); e.target.value = ""; }} />
          </label>
        </div>
      </section>

      <section className="card">
        <h3>2 · Format and length</h3>
        <div className="row-buttons small">
          <button className={`btn small-btn ${isReel ? "" : "ghost"}`} onClick={() => set({ format: "reel" })}>Reel / Short 9:16</button>
          <button className={`btn small-btn ${s.format === "youtube" ? "" : "ghost"}`} onClick={() => set({ format: "youtube" })}>YouTube 16:9 (HD)</button>
          <button className={`btn small-btn ${s.format === "youtube4k" ? "" : "ghost"}`} onClick={() => set({ format: "youtube4k" })}>YouTube 16:9 (4K)</button>
        </div>
        {isReel ? (
          <div className="row-buttons small">
            {meta.lengths.map((L) => (
              <button key={L} className={`chip ${s.length === L ? "on" : ""}`} onClick={() => set({ length: L })}>{L} s</button>
            ))}
          </div>
        ) : (
          <label className="small vs-inline">Length in minutes
            <input type="number" min={0.5} max={60} step={0.5} value={s.minutes} onChange={(e) => set({ minutes: Number(e.target.value) })} />
            <input type="range" min={1} max={20} step={0.5} value={s.minutes} onChange={(e) => set({ minutes: Number(e.target.value) })} />
          </label>
        )}
      </section>

      <section className="card">
        <h3>3 · Style</h3>
        <div className="vs-grid small">
          <label>Colour look
            <select value={s.grade.look} onChange={(e) => set({ grade: { look: e.target.value } })}>
              {meta.looks.map((l) => <option key={l} value={l}>{LOOK_NAMES[l] ?? l}</option>)}
            </select>
          </label>
          <label>Strength {Math.round(s.grade.strength * 100)} %
            <input type="range" min={0} max={1.5} step={0.05} value={s.grade.strength} onChange={(e) => set({ grade: { strength: Number(e.target.value) } })} />
          </label>
          <label className="check-line"><input type="checkbox" checked={s.grade.protect_skin} onChange={(e) => set({ grade: { protect_skin: e.target.checked } })} /> Protect skin tones</label>
        </div>
        <div className="vs-grid small">
          <label>Music
            <select value={s.music.mode === "file" ? `file:${s.music.file}` : s.music.mode} onChange={(e) => {
              const v = e.target.value;
              void set({ music: v.startsWith("file:") ? { mode: "file", file: v.slice(5) } : { mode: v } });
            }}>
              <option value="none">No music</option>
              {!!tracks.length && <option value="auto">Automatic from my music folder (fits mood and length)</option>}
              {tracks.map((t) => <option key={t.file} value={`file:${t.file}`}>{t.title} · {t.mood} · {Math.round(t.bpm)} BPM</option>)}
              {st.own_music && <option value="own">My upload: {st.own_music.title}</option>}
            </select>
          </label>
          {s.music.mode === "auto" && !!tracks.length && (
            <label>Mood
              <select value={s.music.mood} onChange={(e) => set({ music: { mood: e.target.value } })}>
                <option value="">any</option>
                {meta.moods.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </label>
          )}
          <label>Music volume {s.music.gain_db > 0 ? "+" : ""}{s.music.gain_db} dB
            <input type="range" min={-20} max={6} step={1} value={s.music.gain_db} onChange={(e) => set({ music: { gain_db: Number(e.target.value) } })} />
          </label>
          <label className="check-line"><input type="checkbox" checked={s.keep_audio} onChange={(e) => set({ keep_audio: e.target.checked })} /> Keep original sound (quietly under the music)</label>
          <label className="btn ghost small-btn">Upload my own song
            <input type="file" accept="audio/*" hidden onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void act(() => api.studioOwnMusic(sid, f)); }} />
          </label>
        </div>
        {s.music.mode === "none" && <p className="small muted">No music: the video is silent (or keeps the original sound if ticked), so you can add a sound later in Instagram/YouTube. Cuts follow a calm rhythm.</p>}
        {s.music.mode === "own" && <p className="small banner">⚠ {musicInfo.note}</p>}
      </section>

      <section className="card">
        <h3>4 · Intro title {isReel ? "" : "(optional title card)"}</h3>
        <div className="vs-title-edit">
          <div className="vs-grid small">
            <label>Location<input value={loc} placeholder="SRI LANKA" onChange={(e) => setDraft({ location: e.target.value, subtitle: sub })} onBlur={(e) => set({ location: e.target.value })} /></label>
            <label>Small line below (optional)<input value={sub} placeholder="Island of Serendipity" onChange={(e) => setDraft({ location: loc, subtitle: e.target.value })} onBlur={(e) => set({ subtitle: e.target.value })} /></label>
            <label>Font
              <select value={s.title.font} onChange={(e) => set({ title: { font: e.target.value } })}>
                {meta.fonts.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </label>
            <label>Size {Math.round(s.title.size * 1000) / 10} %
              <input type="range" min={0.04} max={0.14} step={0.005} value={s.title.size} onChange={(e) => set({ title: { size: Number(e.target.value) } })} />
            </label>
            <label>Letter spacing {s.title.spacing.toFixed(2)} em
              <input type="range" min={0.1} max={0.8} step={0.01} value={s.title.spacing} onChange={(e) => set({ title: { spacing: Number(e.target.value), spacing_start: Math.min(1, Number(e.target.value) + 0.17) } })} />
            </label>
            <label>Height on screen {Math.round(s.title.y * 100)} %
              <input type="range" min={0.2} max={0.8} step={0.01} value={s.title.y} onChange={(e) => set({ title: { y: Number(e.target.value) } })} />
            </label>
            <label>Colour<input type="color" value={rgbHex(s.title.color)} onChange={(e) => set({ title: { color: hexRgb(e.target.value) } })} /></label>
            <label className="check-line"><input type="checkbox" checked={s.title.animate} onChange={(e) => set({ title: { animate: e.target.checked } })} /> Animation (fade in, spacing tightens)</label>
            <label className="check-line"><input type="checkbox" checked={s.title.enabled} onChange={(e) => set({ title: { enabled: e.target.checked } })} /> Show title</label>
          </div>
          <TitlePreview thumb={firstThumb} s={s} reel={isReel} />
        </div>
      </section>

      <section className="card">
        <h3>5 · Make the video</h3>
        <div className="row-buttons">
          <button className="btn" disabled={!!running || !st.clips.length || !!uploads.length} onClick={() => act(() => api.studioGenerate(sid))}>
            {prev ? "↻ Make preview again" : "✨ Generate preview"}
          </button>
          {prev && <button className="btn ghost" disabled={!!running} onClick={() => act(() => api.studioGenerate(sid, true))}>🎲 Other version (order + music)</button>}
          {prev && <button className="btn" disabled={!!running} onClick={() => act(() => api.studioFinal(sid))}>⬆ Render final ({isReel ? "1080×1920" : s.format === "youtube4k" ? "4K" : "1920×1080"})</button>}
          {running && <button className="link" onClick={() => act(() => api.studioCancel(sid))}>cancel</button>}
        </div>
        {st.job && st.job.status !== "done" && (
          <div className="small">
            {running && <div className="vs-bar big"><span style={{ width: `${Math.round(st.job.progress * 100)}%` }} /></div>}
            <span className={st.job.status === "error" ? "banner error" : "muted"}>{st.job.error ?? `${st.job.message} ${running ? Math.round(st.job.progress * 100) + " %" : ""}`}</span>
          </div>
        )}
        {prev && (
          <div className="vs-result">
            <video key={prev.file} className={isReel ? "vs-video reel" : "vs-video"} src={api.studioFile(sid, "renders", prev.file)} controls playsInline />
            <div className="small">
              <p><strong>Preview</strong> (small, fast) · {prev.duration.toFixed(1)} s · {st.plan?.shots.length ?? 0} shots
                {st.plan?.music?.title ? ` · ♪ ${st.plan.music.title}${st.plan.music.bpm ? ` (${Math.round(st.plan.music.bpm)} BPM)` : ""}` : " · no music"}</p>
              {!!st.plan?.warnings?.length && <div className="banner small">⚠ {st.plan.warnings.join(" ")}</div>}
              {st.plan && (
                <ol className="vs-shots">
                  {st.plan.shots.map((x, k) => (
                    <li key={k}>{formatTime(x.t0)} · {x.dur.toFixed(2)} s from {st.clips.find((c) => c.id === x.clip)?.name ?? x.clip} at {x.src_in.toFixed(1)} s
                      {x.speed < 0.99 ? ` · slow motion ${Math.round(x.speed * 100)} %` : x.speed > 1.01 ? ` · ${x.speed.toFixed(1)}×` : ""}
                      {x.hero ? " · ★ hero" : ""}{k === 0 ? " · hook" : ""}</li>
                  ))}
                </ol>
              )}
              {fin && (
                <p><a className="btn" href={api.studioFile(sid, "renders", fin.file, true)} download>⬇ Download final MP4</a>{" "}
                  <span className="muted">{fin.width}×{fin.height} · {fin.fps} fps · {Math.round(fin.size / 1e6)} MB · also on your Desktop</span></p>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

/** Live-Vorschau des Intro-Titels über dem ersten Clip (gleiche Schrift, Laufweite, Höhe, Animation). */
function TitlePreview({ thumb, s, reel }: { thumb: string; s: StudioSettings; reel: boolean }) {
  const [k, setK] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(200);
  useEffect(() => { if (box.current) setW(box.current.clientWidth); }, [reel]);
  const text = (s.location || "SRI LANKA").toUpperCase();
  const size = w * s.title.size;
  return (
    <div className="vs-title-prev">
      <div ref={box} className={`vs-title-frame ${reel ? "reel" : ""}`} style={{ backgroundImage: thumb ? `url(${thumb})` : undefined }}>
        {s.title.enabled && (
          <div key={k} className={`vs-title-text ${s.title.animate ? "anim" : ""}`}
            style={{
              top: `${s.title.y * 100}%`, fontFamily: `"${s.title.font}"`, fontSize: size, color: rgbHex(s.title.color),
              ["--sp0" as string]: `${s.title.spacing_start}em`, ["--sp1" as string]: `${s.title.spacing}em`,
              letterSpacing: s.title.animate ? undefined : `${s.title.spacing}em`,
            }}>
            <div>{text}</div>
            {s.subtitle && <div className="sub" style={{ fontSize: size * 0.36 }}>{s.subtitle}</div>}
          </div>
        )}
      </div>
      <button className="link small" onClick={() => setK(k + 1)}>▶ play animation</button>
    </div>
  );
}

function rgbHex(c: number[]) {
  return `#${(c ?? [255, 255, 255]).map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")}`;
}
function hexRgb(h: string) {
  return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
}
