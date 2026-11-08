import { useEffect, useMemo, useRef, useState } from "react";
import { api, formatTime, type Project, type Transcript, type Word } from "./api";

interface FlatWord extends Word {
  i: number;
  seg: number;
}

export function ProjectView({ id }: { id: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState(-1);
  const [follow, setFollow] = useState(true);
  const video = useRef<HTMLVideoElement>(null);
  const textBox = useRef<HTMLDivElement>(null);

  // Projekt laden und während der Verarbeitung regelmäßig neu abfragen
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const p = await api.project(id);
        if (!alive) return;
        setProject(p);
        if (p.status === "fertig") {
          setTranscript(await api.transcript(id));
          return;
        }
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
      timer = setTimeout(load, 1500);
    };
    load();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [id]);

  const words = useMemo<FlatWord[]>(() => {
    if (!transcript) return [];
    const out: FlatWord[] = [];
    transcript.segments.forEach((s, seg) => s.words.forEach((w) => out.push({ ...w, i: out.length, seg })));
    return out;
  }, [transcript]);

  // Aktuelles Wort beim Abspielen hervorheben
  useEffect(() => {
    const v = video.current;
    if (!v || !words.length) return;
    let raf = 0;
    const tick = () => {
      const t = v.currentTime;
      let lo = 0;
      let hi = words.length - 1;
      let found = -1;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (words[mid].s <= t) {
          found = mid;
          lo = mid + 1;
        } else hi = mid - 1;
      }
      setCurrent(found >= 0 && t <= words[found].e + 0.3 ? found : -1);
      if (!v.paused) raf = requestAnimationFrame(tick);
    };
    const start = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(tick);
    };
    v.addEventListener("play", start);
    v.addEventListener("seeked", start);
    v.addEventListener("timeupdate", tick);
    return () => {
      cancelAnimationFrame(raf);
      v.removeEventListener("play", start);
      v.removeEventListener("seeked", start);
      v.removeEventListener("timeupdate", tick);
    };
  }, [words]);

  // Transkript mitscrollen
  useEffect(() => {
    if (!follow || current < 0 || !textBox.current) return;
    const el = textBox.current.querySelector<HTMLElement>(`[data-i="${current}"]`);
    if (!el) return;
    const box = textBox.current.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    if (r.top < box.top + 40 || r.bottom > box.bottom - 40) el.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [current, follow]);

  const seek = (t: number) => {
    const v = video.current;
    if (!v) return;
    v.currentTime = Math.max(0, t - 0.05);
    void v.play();
  };

  if (error && !project) return <div className="page"><div className="banner error">{error}</div></div>;
  if (!project) return <div className="page muted">Lädt …</div>;

  const ready = project.status === "fertig";
  const portrait = project.info ? project.info.height > project.info.width : false;
  const unsure = words.filter((w) => w.p < 0.5).length;

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

      <div className={`review-grid ${portrait ? "portrait" : ""}`}>
        <div className="player card">
          {project.step !== "pruefen" && project.step !== "ton" && project.step !== "vorschau" && project.info ? (
            <video ref={video} src={api.proxyUrl(id)} controls preload="auto" playsInline />
          ) : (
            <div className="player-placeholder muted">Vorschau-Video wird erstellt …</div>
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
                <dd>{unsure}</dd>
              </div>
            </dl>
          )}
        </div>

        <div className="card transcript-card">
          <div className="transcript-toolbar">
            <h3>Transkript</h3>
            <label className="small">
              <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> mitscrollen
            </label>
          </div>
          <p className="muted small hint">
            Klick auf ein Wort springt im Video dorthin. <span className="unsure">Gepunktet</span> = Spracherkennung war unsicher.
            Schnitte (durchstreichen) kommen in Meilenstein 2.
          </p>
          <div className="transcript" ref={textBox}>
            {!transcript && <p className="muted">Das Transkript erscheint hier, sobald es fertig ist.</p>}
            {transcript?.segments.map((s, si) => (
              <p key={si} className="segment">
                <button className="time" onClick={() => seek(s.s)} title="Hierher springen">
                  {formatTime(s.s)}
                </button>
                {words
                  .filter((w) => w.seg === si)
                  .map((w) => (
                    <span
                      key={w.i}
                      data-i={w.i}
                      className={`word ${w.i === current ? "current" : ""} ${w.p < 0.5 ? "unsure" : ""}`}
                      onClick={() => seek(w.s)}
                      title={`${formatTime(w.s)} · sicher: ${Math.round(w.p * 100)} %`}
                    >
                      {w.w}{" "}
                    </span>
                  ))}
              </p>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
