import { useEffect, useState } from "react";
import { api, type Carousel, type CarouselSummary, type Project } from "./api";

const THEMES: [string, string, string][] = [
  ["creme", "Cream", "#f4ecda"],
  ["flieder", "Lilac", "#e1d8ec"],
  ["lila", "Purple", "#6a4c9c"],
  ["oliv", "Olive", "#6b6f3a"],
];

function copy(text: string, done: (m: string) => void) {
  navigator.clipboard.writeText(text).then(() => done("Copied ✓"), () => done("Copying did not work – please select and copy by hand."));
}

/** Instagram-Karussells: Thema eingeben (oder ein Video wählen) → Claude schreibt → Folien im Carina-Stil. */
export function CarouselStudio() {
  const [list, setList] = useState<CarouselSummary[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [topic, setTopic] = useState("");
  const [points, setPoints] = useState(5);
  const [language, setLanguage] = useState("en");
  const [project, setProject] = useState("");
  const [car, setCar] = useState<Carousel | null>(null);
  const [edit, setEdit] = useState<Carousel | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api.carousels().then((r) => setList(r.carousels)).catch(() => {});
    api.projects().then((p) => setProjects(p.filter((x) => x.status === "fertig" && x.mode === "youtube"))).catch(() => {});
  }, []);
  useEffect(() => setEdit(car), [car]);

  const act = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setErr(null);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const draft = (engine: "claude" | "ollama") =>
    act(engine, async () => {
      const c = await api.carouselDraft(engine, { topic, points, language, project });
      setCar(c);
      setList((await api.carousels()).carousels);
      setMsg("Your carousel is ready ✓ – change any text below, then press “Update slides”.");
    });

  const update = (patch: Partial<Carousel>) =>
    act("update", async () => {
      if (!car) return;
      setCar(await api.carouselEdit(car.id, patch));
      setMsg("Slides updated ✓");
    });

  const dirty = !!edit && !!car && JSON.stringify(edit) !== JSON.stringify(car);
  const stamp = car?.files[0]?.split("_").pop() ?? "";

  return (
    <div className="page carousel-page">
      <section className="card">
        <h2>Carousel</h2>
        <p className="small muted">
          Instagram carousel in your style: cream paper, thin gold frame, Cormorant, lilac accents, your logo.
          Cover + your points + “Hi, I'm Carina” slide, with caption and 5 hashtags.
        </p>
        <div className="carousel-form">
          <label className="small">
            Topic or angle
            <textarea rows={2} value={topic} placeholder={'e.g. "Things I wish I\'d known about burnout" or "Sunday scaries: what is really going on"'}
              onChange={(e) => setTopic(e.target.value)} />
          </label>
          <div className="carousel-opts small">
            <label>
              Points
              <select value={points} onChange={(e) => setPoints(Number(e.target.value))}>
                {[3, 4, 5, 6, 7, 8].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
            <label>
              Language
              <select value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="en">English</option>
                <option value="de">German</option>
              </select>
            </label>
            <label className="grow">
              From one of your videos (optional)
              <select value={project} onChange={(e) => setProject(e.target.value)}>
                <option value="">– no, only the topic –</option>
                {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
          </div>
          <div className="row-buttons">
            <button className="btn" disabled={!!busy || (!topic.trim() && !project)} onClick={() => draft("claude")}>
              {busy === "claude" ? "Claude is writing … (about 30–60 s)" : "✨ Write with Claude"}
            </button>
            <button className="btn ghost" disabled={!!busy || (!topic.trim() && !project)} onClick={() => draft("ollama")}>
              {busy === "ollama" ? "Local AI is writing … (several minutes)" : "Free with Ollama"}
            </button>
          </div>
        </div>
        {err && <div className="banner error small">{err}</div>}
        {msg && <div className="banner small">{msg}</div>}
        {!!list.length && (
          <div className="carousel-list small">
            <span className="muted">Your carousels:</span>
            {list.map((c) => (
              <button key={c.id} className={`chip ${car?.id === c.id ? "on" : ""}`}
                onClick={() => act("load", async () => setCar(await api.carousel(c.id)))}>
                {(c.cover_title || c.topic || c.id).replace(/\*/g, "").slice(0, 48)}
              </button>
            ))}
          </div>
        )}
      </section>

      {car && edit && (
        <section className="card">
          <div className="carousel-head">
            <h3>{car.cover_title.replace(/\*/g, "")}</h3>
            <span className="theme-pick small">
              {THEMES.map(([k, l, c]) => (
                <button key={k} className={`swatch ${car.theme === k ? "on" : ""}`} title={l} style={{ background: c }}
                  disabled={!!busy} onClick={() => update({ theme: k })}><span>{l}</span></button>
              ))}
            </span>
            <a className="btn" href={api.carouselZip(car.id)} download>⬇ Download all (ZIP)</a>
          </div>
          <div className="carousel-grid">
            {car.files.map((f, k) => (
              <a key={f} href={api.carouselFile(car.id, f)} download={`${String(k + 1).padStart(2, "0")}.png`} title="Click = download this slide">
                <img src={`${api.carouselFile(car.id, f)}?v=${stamp}`} alt={`Slide ${k + 1}`} />
                <span className="small muted">{k + 1}</span>
              </a>
            ))}
          </div>

          <h4>Texts <span className="muted small">(*word* = lilac italic)</span></h4>
          <div className="carousel-edit">
            <label className="small">Cover headline
              <input value={edit.cover_title} onChange={(e) => setEdit({ ...edit, cover_title: e.target.value })} />
            </label>
            <label className="small">Teaser under it
              <input value={edit.teaser} onChange={(e) => setEdit({ ...edit, teaser: e.target.value })} />
            </label>
            {edit.slides.map((s, i) => (
              <div key={i} className="carousel-slide-edit">
                <div className="row small">
                  <strong>{i + 1}.</strong>
                  <input value={s.title} onChange={(e) => setEdit({ ...edit, slides: edit.slides.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)) })} />
                  <button className="link danger" title="Remove this slide" onClick={() => setEdit({ ...edit, slides: edit.slides.filter((_, j) => j !== i) })}>✕</button>
                </div>
                <textarea rows={Math.max(3, s.lines.length)} value={s.lines.join("\n")}
                  onChange={(e) => setEdit({ ...edit, slides: edit.slides.map((x, j) => (j === i ? { ...x, lines: e.target.value.split("\n") } : x)) })} />
              </div>
            ))}
            <button className="link" onClick={() => setEdit({ ...edit, slides: [...edit.slides, { title: "New point", lines: ["One short sentence per line."] }] })}>
              + add a slide
            </button>
          </div>
          <div className="row-buttons">
            <button className="btn" disabled={!!busy || !dirty}
              onClick={() => update({ cover_title: edit.cover_title, teaser: edit.teaser, slides: edit.slides, caption: edit.caption, hashtags: edit.hashtags })}>
              {busy === "update" ? "Drawing the slides …" : dirty ? "Update slides" : "Slides are up to date ✓"}
            </button>
          </div>

          <h4>Caption + 5 hashtags</h4>
          <textarea rows={10} value={edit.caption} onChange={(e) => setEdit({ ...edit, caption: e.target.value })} />
          <input value={edit.hashtags.join(" ")} onChange={(e) => setEdit({ ...edit, hashtags: e.target.value.split(/\s+/).filter(Boolean) })} />
          <div className="row-buttons">
            <button className="btn ghost" onClick={() => copy(edit.caption + "\n\n" + edit.hashtags.join(" "), setMsg)}>Copy caption + hashtags</button>
            <button className="link danger" onClick={() => confirm("Delete this carousel?") &&
              act("delete", async () => { setList((await api.carouselDelete(car.id)).carousels); setCar(null); })}>delete carousel</button>
          </div>
        </section>
      )}
    </div>
  );
}
