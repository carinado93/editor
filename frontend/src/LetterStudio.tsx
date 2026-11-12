import { useEffect, useState } from "react";
import { api, type Letter, type LetterPart, type LetterSlide, type LetterSummary } from "./api";

const PART_NAMES: Record<string, string[]> = {
  en: ["Part 1 · Holding my breath", "Part 2 · Letting go", "Part 3 · After the noise"],
  de: ["Teil 1 · Den Atem anhalten", "Teil 2 · Loslassen", "Teil 3 · Nach dem Lärm"],
};
const ACRYLIC = ["raw painting", "soft (your favourite)", "softer", "very watercolor-like"];
const hashtags = (c: string) => (c.match(/(^|\s)#[\p{L}\p{N}_]+/gu) ?? []).length;

/** Kleines Versions-Kennzeichen, damit Vorschaubilder nach jeder Änderung neu geladen werden. */
function ver(part: LetterPart, s?: LetterSlide) {
  const raw = JSON.stringify([part.style, part.acrylic, s ?? part.slides]);
  let h = 0;
  for (let i = 0; i < raw.length; i++) h = (h * 31 + raw.charCodeAt(i)) | 0;
  return String(h);
}

/** Briefe/Gedichte → 3 Karussells pro Konto, im Stil der bisherigen Posts, dann Planen in Metricool. */
export function LetterStudio() {
  const [list, setList] = useState<LetterSummary[]>([]);
  const [letter, setLetter] = useState<Letter | null>(null);
  const [lang, setLang] = useState("en");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [form, setForm] = useState({ title: "", number: "", langs: "en" });
  const [open, setOpen] = useState<{ idx: number; k: number } | null>(null);

  useEffect(() => {
    api.letters().then((r) => setList(r.letters)).catch(() => {});
  }, []);

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

  const create = () =>
    act("new", async () => {
      const langs = form.langs === "both" ? ["en", "de"] : [form.langs];
      const l = await api.letterNew(form.title, form.number, langs);
      setLetter(l);
      setLang(langs[0]);
      setList((await api.letters()).letters);
    });

  const savePart = async (idx: number, patch: Partial<LetterPart>) => {
    if (!letter) return;
    try {
      setLetter(await api.letterPart(letter.id, lang, idx, patch));
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const [sentence, setSentence] = useState<string | null>(null);

  const askClaude = (label: string, fn: () => Promise<{ letter: Letter; sentence: string }>) =>
    act(label, async () => {
      const r = await fn();
      setLetter(r.letter);
      setSentence(r.sentence);
      await navigator.clipboard.writeText(r.sentence).catch(() => {});
    });

  const sync = () =>
    act("sync", async () => {
      if (!letter) return;
      const r = await api.letterSync(letter.id);
      setLetter(r.letter);
      setMsg(r.pictures || r.scheduled
        ? `${r.pictures} new picture${r.pictures === 1 ? "" : "s"} from Canva · ${r.scheduled} part${r.scheduled === 1 ? "" : "s"} scheduled ✓`
        : "Nothing new yet – Claude may still be working. Try again in a minute.");
    });

  if (!letter) {
    return (
      <div className="page letter-page">
        <section className="card">
          <h2>Letters</h2>
          <p className="small muted">
            A letter or poem → 3 carousels (Part 1–3) for The Long Exhale and/or Lieber Schatten, liebes Ich, exactly in the
            look of your posts. Preview, edit, then schedule in Metricool.
          </p>
          <div className="letter-new">
            <label className="small">Letter title<input value={form.title} placeholder="Dear black dog" onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
            <label className="small">Folder no.<input value={form.number} placeholder="09" onChange={(e) => setForm({ ...form, number: e.target.value })} /></label>
            <label className="small">Account
              <select value={form.langs} onChange={(e) => setForm({ ...form, langs: e.target.value })}>
                <option value="en">English · thelongexhale.book</option>
                <option value="de">German · lieberschatten.buch</option>
                <option value="both">Both (you write the German text yourself)</option>
              </select>
            </label>
            <button className="btn" disabled={!!busy || !form.title.trim()} onClick={create}>+ New letter</button>
          </div>
          {err && <div className="banner error small">{err}</div>}
          {!!list.length && (
            <div className="carousel-list small">
              <span className="muted">Your letters:</span>
              {list.map((l) => (
                <button key={l.id} className="chip" onClick={() => act("load", async () => {
                  const x = await api.letter(l.id);
                  setLetter(x);
                  setLang(x.langs[0]);
                })}>{l.number} – {l.title} ({l.langs.map((x) => x.toUpperCase()).join("+")})</button>
              ))}
            </div>
          )}
        </section>
      </div>
    );
  }

  const parts = letter.parts[lang];
  const allRendered = letter.langs.every((lg) => letter.parts[lg].every((p) => !p.slides.length || p.files.length));

  return (
    <div className="page letter-page">
      <section className="card">
        <div className="letter-head">
          <button className="link" onClick={() => setLetter(null)}>← All letters</button>
          <input className="letter-no" value={letter.number} onChange={(e) => setLetter({ ...letter, number: e.target.value })}
            onBlur={() => api.letterMeta(letter.id, { number: letter.number })} />
          <input className="letter-title" value={letter.title} onChange={(e) => setLetter({ ...letter, title: e.target.value })}
            onBlur={() => api.letterMeta(letter.id, { title: letter.title })} />
          {letter.langs.length > 1 && (
            <span className="tempo">
              {letter.langs.map((lg) => (
                <button key={lg} className={lang === lg ? "on" : ""} onClick={() => { setLang(lg); setOpen(null); }}>{lg === "en" ? "English" : "Deutsch"}</button>
              ))}
            </span>
          )}
        </div>
        <p className="small muted">
          Blank line = new slide · <code>*a line*</code> = script line · first slide = cover. Your words are never changed.
          “Coming soon” / “Demnächst” is added at the end automatically.
        </p>
        <div className="row-buttons">
          <button className="btn ghost" disabled={!!busy} onClick={() => act("suggest", async () => {
            setLetter(await api.letterSuggest(letter.id, lang, "claude"));
            setMsg("Captions and picture ideas suggested ✓ – edit them as you like.");
          })}>{busy === "suggest" ? "Claude is thinking …" : "✨ Suggest captions + picture ideas"}</button>
          <button className="btn ghost" disabled={!!busy} onClick={() => act("render", async () => {
            setLetter(await api.letterRender(letter.id));
            setMsg("All slides rendered ✓ – PNG + JPG are ready.");
          })}>{busy === "render" ? "Rendering …" : "Render all slides"}</button>
          <button className="btn ghost" disabled={!!busy} onClick={() => askClaude("pictures", () => api.letterPictures(letter.id))}>
            {busy === "pictures" ? "Preparing …" : "🎨 Pictures with Canva (via Claude)"}
          </button>
          <button className="btn ghost" disabled={!!busy} onClick={sync}>{busy === "sync" ? "Checking …" : "⟳ Get pictures & status"}</button>
          {allRendered && <a className="btn ghost" href={api.letterZip(letter.id)} download>⬇ ZIP (your folder layout)</a>}
        </div>
        {sentence && <ClaudeSentence text={sentence} onClose={() => setSentence(null)} />}
        {err && <div className="banner error small pre">{err}</div>}
        {msg && <div className="banner small">{msg}</div>}
      </section>

      <div className="letter-parts">
        {parts.map((p, idx) => (
          <PartCard key={`${lang}-${idx}`} letter={letter} lang={lang} idx={idx} part={p} onSave={(patch) => savePart(idx, patch)}
            onOpen={(k) => setOpen(open?.idx === idx && open.k === k ? null : { idx, k })} openK={open?.idx === idx ? open.k : null}
            onLetter={setLetter} onErr={setErr} />
        ))}
      </div>

      <section className="card">
        <h3>Approve &amp; schedule</h3>
        <p className="small muted">
          Nothing is posted before you click here. The slides (JPG, last one Coming soon / Demnächst) and a job file go to
          <code> carinado93/app</code> (branch <code>carousel-media</code>). Then you send Claude one sentence (already copied for you) and
          Claude schedules everything with your Metricool connection. Afterwards press “⟳ Get pictures &amp; status”.
        </p>
        <div className="schedule-list small">
          {letter.langs.flatMap((lg) => letter.parts[lg].map((p, i) => (
            <div key={`${lg}${i}`} className="schedule-row">
              <span>{lg.toUpperCase()} · {PART_NAMES[lg][i]} · {p.time.replace("T", " ").slice(0, 16)}</span>
              {p.scheduled?.ok ? (
                <span className="status ok">✓ scheduled {p.scheduled.planner && <a href={p.scheduled.planner} target="_blank" rel="noreferrer">planner</a>}</span>
              ) : p.scheduled?.waiting ? (
                <span className="muted">sent to Claude – waiting</span>
              ) : p.scheduled && !p.scheduled.ok ? (
                <span className="error-text">⚠ {p.scheduled.error} – press “Approve” again to retry this part</span>
              ) : (
                <span className="muted">{p.slides.length ? "not scheduled yet" : "no text"}</span>
              )}
            </div>
          )))}
        </div>
        <button className="btn" disabled={!!busy} onClick={() => {
          const lines = letter.langs.flatMap((lg) => letter.parts[lg].map((p, i) => [lg, i, p] as const))
            .filter(([, , p]) => p.slides.length && !p.scheduled?.ok)
            .map(([lg, i, p]) => `${lg.toUpperCase()} ${PART_NAMES[lg][i]} – ${p.time.replace("T", " ").slice(0, 16)}`).join("\n");
          if (lines && confirm(`Approve and send these posts to Claude for scheduling?\n\n${lines}`)) askClaude("send", () => api.letterSend(letter.id));
          else if (!lines) setMsg("Everything is already scheduled ✓");
        }}>{busy === "send" ? "Uploading slides …" : "Approve & schedule"}</button>
        <button className="link danger" style={{ marginLeft: 16 }} onClick={() => confirm("Delete this letter from the app?") &&
          act("del", async () => { setList((await api.letterDelete(letter.id)).letters); setLetter(null); })}>delete letter</button>
      </section>
    </div>
  );
}

function PartCard({ letter, lang, idx, part, onSave, onOpen, openK, onLetter, onErr }: {
  letter: Letter; lang: string; idx: number; part: LetterPart; onSave: (p: Partial<LetterPart>) => Promise<void>;
  onOpen: (k: number) => void; openK: number | null; onLetter: (l: Letter) => void; onErr: (m: string) => void;
}) {
  const [text, setText] = useState(part.text);
  const [caption, setCaption] = useState(part.caption);
  const [acrylic, setAcrylic] = useState(part.acrylic);
  useEffect(() => setText(part.text), [part.text]);
  useEffect(() => setCaption(part.caption), [part.caption]);
  useEffect(() => setAcrylic(part.acrylic), [part.acrylic]);
  const n = hashtags(caption);
  const painted = part.style === "painted";

  return (
    <section className="card part-card">
      <h3>{PART_NAMES[lang][idx]}</h3>
      <span className="tempo small">
        <button className={!painted ? "on" : ""} onClick={() => onSave({ style: "storyteller" })}>Storyteller</button>
        <button className={painted ? "on" : ""} onClick={() => onSave({ style: "painted" })}>Painted Scene</button>
      </span>
      {painted && (
        <label className="small acrylic">
          Acrylic: <strong>{acrylic}</strong> – {ACRYLIC[acrylic]}
          <input type="range" min={0} max={3} step={1} value={acrylic} onChange={(e) => setAcrylic(Number(e.target.value))}
            onMouseUp={() => onSave({ acrylic })} onTouchEnd={() => onSave({ acrylic })} onKeyUp={() => onSave({ acrylic })} />
        </label>
      )}
      <label className="small">Text (blank line = new slide)
        <textarea rows={9} value={text} onChange={(e) => setText(e.target.value)} onBlur={() => text !== part.text && onSave({ text })}
          placeholder={idx === 0 ? "Dear black dog,\nI'm the only one\nwho can see you.\n\nYou're there all the time,\n…" : "Dear black dog,\n…"} />
      </label>
      {part.auto_split && <div className="small seo-note warn">No blank lines found – I split the text myself. Please check the slides below.</div>}

      {!!part.slides.length && (
        <div className="letter-sheet">
          {part.slides.map((s, k) => (
            <button key={k} className={`letter-thumb ${openK === k ? "on" : ""}`} onClick={() => onOpen(k)} title="Click to edit this slide">
              <img src={api.letterPreviewUrl(letter.id, lang, idx, k, ver(part, s))} alt={`Slide ${k + 1}`} loading="lazy"
                onError={(e) => ((e.target as HTMLImageElement).style.opacity = "0.25")} />
              <span>{k + 1}{painted && !s.image ? " · needs painting" : !painted && s.wants_art && !s.image ? " · picture?" : ""}</span>
            </button>
          ))}
          <div className="letter-thumb soon">
            <img src={api.letterPreviewUrl(letter.id, lang, idx, part.slides.length, "soon")} alt="Coming soon" loading="lazy" />
            <span>{part.slides.length + 1} · {lang === "de" ? "Demnächst" : "Coming soon"}</span>
          </div>
        </div>
      )}
      {openK != null && part.slides[openK] && (
        <SlideEditor letter={letter} lang={lang} idx={idx} k={openK} part={part} onSave={onSave} onLetter={onLetter} onErr={onErr} />
      )}

      <label className="small">Date &amp; time (Europe/Berlin)
        <input type="datetime-local" value={part.time.slice(0, 16)} onChange={(e) => onSave({ time: e.target.value + ":00" })} />
      </label>
      <label className="small">Caption <span className={n === 5 ? "status ok" : "error-text"}>{n === 5 ? "✓ 5 hashtags" : `⚠ ${n} hashtags – Instagram needs exactly 5`}</span>
        <textarea rows={4} value={caption} onChange={(e) => setCaption(e.target.value)} onBlur={() => caption !== part.caption && onSave({ caption })} />
      </label>
    </section>
  );
}

function SlideEditor({ letter, lang, idx, k, part, onSave, onLetter, onErr }: {
  letter: Letter; lang: string; idx: number; k: number; part: LetterPart; onSave: (p: Partial<LetterPart>) => Promise<void>;
  onLetter: (l: Letter) => void; onErr: (m: string) => void;
}) {
  const s = part.slides[k];
  const [lines, setLines] = useState(s.lines.join("\n"));
  const [motif, setMotif] = useState(s.motif);
  useEffect(() => setLines(s.lines.join("\n")), [s.lines.join("\n")]);
  useEffect(() => setMotif(s.motif), [s.motif]);
  const painted = part.style === "painted";
  const setSlides = (fn: (sl: LetterSlide[]) => LetterSlide[]) => onSave({ slides: fn(part.slides.map((x) => ({ ...x, lines: [...x.lines] }))) });
  const patch = (p: Partial<LetterSlide>) => setSlides((sl) => sl.map((x, j) => (j === k ? { ...x, ...p } : x)));

  return (
    <div className="slide-editor small">
      <strong>Slide {k + 1}{k === 0 ? " (cover)" : ""}</strong>
      <textarea rows={Math.max(3, s.lines.length + 1)} value={lines} onChange={(e) => setLines(e.target.value)}
        onBlur={() => lines !== s.lines.join("\n") && patch({ lines: lines.split("\n").filter((x) => x.trim()) })} />
      <div className="row-buttons">
        {k > 0 && <button className="link" onClick={() => setSlides((sl) => {
          const first = sl[k].lines.shift();
          if (first) sl[k - 1].lines.push(first);
          return sl.filter((x) => x.lines.length);
        })}>↑ first line to previous slide</button>}
        {k < part.slides.length - 1 && <button className="link" onClick={() => setSlides((sl) => {
          const last = sl[k].lines.pop();
          if (last) sl[k + 1].lines.unshift(last);
          return sl.filter((x) => x.lines.length);
        })}>↓ last line to next slide</button>}
        {!painted && (
          <button className="link" onClick={() => patch({ bg: s.bg === "sage" ? "cream" : "sage" })}>
            background: {s.bg === "sage" ? "sage → cream" : "cream → sage"}
          </button>
        )}
      </div>
      <div className="slide-image">
        <strong>{painted ? "Painting" : "Watercolor illustration (optional)"}</strong>
        <label>Picture idea
          <input value={motif} placeholder={painted ? "a quiet bedroom at night, a warm lamp" : "a smoky half-transparent black dog"}
            onChange={(e) => setMotif(e.target.value)} onBlur={() => motif !== s.motif && patch({ motif })} />
        </label>
        <div className="row-buttons">
          <label className="btn ghost small-btn">
            {s.image ? "Replace image" : "Upload image"}
            <input type="file" accept="image/*" hidden onChange={async (e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (!f) return;
              try {
                onLetter(await api.letterImage(letter.id, lang, idx, k, f));
              } catch (er) {
                onErr((er as Error).message);
              }
            }} />
          </label>
          {s.image && <button className="link danger" onClick={async () => onLetter(await api.letterImageDelete(letter.id, lang, idx, k))}>remove image</button>}
        </div>
        <span className="muted">Pictures come from Canva through Claude (button “🎨 Pictures with Canva” at the top). For a new version: remove the image, change the picture idea, and ask again.</span>
        {painted && s.image && (
          <div className="crop-sliders">
            <label>Zoom {s.zoom.toFixed(2)}<input type="range" min={1} max={2} step={0.05} defaultValue={s.zoom} onMouseUp={(e) => patch({ zoom: Number((e.target as HTMLInputElement).value) })} /></label>
            <label>Left ↔ right<input type="range" min={0} max={1} step={0.05} defaultValue={s.fx} onMouseUp={(e) => patch({ fx: Number((e.target as HTMLInputElement).value) })} /></label>
            <label>Up ↕ down<input type="range" min={0} max={1} step={0.05} defaultValue={s.fy} onMouseUp={(e) => patch({ fy: Number((e.target as HTMLInputElement).value) })} /></label>
          </div>
        )}
      </div>
    </div>
  );
}

/** Der Satz für Claude – schon kopiert, mit Knopf zum erneuten Kopieren und zum Öffnen von claude.ai. */
function ClaudeSentence({ text, onClose }: { text: string; onClose: () => void }) {
  const [copied, setCopied] = useState(true);
  return (
    <div className="claude-sentence small">
      <strong>✓ Ready. Send this to Claude (it is already copied):</strong>
      <code>{text}</code>
      <div className="row-buttons">
        <button className="btn small-btn" onClick={() => navigator.clipboard.writeText(text).then(() => setCopied(true))}>{copied ? "Copied ✓" : "Copy"}</button>
        <a className="btn ghost small-btn" href="https://claude.ai/new" target="_blank" rel="noreferrer">Open Claude</a>
        <button className="link" onClick={onClose}>close</button>
      </div>
    </div>
  );
}
