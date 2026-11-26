import { useEffect, useRef, useState } from "react";
import { MomentPicker } from "./MomentPicker";
import { ShotPanel } from "./ShotPanel";
import { CaptionExample, ExamplePicker, FontExample, LookExample, TextAnimExample, TransitionExample } from "../Pickers";
import { api, formatTime, type StudioMeta, type StudioPlan, type StudioProject, type StudioSettings, type StudioTrack } from "../api";

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
            <a title="Open – this drone video project" key={p.sid} className="chip" href={`#/studio/${p.sid}`}>{p.name} · {p.clips} clip{p.clips === 1 ? "" : "s"}{p.has_final ? " · ✓" : ""}</a>
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
  const [picking, setPicking] = useState<string | null>(null);
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
  const isReel = s.format === "reel";
  const hasReel = s.format === "reel" || s.format === "both";
  const hasYt = s.format !== "reel";
  const fmts = Object.keys(st.plans).sort((a, b) => (a === "reel" ? -1 : b === "reel" ? 1 : 0));
  const anyPreview = fmts.some((f) => st.renders[f]?.preview);
  const edited = fmts.some((f) => st.plans[f]?.edited);
  const firstThumb = st.clips[0] ? api.studioFile(sid, "clips", st.clips[0].thumb) : "";

  return (
    <div className="page vs-page">
      <section className="card">
        <div className="letter-head">
          <a title="Back – to all Video Studio projects" className="link" href="#/studio">← Video Studio</a>
          <h2 style={{ margin: 0 }}>{st.name}</h2>
        </div>
        {err && <div className="banner error small">⚠ {err}</div>}

        <div className="carousel-head">
          <h3>1 · Your clips</h3>
          {!!st.clips.length && st.clips.some((c) => !c.analysed) && (
            <button title="Analyse – the app looks at every clip to suggest the best moments" className="btn ghost small-btn" disabled={!!running} onClick={() => act(() => api.studioAnalyse(sid))}>🔎 Analyse clips (for suggestions)</button>
          )}
        </div>
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
              <span className="row-buttons">
                <button title="Choose seconds – mark parts that must (or must never) be in the video" className="link small" onClick={() => setPicking(picking === c.id ? null : c.id)}>
                  🎯 choose seconds{(c.must?.length || c.never?.length) ? ` (${(c.must?.length ?? 0)}✓ ${(c.never?.length ?? 0)}✗)` : ""}</button>
                <button className="link small" disabled={!!running} onClick={() => confirm(`Remove ${c.name}?`) && act(() => api.studioDeleteClip(sid, c.id))}>remove</button>
              </span>
            </div>
          ))}
          {uploads.map((u) => (
            <div key={u.name} className="vs-clip uploading small">
              <strong>{u.name}</strong>
              <div className="vs-bar"><span style={{ width: `${(100 * u.sent) / Math.max(1, u.size)}%` }} /></div>
              <span className="muted">{Math.round(u.sent / 1e6)} / {Math.round(u.size / 1e6)} MB</span>
            </div>
          ))}
          <label className="vs-clip vs-add" key="add">
            + Add clips
            <input type="file" accept="video/*,.mov,.mp4" multiple hidden onChange={(e) => { if (e.target.files) void upload(e.target.files); e.target.value = ""; }} />
          </label>
        </div>
        {picking && st.clips.find((c) => c.id === picking) && (
          <MomentPicker sid={sid} clip={st.clips.find((c) => c.id === picking)!} busy={!!running} onState={setSt} onErr={setErr} />
        )}
      </section>

      <section className="card">
        <h3>2 · Format and length</h3>
        <div className="row-buttons small">
          <button title="Vertical – 9:16 for Instagram Reels and YouTube Shorts" className={`btn small-btn ${isReel ? "" : "ghost"}`} onClick={() => set({ format: "reel" })}>Vertical · Reel / Short 9:16</button>
          <button title="Landscape HD – 16:9 for YouTube, 1920×1080" className={`btn small-btn ${s.format === "youtube" ? "" : "ghost"}`} onClick={() => set({ format: "youtube" })}>Landscape · YouTube 16:9 (HD)</button>
          <button title="Landscape 4K – 16:9 for YouTube, 3840×2160 (slower)" className={`btn small-btn ${s.format === "youtube4k" ? "" : "ghost"}`} onClick={() => set({ format: "youtube4k" })}>Landscape · YouTube 16:9 (4K)</button>
          <button title="Both – one vertical and one landscape video from the same clips" className={`btn small-btn ${s.format === "both" ? "" : "ghost"}`} onClick={() => set({ format: "both" })}>Both: vertical + landscape</button>
        </div>
        {hasReel && (
          <div className="row-buttons small">
            <span className="muted">Vertical length:</span>
            {meta.lengths.map((L) => (
              <button title="Length – how long the vertical video is" key={L} className={`chip ${s.length === L ? "on" : ""}`} onClick={() => set({ length: L })}>{L} s</button>
            ))}
          </div>
        )}
        {hasYt && (
          <label className="small vs-inline">Landscape length in minutes
            <input type="number" min={0.5} max={60} step={0.5} value={s.minutes} onChange={(e) => set({ minutes: Number(e.target.value) })} />
            <input type="range" min={0.5} max={20} step={0.5} value={s.minutes} onChange={(e) => set({ minutes: Number(e.target.value) })} />
            {s.format === "both" && <span className="check-line"><input type="checkbox" checked={s.yt4k} onChange={(e) => set({ yt4k: e.target.checked })} /> landscape in 4K</span>}
          </label>
        )}
      </section>

      <section className="card">
        <h3>3 · Style</h3>
        <div className="vs-grid small">
          <label>Colour look
            <ExamplePicker value={s.grade.look} onChange={(v) => set({ grade: { look: v } })}
              options={meta.looks.map((l) => ({ value: l, label: LOOK_NAMES[l] ?? l }))}
              example={(o, small) => <LookExample look={o.value} img={firstThumb} small={small} />} />
          </label>
          <label>Strength {Math.round(s.grade.strength * 100)} %
            <input type="range" min={0} max={1.5} step={0.05} value={s.grade.strength} onChange={(e) => set({ grade: { strength: Number(e.target.value) } })} />
          </label>
          <label className="check-line"><input type="checkbox" checked={s.grade.protect_skin} onChange={(e) => set({ grade: { protect_skin: e.target.checked } })} /> Protect skin tones</label>
          <label className="check-line"><input type="checkbox" checked={s.grade.match} onChange={(e) => set({ grade: { match: e.target.checked } })} /> Match brightness of all shots (auto-grade)</label>
          {(["sharpen", "clarity", "vignette", "grain"] as const).map((k) => (
            <label key={k}>{{ sharpen: "Sharpen", clarity: "Clarity", vignette: "Vignette", grain: "Grain" }[k]} {Number(s.grade.fx?.[k] ?? 0)}
              <input type="range" min={0} max={100} step={1} value={Number(s.grade.fx?.[k] ?? 0)} onChange={(e) => set({ grade: { fx: { [k]: Number(e.target.value) } } })} />
            </label>
          ))}
          <button className="link" onClick={() => set({ grade: { fx: { sharpen: 30, clarity: 15, denoise: true } } })}>“Drone crisp” preset</button>
          <label>Stabilize all shots
            <select value={s.grade.stabilize} onChange={(e) => set({ grade: { stabilize: e.target.value } })}>
              <option value="">off</option><option value="minimal">minimal</option><option value="recommended">recommended</option><option value="most">most stable</option>
            </select>
          </label>
          <label className="check-line"><input type="checkbox" checked={!!s.grade.fx?.denoise} onChange={(e) => set({ grade: { fx: { denoise: e.target.checked } } })} /> Denoise (cleaner sky and water)</label>
          <label className="check-line"><input type="checkbox" checked={s.normalize} onChange={(e) => set({ normalize: e.target.checked })} /> Normalize loudness (−14 LUFS)</label>
          <label className="check-line"><input type="checkbox" checked={s.captions.enabled} onChange={(e) => set({ captions: { enabled: e.target.checked }, ...(e.target.checked ? { keep_audio: true } : {}) })} /> Auto captions from the spoken words (needs original sound)</label>
          {s.captions.enabled && <>
            <label>Caption style
              <ExamplePicker value={s.captions.style} onChange={(v) => set({ captions: { style: v } })} tile="lg"
                options={[
                  { value: "clean", label: "Clean (white)", desc: "White words with a soft shadow" },
                  { value: "bold", label: "Bold (big caps)", desc: "Big, thick capitals" },
                  { value: "karaoke", label: "Word by word (lilac)", desc: "The word you are saying lights up in lilac" },
                  { value: "boxed", label: "Boxed", desc: "White words on a dark box – easy to read on busy pictures" },
                ]}
                example={(o, small) => <CaptionExample style={o.value} small={small} />} />
            </label>
            <label>Language
              <select value={s.captions.language} onChange={(e) => set({ captions: { language: e.target.value } })}>
                <option value="auto">automatic</option><option value="de">German</option><option value="en">English</option>
              </select>
            </label>
            <label className="check-line"><input type="checkbox" checked={s.captions.drop_fillers} onChange={(e) => set({ captions: { drop_fillers: e.target.checked } })} /> Leave out filler words (äh, ähm, um)</label>
          </>}
        </div>
        <div className="vs-grid small">
          <label>Transitions
            <ExamplePicker value={s.transition} onChange={(v) => set({ transition: v })} tile="sm"
              options={[
                { value: "auto", label: "Automatic", desc: "The app picks a transition that fits the shots and the beat" },
                ...Object.entries(meta.transitions).map(([k, l]) => ({ value: k, label: k === "cut" ? "Hard cuts only" : l, desc: k === "cut" ? "No transition, straight cut" : `${l} on every cut` })),
              ]}
              example={(o, small) => o.value === "auto" ? <span className={small ? "" : "ex-font small"}>✨ auto</span> : <TransitionExample kind={o.value} small={small} />} />
          </label>
          <label>Transition length {s.transition_dur ? `${s.transition_dur.toFixed(1)} s` : "(standard)"}
            <input type="range" min={0} max={2} step={0.1} value={s.transition_dur} onChange={(e) => set({ transition_dur: Number(e.target.value) })} />
          </label>
          <label className="check-line"><input type="checkbox" checked={s.ramps} onChange={(e) => set({ ramps: e.target.checked })} /> Speed ramps (slow motion on the best moments)</label>
          <label className="check-line"><input type="checkbox" checked={s.speedup} onChange={(e) => set({ speedup: e.target.checked })} /> Faster flights (2× on long, steady flights)</label>
          <label className="check-line"><input type="checkbox" checked={s.smooth_slowmo} onChange={(e) => set({ smooth_slowmo: e.target.checked })} /> Smooth slow motion in the final video (in-between frames, slower to render)</label>
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
        <h3>4 · Intro title and outro</h3>
        <div className="vs-title-edit">
          <div className="vs-grid small">
            <label>Location<input value={loc} placeholder="SRI LANKA" onChange={(e) => setDraft({ location: e.target.value, subtitle: sub })} onBlur={(e) => set({ location: e.target.value })} /></label>
            <label>Small line below (optional)<input value={sub} placeholder="Island of Serendipity" onChange={(e) => setDraft({ location: loc, subtitle: e.target.value })} onBlur={(e) => set({ subtitle: e.target.value })} /></label>
            <label>Font
              <ExamplePicker value={s.title.font} onChange={(v) => set({ title: { font: v } })} tile="lg"
                options={meta.fonts.map((f) => ({ value: f, label: f }))}
                example={(o, small) => <FontExample font={o.value} text={(loc || "SRI LANKA").toUpperCase()} small={small} />} />
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
            <label>Animation in
              <ExamplePicker value={s.title.animate ? s.title.anim_in : "off"} tile="lg"
                onChange={(v) => set({ title: v === "off" ? { animate: false } : { animate: true, anim_in: v } })}
                options={[...Object.entries(meta.anims_in).map(([k, l]) => ({ value: k, label: l })), { value: "off", label: "No animation" }]}
                example={(o, small) => <TextAnimExample kind={o.value === "off" ? "none" : o.value} dir="in" font={s.title.font}
                  text={(loc || "SRI LANKA").toUpperCase()} small={small} />} />
            </label>
            <label>Animation out
              <ExamplePicker value={s.title.anim_out} onChange={(v) => set({ title: { anim_out: v } })} tile="lg"
                options={Object.entries(meta.anims_out).map(([k, l]) => ({ value: k, label: l }))}
                example={(o, small) => <TextAnimExample kind={o.value} dir="out" font={s.title.font}
                  text={(loc || "SRI LANKA").toUpperCase()} small={small} />} />
            </label>
            <label className="check-line"><input type="checkbox" checked={s.title.enabled} onChange={(e) => set({ title: { enabled: e.target.checked } })} /> Show title</label>
            {hasYt && <label className="check-line"><input type="checkbox" checked={s.title.youtube_card} onChange={(e) => set({ title: { youtube_card: e.target.checked } })} /> Title also on the landscape video</label>}
            <label className="check-line"><input type="checkbox" checked={s.outro.enabled} onChange={(e) => set({ outro: { enabled: e.target.checked } })} /> Outro at the end</label>
            {s.outro.enabled && <label>Outro text (e.g. your account)<input defaultValue={s.outro.text} placeholder="@youraccount" onBlur={(e) => set({ outro: { text: e.target.value } })} /></label>}
          </div>
          <TitlePreview thumb={firstThumb} s={s} reel={hasReel} />
        </div>
      </section>

      <section className="card">
        <h3>5 · Make the video</h3>
        <div className="row-buttons">
          <button title="Generate – make a new preview from your settings" className="btn" disabled={!!running || !st.clips.length || !!uploads.length} onClick={() => act(() => api.studioGenerate(sid))}>
            {anyPreview ? "↻ Make new preview" : "✨ Generate preview"}
          </button>
          {anyPreview && <button title="Other version – new shot order and other music" className="btn ghost" disabled={!!running} onClick={() => act(() => api.studioGenerate(sid, true))}>🎲 Other version (order + music)</button>}
          {anyPreview && <button title="Update preview – keep your shots, show your latest changes" className={`btn ${edited ? "" : "ghost"}`} disabled={!!running} onClick={() => act(() => api.studioPreview(sid))}>↻ Update preview (keep shots)</button>}
          {anyPreview && <button title="Render final – make the full-quality video file" className="btn" disabled={!!running} onClick={() => act(() => api.studioFinal(sid))}>⬆ Render final video{fmts.length > 1 ? "s" : ""}</button>}
          {running && <button className="link" onClick={() => act(() => api.studioCancel(sid))}>cancel</button>}
        </div>
        <p className="small muted">Changed colour, title, outro, volume, transitions or a shot? Press “Update preview” – your shots stay. Changed the format or length? Press “Make new preview”.</p>
        {st.job && st.job.status !== "done" && (
          <div className="small">
            {running && <div className="vs-bar big"><span style={{ width: `${Math.round(st.job.progress * 100)}%` }} /></div>}
            <span className={st.job.status === "error" ? "banner error" : "muted"}>{st.job.error ?? `${st.job.message} ${running ? Math.round(st.job.progress * 100) + " %" : ""}`}</span>
          </div>
        )}
        {fmts.map((f) => (
          <FormatResult key={f} sid={sid} fmt={f} st={st} meta={meta} busy={!!running} onState={setSt} onErr={setErr} />
        ))}
      </section>
    </div>
  );
}

/** Ergebnis eines Formats: Vorschau-Video, Zeitleiste (Aufnahmen tauschen/verschieben/Tempo/Übergang), Download. */
function FormatResult({ sid, fmt, st, meta, busy, onState, onErr }: {
  sid: string; fmt: string; st: StudioProject; meta: StudioMeta; busy: boolean;
  onState: (s: StudioProject) => void; onErr: (m: string) => void;
}) {
  const plan: StudioPlan = st.plans[fmt];
  const r = st.renders[fmt] ?? {};
  const [sel, setSel] = useState<number | null>(null);
  const reel = fmt === "reel";
  const edit = async (k: number, action: string, value?: string | number) => {
    try { onState(await api.studioShot(sid, fmt, k, action, value)); } catch (e) { onErr((e as Error).message); }
  };
  const label = reel ? "Vertical reel 9:16" : fmt === "youtube4k" ? "Landscape 16:9 (4K)" : "Landscape 16:9 (HD)";
  return (
    <div className="vs-format">
      <h4>{label} · {plan.duration >= 60 ? `${(plan.duration / 60).toFixed(1)} min` : `${plan.duration} s`} · {plan.shots.length} shots
        {plan.music?.title ? ` · ♪ ${plan.music.title}` : ""}{plan.edited ? " · changed (press “Update preview”)" : ""}</h4>
      {!!plan.warnings?.length && <div className="banner small">⚠ {plan.warnings.join(" ")}</div>}
      <div className="vs-result">
        {r.preview && <video key={r.preview.file} className={reel ? "vs-video reel" : "vs-video"} src={api.studioFile(sid, "renders", r.preview.file)} controls playsInline />}
        {r.final && (
          <p className="small"><a title="Download – save the finished MP4" className="btn" href={api.studioFile(sid, "renders", r.final.file, true)} download>⬇ Download final MP4</a><br />
            <span className="muted">{r.final.width}×{r.final.height} · {r.final.fps} fps · {Math.round(r.final.size / 1e6)} MB · also on your Desktop</span></p>
        )}
      </div>
      <div className="vs-timeline">
        {plan.shots.map((x, k) => (
          <div key={k} className={`vs-shot small ${sel === k ? "sel" : ""}`}>
            <img src={api.studioShotThumb(sid, fmt, k, `${x.clip}${x.src_in}`)} alt={`Shot ${k + 1}`} loading="lazy"
              title="click to edit this shot" onClick={() => setSel(sel === k ? null : k)} />
            <div><strong>{k + 1}</strong> · {formatTime(x.t0)} · {x.dur.toFixed(1)} s{k === 0 ? " · hook" : ""}{x.hero ? " · ★" : ""}</div>
            <select value={x.ramp ? `ramp:${x.ramp}` : String(x.speed)} disabled={busy}
              onChange={(e) => (e.target.value.startsWith("ramp:") ? edit(k, "ramp", e.target.value.slice(5)) : edit(k, "speed", Number(e.target.value)))}>
              <option value="1">Normal speed</option>
              <option value="0.5">Slow motion 50 %</option>
              <option value="0.75">Slow 75 %</option>
              <option value="1.5">Fast 1.5×</option>
              <option value="2">Fast 2×</option>
              <option value="3">Fast 3×</option>
              {Object.entries(meta.ramps).map(([id, l]) => <option key={id} value={`ramp:${id}`}>Ramp: {l}</option>)}
              {!["0.5", "0.75", "1", "1.5", "2", "3"].includes(String(x.speed)) && !x.ramp && <option value={String(x.speed)}>{x.speed}×</option>}
            </select>
            <div className="vs-shot-btns">
              <button disabled={busy || k === 0} title="move earlier" onClick={() => edit(k, "left")}>←</button>
              <button disabled={busy} title="use another shot here" onClick={() => edit(k, "swap")}>⇄ swap</button>
              <button disabled={busy || k === plan.shots.length - 1} title="move later" onClick={() => edit(k, "right")}>→</button>
            </div>
            {k < plan.shots.length - 1 && (
              <select className="vs-trans" value={plan.transitions?.[k]?.id ?? "cut"} disabled={busy} title="transition after this shot"
                onChange={(e) => edit(k, "transition", e.target.value)}>
                {Object.entries(meta.transitions).map(([id, l]) => <option key={id} value={id}>→ {l}</option>)}
              </select>
            )}
          </div>
        ))}
      </div>
      {sel !== null && sel < plan.shots.length && (
        <ShotPanel sid={sid} fmt={fmt} k={sel} plan={plan} st={st} meta={meta} onState={onState} onErr={onErr} />
      )}
      {sel === null && <p className="small muted">Click a shot picture to edit it (filters, colour, HSL, effects, crop and zoom, text).</p>}
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
      <button title="Play – show the title animation again" className="link small" onClick={() => setK(k + 1)}>▶ play animation</button>
    </div>
  );
}

function rgbHex(c: number[]) {
  return `#${(c ?? [255, 255, 255]).map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")}`;
}
function hexRgb(h: string) {
  return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
}
