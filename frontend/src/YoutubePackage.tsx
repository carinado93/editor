import { useEffect, useState } from "react";
import { api, type YoutubeMeta } from "./api";
import { CoverStudio } from "./CoverStudio";
import { ClaudeWaiting, Status } from "./ReelPackage";
import { useClaudeRoundtrip } from "./claudeRoundtrip";

function copy(text: string, done: (msg: string) => void) {
  navigator.clipboard.writeText(text).then(
    () => done("Kopiert ✓"),
    () => done("Kopieren ging nicht – bitte Text markieren und Strg+C drücken."),
  );
}

export function YoutubePackage({ id }: { id: string }) {
  const [prompt, setPrompt] = useState("");
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
        setPrompt(r.prompt);
        setMeta(r.meta);
        setFullDesc(r.full_description);
      })
      .catch((e) => setErr(e.message));
    api.project(id).then((p) => setThumbs(p.thumbnails ?? []));
  }, [id]);

  const onClaudeAnswer = async (text: string) => {
    const r = await api.importYoutubeTexts(id, text);
    setMeta(r.meta);
    setFullDesc(r.full_description);
    setMsg("Antwort von Claude übernommen ✓");
  };
  const claude = useClaudeRoundtrip(["titles", "chapters"], onClaudeAnswer);

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
      setMsg("Gespeichert ✓");
    });

  return (
    <section className="package">
      <h2>YouTube-Paket</h2>


      <div className="package-grid">
        <div className="card">
          <h3>Titel, Beschreibung, Kapitel, Tags</h3>
          <p className="small muted">
            Die Kapitel-Zeiten passen zum <strong>geschnittenen</strong> Video. Bitte erst die Schnitte fertig machen.
          </p>
          <div className="row-buttons">
            <button className="btn" disabled={!!busy} onClick={() => act("ollama", async () => {
              const r = await api.youtubeTextsOllama(id);
              setMeta(r.meta);
              setFullDesc(r.full_description);
            })}>
              {busy === "ollama" ? "Lokale KI schreibt … (1–3 Min)" : "Mit lokaler KI erstellen (Ollama)"}
            </button>
            <button className="btn ghost" disabled={!!busy} onClick={() => {
              setErr(null);
              setMsg(null);
              if (prompt) {
                claude.start(prompt);
              } else {
                claude
                  .startLate(async () => {
                    const r = await api.youtubeTexts(id);
                    setPrompt(r.prompt);
                    return r.prompt;
                  })
                  .catch((e) => {
                    claude.cancel();
                    setErr((e as Error).message);
                  });
              }
            }}>
              Mit Claude erstellen (claude.ai)
            </button>
          </div>
          <Status busy={busy} err={err} msg={msg} />
          {claude.waiting && (
            <ClaudeWaiting hint={claude.hint} promptText={prompt} onCancel={claude.cancel} onCopy={() => claude.copyAgain(prompt)}
              onPaste={(text) => act("import", async () => { await onClaudeAnswer(text); claude.cancel(); })} />
          )}
          {meta && (
            <MetaEditor meta={meta} fullDesc={fullDesc} busy={!!busy} onSave={save} onCopy={(t) => copy(t, setMsg)} />
          )}
        </div>

        <div className="card">
          <h3>Thumbnail-Vorschläge</h3>
          <p className="small muted">Bilder, in denen deine Augen offen sind, du in die Kamera schaust und lächelst. Klick = in voller Größe öffnen.</p>
          <button className="btn" disabled={!!busy} onClick={() => act("thumbs", async () => setThumbs((await api.thumbnails(id)).thumbnails))}>
            {busy === "thumbs" ? "Suche die besten Bilder …" : thumbs.length ? "Neu suchen" : "Bilder vorschlagen"}
          </button>
          <div className="thumb-grid">
            {thumbs.map((t) => (
              <a key={t.file} href={api.thumbnailUrl(id, t.file)} target="_blank" rel="noreferrer" download>
                <img src={api.thumbnailUrl(id, t.file)} alt={`Bild bei ${t.t} s`} loading="lazy" />
              </a>
            ))}
          </div>
          <h3 style={{ marginTop: 24 }}>Thumbnail gestalten</h3>
          <p className="small muted">Im Stil deiner bisherigen Thumbnails, aus den besten Standbildern oben.</p>
          <CoverStudio id={id} kinds={["youtube", "meditation", "reel"]} />

          <p className="small muted" style={{ marginTop: 16 }}>
            Für CapCut: das gerenderte MP4 und die Untertitel-Datei (.srt) aus dem Export-Ordner nehmen.
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
      <h4>Titel (einen auswählen)</h4>
      {m.titles.map((t, i) => (
        <div key={i} className="copy-row">
          <input
            value={t}
            onChange={(e) => setM({ ...m, titles: m.titles.map((x, j) => (j === i ? e.target.value : x)) })}
          />
          <span className={`small ${t.length > 70 ? "error-text" : "muted"}`}>{t.length}</span>
          <button className="link" onClick={() => onCopy(t)}>kopieren</button>
        </div>
      ))}
      <h4>Beschreibung</h4>
      <textarea rows={6} value={m.description} onChange={(e) => setM({ ...m, description: e.target.value })} />
      <h4>Kapitel</h4>
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
          Änderungen speichern
        </button>
        <button className="btn ghost" onClick={() => onCopy(fullDesc)}>
          Beschreibung + Kapitel kopieren
        </button>
        <button className="btn ghost" onClick={() => onCopy(m.tags.join(", "))}>
          Tags kopieren
        </button>
      </div>
    </div>
  );
}
