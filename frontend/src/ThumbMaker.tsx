import { useEffect, useRef, useState } from "react";
import { api, type Project, type TmState, type TmVersion } from "./api";

const LAYOUTS: [string, string][] = [
  ["auto", "Let the app choose"],
  ["top", "Top line – bold left, script right, me in the middle"],
  ["two", "Two lines – bold on top, big script over my chest"],
  ["side", "Side – me on one side, words stacked on the other"],
];

const PAIRS: [string, string][] = [
  ["colours:lilac+pink", "My colours: lilac + pink"],
  ["colours:pink+yellow", "My colours: pink + yellow"],
  ["colours:yellow+lilac", "My colours: yellow + lilac"],
  ["colours:white+pink", "My colours: white + pink"],
  ["colours:lilac+white", "My colours: lilac + white"],
];
const DEFAULT_PAIRS = ["colours:lilac+pink", "colours:pink+yellow", "colours:yellow+lilac"];

/** Startseite des Thumbnail-Makers: YouTube-Projekt wählen oder ein eigenes Thumbnail ohne Video. */
export function ThumbMakerPage({ wid }: { wid?: string }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [own, setOwn] = useState<{ wid: string; name: string; count: number }[]>([]);
  useEffect(() => {
    if (wid) return;
    api.projects().then((p) => setProjects(p.filter((x) => x.mode === "youtube" && x.status === "fertig"))).catch(() => {});
    api.tmList().then((r) => setOwn(r.own)).catch(() => {});
  }, [wid]);
  if (wid) return <ThumbMaker wid={wid} />;
  return (
    <div className="page tm-page">
      <section className="card">
        <h2>Thumbnail maker</h2>
        <p className="small muted">
          Describe a background, the app makes it as a picture, puts you in front of it and adds a 2-word title – 3 versions
          for YouTube “Test &amp; Compare”.
        </p>
        <h4>From a YouTube project</h4>
        <div className="carousel-list small">
          {projects.map((p) => <a key={p.id} className="chip" href={`#/thumbnail/${p.id}`}>{p.name}</a>)}
          {!projects.length && <span className="muted">No finished YouTube project yet.</span>}
        </div>
        <h4>Without a video (upload a photo)</h4>
        <div className="carousel-list small">
          <button className="btn small-btn" onClick={async () => { const s = await api.tmNew(); window.location.hash = `#/thumbnail/${s.wid}`; }}>
            + New thumbnail
          </button>
          {own.map((o) => <a key={o.wid} className="chip" href={`#/thumbnail/${o.wid}`}>{o.name} · {o.count} versions</a>)}
        </div>
      </section>
    </div>
  );
}

function ThumbMaker({ wid }: { wid: string }) {
  const [st, setSt] = useState<TmState | null>(null);
  const [frames, setFrames] = useState<{ k: number; t: number; file: string }[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<"backgrounds" | "titles" | "colours">("colours");
  const [prompts, setPrompts] = useState<string[]>(["", "", ""]);
  const [pairs, setPairs] = useState<string[]>(DEFAULT_PAIRS);
  const [titles, setTitles] = useState<string[][]>([["", ""], ["", ""], ["", ""]]);
  const [layout, setLayout] = useState("auto");
  const [behind, setBehind] = useState(false);
  const [doodles, setDoodles] = useState(false);

  useEffect(() => {
    api.tmGet(wid).then((s) => {
      setSt(s);
      if (s.has_video) api.tmFrames(wid).then((r) => setFrames(r.frames)).catch(() => {});
    }).catch((e) => setErr(e.message));
  }, [wid]);

  const act = async (label: string, fn: () => Promise<TmState>) => {
    setBusy(label);
    setErr(null);
    try {
      setSt(await fn());
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  if (!st) return <div className="page">{err ?? "Loading …"}</div>;
  const v = (n: string) => api.tmFileUrl(wid, n);
  const ideas = st.ideas ?? { backgrounds: [], titles: [] };

  return (
    <div className="page tm-page">
      <section className="card">
        <div className="letter-head">
          <a className="link" href={st.has_video ? `#/p/${wid}` : "#/thumbnail"}>← back</a>
          <h2 style={{ margin: 0 }}>{st.has_video ? `Thumbnail · ${st.name}` : "Thumbnail maker"}</h2>
        </div>
        {err && <div className="banner error small">{err}</div>}

        <h3>1 · Your photo</h3>
        {st.has_video && !!frames.length && (
          <>
            <p className="small muted">Click a frame from your video (or upload a photo below).</p>
            <div className="tm-frames">
              {frames.map((f) => (
                <button key={f.k} className="tm-frame" disabled={!!busy} onClick={() => act("photo", () => api.tmPhotoFrame(wid, f.k))}>
                  <img src={api.tmFrameUrl(wid, f.file)} alt={`Frame at ${f.t}s`} loading="lazy" />
                </button>
              ))}
            </div>
          </>
        )}
        <div className="row-buttons">
          <label className="btn ghost">
            {busy === "photo" ? "Cutting you out …" : "Upload a photo"}
            <input type="file" accept="image/*" hidden disabled={!!busy} onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (f) void act("photo", () => api.tmPhotoUpload(wid, f));
            }} />
          </label>
          {busy === "photo" && <span className="small muted">Cutting you out (incl. fingers and hair) …</span>}
        </div>
        {st.cutout && (
          <div className="tm-cut">
            <img className="checker" src={`${v(st.cutout)}?v=${st.photo_v ?? 0}`} alt="You, cut out" />
            <span className="small muted">Your cut-out ({st.photo_source}). Your photo is never colour-graded.</span>
          </div>
        )}
      </section>

      <section className="card">
        <h3>2 · Background &amp; title</h3>
        <div className="row-buttons small">
          <button className={`btn small-btn ${mode === "backgrounds" ? "" : "ghost"}`} onClick={() => setMode("backgrounds")}>3 backgrounds, same title</button>
          <button className={`btn small-btn ${mode === "titles" ? "" : "ghost"}`} onClick={() => setMode("titles")}>1 background, 3 titles</button>
          <button className={`btn small-btn ${mode === "colours" ? "" : "ghost"}`} onClick={() => setMode("colours")}>
            <span className="tm-swatch" style={{ background: "linear-gradient(90deg,#FEF8F3,#C9B3EC,#E8B9B7,#FAE8A5)" }} /> My colours (lilac · pink · yellow · white)
          </button>
          <button className="btn ghost small-btn" disabled={!!busy} onClick={() => act("suggest", () => api.tmSuggest(wid))}>
            {busy === "suggest" ? "Claude is thinking …" : "✨ Suggest backgrounds + titles"}
          </button>
        </div>
        {!!ideas.backgrounds.length && (
          <div className="hook-chips small">
            <span className="muted">Background ideas (click to use):</span>
            {ideas.backgrounds.map((b, k) => (
              <button key={k} className="chip" onClick={() => {
                const next = [...prompts];
                const slot = mode === "titles" ? 0 : Math.max(0, next.findIndex((x) => !x.trim()));
                next[slot === -1 ? 0 : slot] = b;
                setPrompts(next);
              }}>{b}</button>
            ))}
          </div>
        )}
        {!!ideas.titles.length && (
          <div className="hook-chips small">
            <span className="muted">Title ideas (only proposals – click to use, then edit):</span>
            {ideas.titles.map((t, k) => (
              <button key={k} className="chip" onClick={() => {
                const next = titles.map((x) => [...x]);
                next[mode === "titles" ? k : 0] = [...t];
                setTitles(next);
              }}>{t[0]} ▸ {t[1]}</button>
            ))}
          </div>
        )}
        {mode === "colours" && (
          <div className="tm-prompts small">
            <span className="muted">3 versions, each with 2 of your colours. Made by the app – free, no AI.</span>
            {[0, 1, 2].map((k) => (
              <label key={k}>Version {k + 1}{" "}
                <select value={pairs[k]} onChange={(e) => setPairs(pairs.map((p, j) => (j === k ? e.target.value : p)))}>
                  {PAIRS.map(([val, label]) => <option key={val} value={val}>{label.replace("My colours: ", "")}</option>)}
                </select>
              </label>
            ))}
          </div>
        )}
        {mode !== "colours" && <div className="tm-prompts">
          {(mode === "titles" ? [0] : [0, 1, 2]).map((k) => (
            <label key={k} className="small">Background {mode === "titles" ? "" : k + 1} – describe it in your words
              <textarea rows={2} value={prompts[k]} placeholder="e.g. cosy home office at night, lilac neon light, two monitors"
                onChange={(e) => setPrompts(prompts.map((p, j) => (j === k ? e.target.value : p)))} />
            </label>
          ))}
        </div>}
        <div className="tm-titles small">
          {(mode === "titles" ? [0, 1, 2] : [0]).map((k) => (
            <div key={k} className="tm-title-row">
              <span className="muted">Title {mode === "titles" ? k + 1 : ""}</span>
              <input value={titles[k][0]} placeholder="word 1 (bold)" onChange={(e) => setTitles(titles.map((t, j) => (j === k ? [e.target.value, t[1]] : t)))} />
              <span className="tm-tag-mini">▶</span>
              <input className="script" value={titles[k][1]} placeholder="word 2 (script)" onChange={(e) => setTitles(titles.map((t, j) => (j === k ? [t[0], e.target.value] : t)))} />
            </div>
          ))}
        </div>
        <div className="tm-opts small">
          <label>Layout
            <select value={layout} onChange={(e) => setLayout(e.target.value)}>
              {LAYOUTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </label>
          <label className="check-line"><input type="checkbox" checked={behind} onChange={(e) => setBehind(e.target.checked)} /> Text behind me</label>
          <label className="check-line"><input type="checkbox" checked={doodles} onChange={(e) => setDoodles(e.target.checked)} /> Lilac doodles</label>
        </div>
        <p className="small muted">Cost: <strong>{mode === "colours" ? "free" : mode === "titles" ? st.cost.replace("3 images", "1 image") : st.cost}</strong> · change the image service in Settings.</p>
        <button className="btn" disabled={!!busy || !st.cutout} onClick={() => act("gen", () => api.tmGenerate(wid, { mode, prompts: mode === "colours" ? pairs : prompts, titles, layout, behind, doodles }))}>
          {busy === "gen" ? "Making 3 versions … (up to a minute per background)" : !st.cutout ? "Choose your photo first" : "✨ Make 3 versions"}
        </button>
        {st.fallback_used && (
          <div className="banner error small">
            The image service could not be reached, so a blurred frame of your own photo was used as background. Check your internet
            or the image service in Settings, then press “New background”.
          </div>
        )}
      </section>

      {!!st.versions?.length && (
        <section className="card">
          <div className="carousel-head">
            <h3>3 · Your versions</h3>
            <a className="btn" href={api.tmZipUrl(wid)} download>⬇ Download all 3</a>
          </div>
          <p className="small muted">Left: full size. Right: how it looks in the phone feed (360 px). Saved in the project folder and on your Desktop (SOCIAL MEDIA APP › Thumbnails).</p>
          <div className="tm-versions">
            {st.versions.map((ver) => (
              <VersionCard key={ver.id} wid={wid} v={ver} busy={!!busy} onState={setSt} onErr={setErr} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function VersionCard({ wid, v, busy, onState, onErr }: {
  wid: string; v: TmVersion; busy: boolean; onState: (s: TmState) => void; onErr: (m: string) => void;
}) {
  const [working, setWorking] = useState<string | null>(null);
  const [t1, setT1] = useState(v.spec.title1);
  const [t2, setT2] = useState(v.spec.title2);
  const [bgPrompt, setBgPrompt] = useState(v.prompt);
  const [drag, setDrag] = useState<"me" | "text">("me");
  const imgRef = useRef<HTMLImageElement>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  useEffect(() => { setT1(v.spec.title1); setT2(v.spec.title2); }, [v.spec.title1, v.spec.title2]);

  const save = async (patch: Partial<TmVersion["spec"]>, label = "save") => {
    setWorking(label);
    try {
      onState(await api.tmUpdate(wid, v.id, patch));
    } catch (e) {
      onErr((e as Error).message);
    } finally {
      setWorking(null);
    }
  };
  const p = v.spec.person ?? {};
  const tx = v.spec.text ?? {};
  const move = (what: "me" | "text", dx: number, dy: number) => {
    const cur = what === "me" ? p : tx;
    const r = (n: number) => Math.round(n * 1000) / 1000;
    const next = { ...cur, dx: r((cur.dx ?? 0) + dx), dy: r((cur.dy ?? 0) + dy) };
    void save(what === "me" ? { person: next } : { text: next });
  };
  const url = `${api.tmFileUrl(wid, v.png)}`;

  return (
    <div className="tm-version">
      <div className="tm-previews">
        <div className="tm-big" title={`Drag to move ${drag === "me" ? "yourself" : "the title"}`}>
          <img ref={imgRef} src={url} alt={`Version ${v.id}`} draggable={false}
            onPointerDown={(e) => { start.current = { x: e.clientX, y: e.clientY }; (e.target as HTMLElement).setPointerCapture(e.pointerId); }}
            onPointerUp={(e) => {
              const s = start.current;
              start.current = null;
              const r = imgRef.current?.getBoundingClientRect();
              if (!s || !r) return;
              const dx = (e.clientX - s.x) / r.width, dy = (e.clientY - s.y) / r.height;
              if (Math.abs(dx) + Math.abs(dy) > 0.01) move(drag, dx, dy);
            }} />
          {working && <span className="tm-working small">updating …</span>}
        </div>
        <div className="tm-phone"><img src={url} alt="Phone feed size" /><span className="small muted">phone feed</span></div>
      </div>
      {!!v.warnings?.length && <div className="banner error small">⚠ {v.warnings.join(" ")}</div>}
      <div className="tm-edit small">
        <div className="tm-title-row">
          <input value={t1} onChange={(e) => setT1(e.target.value)} onBlur={() => t1 !== v.spec.title1 && save({ title1: t1 })} />
          <span className="tm-tag-mini">▶</span>
          <input className="script" value={t2} onChange={(e) => setT2(e.target.value)} onBlur={() => t2 !== v.spec.title2 && save({ title2: t2 })} />
        </div>
        <div className="tm-opts">
          <select value={v.spec.layout} disabled={busy || !!working} onChange={(e) => save({ layout: e.target.value, person: {}, text: {} })}>
            {LAYOUTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <label className="check-line"><input type="checkbox" checked={v.spec.behind} onChange={(e) => save({ behind: e.target.checked })} /> Text behind me</label>
          <label className="check-line"><input type="checkbox" checked={v.spec.doodles} onChange={(e) => save({ doodles: e.target.checked })} /> Doodles</label>
          {v.spec.doodles && (
            <input className="tm-doodle" defaultValue={v.spec.doodle_text} placeholder="little note"
              onBlur={(e) => e.target.value !== v.spec.doodle_text && save({ doodle_text: e.target.value })} />
          )}
        </div>
        <div className="tm-move">
          <span className="seg">
            <button className={drag === "me" ? "on" : ""} onClick={() => setDrag("me")}>move me</button>
            <button className={drag === "text" ? "on" : ""} onClick={() => setDrag("text")}>move the title</button>
          </span>
          <span className="muted">drag on the picture, or:</span>
          <span className="nudge">
            {([["←", -1, 0], ["↑", 0, -1], ["↓", 0, 1], ["→", 1, 0]] as const).map(([l, ddx, ddy]) => (
              <button key={l} disabled={!!working} onClick={(e) => move(drag, ddx * (e.shiftKey ? 0.05 : 0.015), ddy * (e.shiftKey ? 0.05 : 0.015))}>{l}</button>
            ))}
          </span>
          <label>size
            <input type="range" min={0.5} max={1.5} step={0.05} defaultValue={(drag === "me" ? p.s : tx.s) ?? 1} key={drag}
              onMouseUp={(e) => {
                const s = Number((e.target as HTMLInputElement).value);
                void save(drag === "me" ? { person: { ...p, s } } : { text: { ...tx, s } });
              }} />
          </label>
          <button className="link" onClick={() => save({ person: {}, text: {} })}>reset position</button>
        </div>
        <div className="tm-bg">
          {bgPrompt.startsWith("colours:") ? (
            <select value={bgPrompt} onChange={(e) => setBgPrompt(e.target.value)}>
              {PAIRS.map(([val, label]) => <option key={val} value={val}>{label}</option>)}
              <option value="">… or describe an AI background instead</option>
            </select>
          ) : (
            <input value={bgPrompt} onChange={(e) => setBgPrompt(e.target.value)} placeholder="describe a new background" />
          )}
          <button className="btn ghost small-btn" disabled={busy || !!working} onClick={async () => {
            setWorking("bg");
            try {
              onState(await api.tmNewBackground(wid, v.id, bgPrompt));
            } catch (er) {
              onErr((er as Error).message);
            } finally {
              setWorking(null);
            }
          }}>{working === "bg" ? "Making the background …" : "New background"}</button>
          <a className="btn small-btn" href={`${url}?download=1`} download={`thumbnail_${v.id}.png`}>⬇ PNG</a>
          <span className="muted">{Math.round((v.size ?? 0) / 1024)} KB · {v.layout_used}</span>
        </div>
      </div>
    </div>
  );
}
