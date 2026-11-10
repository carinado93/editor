import { useEffect, useState } from "react";
import { api, type YoutubeMeta } from "./api";
import { CoverStudio } from "./CoverStudio";
import { Status } from "./ReelPackage";
import { ClipsPanel } from "./ClipsPanel";

function copy(text: string, done: (msg: string) => void) {
  navigator.clipboard.writeText(text).then(
    () => done("Copied ✓"),
    () => done("Copying did not work – please select the text and press Ctrl+C."),
  );
}

export function YoutubePackage({ id }: { id: string }) {
  const [meta, setMeta] = useState<YoutubeMeta | null>(null);
  const [fullDesc, setFullDesc] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [thumbs, setThumbs] = useState<{ file: string; t: number }[]>([]);

  useEffect(() => {
    api
      .youtubeTexts(id)
      .then((r) => {
        setMeta(r.meta);
        setFullDesc(r.full_description);
      })
      .catch((e) => setErr(e.message));
    api.project(id).then((p) => setThumbs(p.thumbnails ?? []));
  }, [id]);

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

  const save = (m: YoutubeMeta) =>
    act("speichern", async () => {
      const r = await api.saveYoutubeTexts(id, m);
      setMeta(r.meta);
      setFullDesc(r.full_description);
      setMsg("Saved ✓");
    });

  return (
    <section className="package">
      <h2>YouTube package</h2>


      <ClipsPanel id={id} />
      <div className="package-grid">
        <div className="card">
          <h3>Title, description, chapters, tags</h3>
          <p className="small muted">
            The chapter times match the <strong>edited</strong> video. Please finish the cuts first.
          </p>
          <div className="row-buttons">
            <button className="btn ghost" disabled={!!busy} onClick={() => act("ollama", async () => {
              const r = await api.youtubeTextsOllama(id);
              setMeta(r.meta);
              setFullDesc(r.full_description);
            })}>
              {busy === "ollama" ? "Local AI is writing … (1–3 min)" : "Free with Ollama"}
            </button>
            <button className="btn" disabled={!!busy} onClick={() => act("claude", async () => {
              const r = await api.youtubeTextsClaude(id);
              setMeta(r.meta);
              setFullDesc(r.full_description);
              setMsg("Done ✓ – Claude's suggestions are below.");
            })}>
              {busy === "claude" ? "Claude is writing … (about 20–60 s)" : "Create with Claude"}
            </button>
          </div>
          <Status busy={busy} err={err} msg={msg} />
          {err?.includes("Settings") && <a className="small" href="#/einstellungen">→ go to Settings</a>}
          {meta && (
            <MetaEditor meta={meta} fullDesc={fullDesc} busy={!!busy} onSave={save} onCopy={(t) => copy(t, setMsg)} />
          )}
        </div>

        <div className="card">
          <h3>Thumbnail suggestions</h3>
          <p className="small muted">Frames where your eyes are open, you look into the camera and smile. Click = open full size.</p>
          <button className="btn" disabled={!!busy} onClick={() => act("thumbs", async () => setThumbs((await api.thumbnails(id)).thumbnails))}>
            {busy === "thumbs" ? "Finding the best frames …" : thumbs.length ? "Search again" : "Suggest frames"}
          </button>
          <div className="thumb-grid">
            {thumbs.map((t) => (
              <a key={t.file} href={api.thumbnailUrl(id, t.file)} target="_blank" rel="noreferrer" download>
                <img src={api.thumbnailUrl(id, t.file)} alt={`Frame at ${t.t} s`} loading="lazy" />
              </a>
            ))}
          </div>
          <h3 style={{ marginTop: 24 }}>Design a thumbnail</h3>
          <p className="small muted">In the style of your previous thumbnails, from the best frames above.</p>
          <CoverStudio id={id} kinds={["youtube", "meditation", "reel"]} />

          <p className="small muted" style={{ marginTop: 16 }}>
            For CapCut: use the rendered MP4 and the subtitle file (.srt) from the export folder.
          </p>
        </div>
      </div>
    </section>
  );
}

function MetaEditor({
  meta,
  fullDesc,
  busy,
  onSave,
  onCopy,
}: {
  meta: YoutubeMeta;
  fullDesc: string;
  busy: boolean;
  onSave: (m: YoutubeMeta) => void;
  onCopy: (t: string) => void;
}) {
  const [m, setM] = useState(meta);
  useEffect(() => setM(meta), [meta]);
  const chaptersText = m.chapters.map((c) => `${c.time} ${c.title}`).join("\n");

  return (
    <div className="meta">
      {!!meta.warnings?.length && (
        <div className="banner error small">
          {meta.warnings.map((w) => (
            <div key={w}>⚠ {w}</div>
          ))}
        </div>
      )}
      <h4>Titles (pick one)</h4>
      {m.titles.map((t, i) => (
        <div key={i} className="copy-row">
          <input
            value={t}
            onChange={(e) => setM({ ...m, titles: m.titles.map((x, j) => (j === i ? e.target.value : x)) })}
          />
          <span className={`small ${t.length > 70 ? "error-text" : "muted"}`}>{t.length}</span>
          <button className="link" onClick={() => onCopy(t)}>copy</button>
        </div>
      ))}
      <h4>Description</h4>
      <textarea rows={6} value={m.description} onChange={(e) => setM({ ...m, description: e.target.value })} />
      <h4>Chapters</h4>
      <textarea
        rows={Math.min(10, m.chapters.length + 1)}
        value={chaptersText}
        onChange={(e) =>
          setM({
            ...m,
            chapters: e.target.value
              .split("\n")
              .map((l) => l.match(/^\s*(\d+:\d{2}(?::\d{2})?)\s+(.*)$/))
              .filter(Boolean)
              .map((x) => ({ time: x![1], title: x![2] })),
          })
        }
      />
      <h4>Tags</h4>
      <input value={m.tags.join(", ")} onChange={(e) => setM({ ...m, tags: e.target.value.split(",").map((x) => x.trim()) })} />
      <h4>Hashtags</h4>
      <input value={m.hashtags.join(" ")} onChange={(e) => setM({ ...m, hashtags: e.target.value.split(/\s+/).filter(Boolean) })} />
      <div className="row-buttons">
        <button className="btn" disabled={busy} onClick={() => onSave(m)}>
          Save changes
        </button>
        <button className="btn ghost" onClick={() => onCopy(fullDesc)}>
          Copy description + chapters
        </button>
        <button className="btn ghost" onClick={() => onCopy(m.tags.join(", "))}>
          Copy tags
        </button>
      </div>
    </div>
  );
}
