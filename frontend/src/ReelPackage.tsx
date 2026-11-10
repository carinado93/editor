import { useEffect, useState } from "react";
import { api, formatTime, type CutView, type Overlay, type ReelTexts } from "./api";
import { CoverStudio } from "./CoverStudio";

function copy(text: string, done: (msg: string) => void) {
  navigator.clipboard.writeText(text).then(
    () => done("Copied ✓"),
    () => done("Copying did not work – please select the text and press Ctrl+C."),
  );
}

export function ReelPackage({
  id,
  cuts,
  onCuts,
  time,
  duration,
}: {
  id: string;
  cuts: CutView;
  onCuts: (c: CutView) => void;
  time: number;
  duration: number;
}) {
  const [overlays, setOverlays] = useState<Overlay[]>(cuts.cutlist.overlays ?? []);
  const [idea, setIdea] = useState("");
  const [lang, setLang] = useState("en");
  const [silent, setSilent] = useState(false);
  const [texts, setTexts] = useState<ReelTexts | null>(null);
  const [full, setFull] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => setOverlays(cuts.cutlist.overlays ?? []), [cuts]);

  useEffect(() => {
    api
      .reelTexts(id)
      .then((r) => {
        setTexts(r.texts);
        setFull(r.full_caption);
        setSilent(r.silent);
        setLang(r.language === "de" ? "de" : "en");
        setIdea(r.idea ?? "");
      })
      .catch((e) => setErr(e.message));
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

  const saveOverlays = (list: Overlay[]) =>
    act("overlays", async () => {
      onCuts(await api.setOverlays(id, list));
      setMsg("Texts saved ✓ – the preview shows them right away.");
    });

  const upd = (i: number, patch: Partial<Overlay>) => setOverlays(overlays.map((o, j) => (j === i ? { ...o, ...patch } : o)));

  const applyTexts = (r: { texts: ReelTexts; full_caption: string }) => {
    setTexts(r.texts);
    setFull(r.full_caption);
  };

  return (
    <section className="package">
      <h2>Reel package</h2>

      <div className="package-grid">
        <div className="card">
          <h3>Texts in the video</h3>
          <p className="small muted">
            Cream card in Cormorant, a *word in asterisks* becomes purple italic. Sits in the safe zone and never over your face.
            Visible for at least about 4.4 seconds so people can read it.
          </p>
          {overlays.map((o, i) => (
            <div key={o.id} className="overlay-row">
              <label className="small">
                <input type="checkbox" checked={o.on} onChange={(e) => upd(i, { on: e.target.checked })} /> show
              </label>
              <textarea rows={2} value={o.text} onChange={(e) => upd(i, { text: e.target.value })} />
              <div className="small overlay-times">
                from
                <input type="number" step={0.1} min={0} value={o.start} onChange={(e) => upd(i, { start: Number(e.target.value) })} />
                to
                <input type="number" step={0.1} min={0} value={o.end} onChange={(e) => upd(i, { end: Number(e.target.value) })} />
                sec.
                <select value={o.anim ?? "karte"} onChange={(e) => upd(i, { anim: e.target.value as Overlay["anim"] })}>
                  <option value="pop">Pop</option>
                  <option value="karte">Card (soft)</option>
                  <option value="wort">Word by word</option>
                  <option value="slide">Slide</option>
                </select>
                <span className={o.end - o.start < 4.4 ? "error-text" : "muted"}>({(o.end - o.start).toFixed(1)} s)</span>
                <button className="link danger" onClick={() => setOverlays(overlays.filter((_, j) => j !== i))}>
                  remove
                </button>
              </div>
            </div>
          ))}
          <div className="row-buttons">
            <button
              className="btn ghost"
              onClick={() =>
                setOverlays([
                  ...overlays,
                  { id: `text-${Date.now()}`, kind: "hook", anim: "karte", start: Math.round(time * 10) / 10, end: Math.min(duration, Math.round((time + 4.6) * 10) / 10), text: "", on: true },
                ])
              }
            >
              + Text at {formatTime(time)}
            </button>
            <button className="btn" disabled={!!busy} onClick={() => saveOverlays(overlays)}>
              Save texts
            </button>
          </div>
          {busy === "overlays" || (msg ?? "").startsWith("Texts") ? <Status busy={busy} err={err} msg={msg} /> : null}
        </div>

        <div className="card">
          <h3>Your idea & texts</h3>
          {silent && <div className="banner small">You don't speak in this clip. Claude looks at still frames from the clip. With an idea it gets even more precise.</div>}
          <label className="small idea-box">
            Idea / instructions (optional – otherwise Claude works out the topic from the clip)
            <textarea
              rows={3}
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              placeholder="e.g. Sunday scaries: polarising hook, 3 short statements, mention my notebook at the end"
            />
          </label>
          <label className="small">
            Language{" "}
            <select value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="en">English (@carina.dorca)</option>
              <option value="de">German (@carinadorca.coach)</option>
            </select>
          </label>
          <div className="row-buttons">
            <button className="btn ghost" disabled={!!busy} onClick={() => {
              act("ollama", async () => {
                const r = await api.reelTextsOllama(id, idea, lang);
                applyTexts(r);
                if (r.cuts?.cutlist) onCuts(r.cuts);
                setMsg(r.cuts?.warnings?.length ? r.cuts.warnings.join(" ") : "Done ✓ – hook and texts are in the video (preview on the left).");
              });
            }}>
              {busy === "ollama" ? "Local AI is writing … (1–2 min)" : "Free with Ollama"}
            </button>
            <button className="btn" disabled={!!busy} onClick={() => {
              act("claude", async () => {
                const r = await api.reelTextsClaude(id, idea, lang);
                applyTexts(r);
                if (r.cuts?.cutlist) onCuts(r.cuts);
                setMsg(r.cuts?.warnings?.length ? r.cuts.warnings.join(" ") : "Done ✓ – hook and texts are in the video (preview on the left).");
              });
            }}>
              {busy === "claude" ? "Claude is writing … (about 20–60 s)" : "Create with Claude"}
            </button>
          </div>
          <Status busy={busy} err={err} msg={msg} />
          {err?.includes("Settings") && <a className="small" href="#/einstellungen">→ go to Settings</a>}
          {!!texts?.scenes?.length && (
            <div className="scenes">
              <h4>Texts in the video (hook first)</h4>
              <ol className="small">
                {texts.scenes.map((sc, i) => (
                  <li key={i}>{sc}</li>
                ))}
              </ol>
              <button className="btn" disabled={!!busy} onClick={() => act("scenes", async () => {
                const r = await api.applyScenes(id);
                onCuts(r);
                setMsg(r.warnings?.length ? r.warnings.join(" ") : "Texts added to the video ✓ – you can still change them on the left.");
              })}>
                Spread the texts again
              </button>
            </div>
          )}
          {texts && <ReelTextEditor texts={texts} full={full} busy={!!busy} onCopy={(t) => copy(t, setMsg)}
            onSave={(t) => act("save", async () => { applyTexts(await api.saveReelTexts(id, t)); setMsg("Saved ✓"); })} />}

          <h3 style={{ marginTop: 24 }}>Reel cover</h3>
          <p className="small muted">Colour wash rotating purple → light → olive, text from "Cover text".</p>
          <CoverStudio key={`${texts?.cover_text ?? ""}|${overlays[0]?.text ?? ""}`} id={id} kinds={["reel"]} />
        </div>
      </div>
    </section>
  );
}

function ReelTextEditor({ texts, full, busy, onSave, onCopy }: {
  texts: ReelTexts; full: string; busy: boolean; onSave: (t: ReelTexts) => void; onCopy: (t: string) => void;
}) {
  const [t, setT] = useState(texts);
  useEffect(() => setT(texts), [texts]);
  return (
    <div className="meta">
      {!!texts.warnings?.length && (
        <div className="banner error small">
          {texts.warnings.map((w) => (
            <div key={w}>⚠ {w}</div>
          ))}
        </div>
      )}
      <h4>Caption</h4>
      <textarea rows={10} value={t.caption} onChange={(e) => setT({ ...t, caption: e.target.value })} />
      <h4>5 Hashtags</h4>
      <input value={t.hashtags.join(" ")} onChange={(e) => setT({ ...t, hashtags: e.target.value.split(/\s+/).filter(Boolean) })} />
      <h4>Cover text</h4>
      <input value={t.cover_text} onChange={(e) => setT({ ...t, cover_text: e.target.value })} />
      <h4>YouTube Shorts title</h4>
      <div className="copy-row">
        <input value={t.shorts_title} onChange={(e) => setT({ ...t, shorts_title: e.target.value })} />
        <button className="link" onClick={() => onCopy(t.shorts_title)}>copy</button>
      </div>
      <div className="row-buttons">
        <button className="btn" disabled={busy} onClick={() => onSave(t)}>Save changes</button>
        <button className="btn ghost" onClick={() => onCopy(full)}>Copy caption + hashtags</button>
      </div>
    </div>
  );
}

export function Status({ busy, err, msg }: { busy: string | null; err: string | null; msg: string | null }) {
  if (!busy && !err && !msg) return null;
  return (
    <div className={`banner small ${err ? "error" : ""}`} role="status">
      {busy ? "⏳ Working … please wait." : err ? `⚠ ${err}` : msg}
    </div>
  );
}
