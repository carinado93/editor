import { useEffect, useState } from "react";
import { api, formatTime, type CutView, type Overlay, type ReelTexts } from "./api";
import { CoverStudio } from "./CoverStudio";

function copy(text: string, done: (msg: string) => void) {
  navigator.clipboard.writeText(text).then(
    () => done("Kopiert ✓"),
    () => done("Kopieren ging nicht – bitte Text markieren und Strg+C drücken."),
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
  const [prompt, setPrompt] = useState("");
  const [texts, setTexts] = useState<ReelTexts | null>(null);
  const [full, setFull] = useState("");
  const [paste, setPaste] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => setOverlays(cuts.cutlist.overlays ?? []), [cuts]);
  useEffect(() => {
    api
      .reelTexts(id)
      .then((r) => {
        setPrompt(r.prompt);
        setTexts(r.texts);
        setFull(r.full_caption);
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
      setMsg("Texte gespeichert ✓ – die Vorschau zeigt sie sofort.");
    });

  const upd = (i: number, patch: Partial<Overlay>) => setOverlays(overlays.map((o, j) => (j === i ? { ...o, ...patch } : o)));

  const applyTexts = (r: { texts: ReelTexts; full_caption: string }) => {
    setTexts(r.texts);
    setFull(r.full_caption);
  };

  return (
    <section className="package">
      <h2>Reel-Paket</h2>
      {err && <div className="banner error">{err}</div>}
      {msg && <div className="banner">{msg}</div>}
      <div className="package-grid">
        <div className="card">
          <h3>Texte im Video</h3>
          <p className="small muted">
            Creme-Karte in Cormorant, *Wort in Sternchen* wird lila-kursiv. Steht in der Safe Zone und nie über deinem Gesicht.
            Mindestens ca. 4,4 Sekunden sichtbar, damit man es lesen kann.
          </p>
          {overlays.map((o, i) => (
            <div key={o.id} className="overlay-row">
              <label className="small">
                <input type="checkbox" checked={o.on} onChange={(e) => upd(i, { on: e.target.checked })} /> zeigen
              </label>
              <textarea rows={2} value={o.text} onChange={(e) => upd(i, { text: e.target.value })} />
              <div className="small overlay-times">
                von
                <input type="number" step={0.1} min={0} value={o.start} onChange={(e) => upd(i, { start: Number(e.target.value) })} />
                bis
                <input type="number" step={0.1} min={0} value={o.end} onChange={(e) => upd(i, { end: Number(e.target.value) })} />
                Sek.
                <span className={o.end - o.start < 4.4 ? "error-text" : "muted"}>({(o.end - o.start).toFixed(1).replace(".", ",")} s)</span>
                <button className="link danger" onClick={() => setOverlays(overlays.filter((_, j) => j !== i))}>
                  entfernen
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
                  { id: `text-${Date.now()}`, kind: "hook", start: Math.round(time * 10) / 10, end: Math.min(duration, Math.round((time + 4.6) * 10) / 10), text: "", on: true },
                ])
              }
            >
              + Text bei {formatTime(time)}
            </button>
            <button className="btn" disabled={!!busy} onClick={() => saveOverlays(overlays)}>
              Texte speichern
            </button>
          </div>
        </div>

        <div className="card">
          <h3>Caption, 5 Hashtags, Cover-Text, Shorts-Titel</h3>
          <div className="row-buttons">
            <button className="btn" disabled={!!busy} onClick={() => act("ollama", async () => applyTexts(await api.reelTextsOllama(id)))}>
              {busy === "ollama" ? "Lokale KI schreibt … (1–2 Min)" : "Mit lokaler KI erstellen (Ollama)"}
            </button>
            <button className="btn ghost" disabled={!!busy} onClick={() => { copy(prompt, setMsg); setShowPaste(true); }}>
              Auftrag für claude.ai kopieren
            </button>
          </div>
          {showPaste && (
            <div className="paste-box">
              <p className="small">
                1. In <a href="https://claude.ai/new" target="_blank" rel="noreferrer">claude.ai</a> einfügen und abschicken. 2. Die komplette Antwort hier einfügen:
              </p>
              <textarea rows={5} value={paste} onChange={(e) => setPaste(e.target.value)} placeholder='{"caption": … }' />
              <button className="btn" disabled={!paste.trim() || !!busy} onClick={() => act("import", async () => {
                applyTexts(await api.importReelTexts(id, paste));
                setPaste("");
                setShowPaste(false);
              })}>
                Antwort übernehmen
              </button>
            </div>
          )}
          {texts && <ReelTextEditor texts={texts} full={full} busy={!!busy} onCopy={(t) => copy(t, setMsg)}
            onSave={(t) => act("save", async () => { applyTexts(await api.saveReelTexts(id, t)); setMsg("Gespeichert ✓"); })} />}

          <h3 style={{ marginTop: 24 }}>Reel-Cover</h3>
          <p className="small muted">Farbschleier im Wechsel lila → hell → oliv, Text aus „Cover-Text“.</p>
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
      <h4>Cover-Text</h4>
      <input value={t.cover_text} onChange={(e) => setT({ ...t, cover_text: e.target.value })} />
      <h4>YouTube-Shorts-Titel</h4>
      <div className="copy-row">
        <input value={t.shorts_title} onChange={(e) => setT({ ...t, shorts_title: e.target.value })} />
        <button className="link" onClick={() => onCopy(t.shorts_title)}>kopieren</button>
      </div>
      <div className="row-buttons">
        <button className="btn" disabled={busy} onClick={() => onSave(t)}>Änderungen speichern</button>
        <button className="btn ghost" onClick={() => onCopy(full)}>Caption + Hashtags kopieren</button>
      </div>
    </div>
  );
}
