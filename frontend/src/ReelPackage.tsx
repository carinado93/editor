import { useEffect, useState } from "react";
import { api, formatTime, type CutView, type Overlay, type ReelTexts } from "./api";
import { CoverStudio } from "./CoverStudio";
import { useClaudeRoundtrip } from "./claudeRoundtrip";

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
  const [idea, setIdea] = useState("");
  const [lang, setLang] = useState("en");
  const [silent, setSilent] = useState(false);
  const [texts, setTexts] = useState<ReelTexts | null>(null);
  const [full, setFull] = useState("");
  const [promptText, setPromptText] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => setOverlays(cuts.cutlist.overlays ?? []), [cuts]);

  // Auftrag für Claude schon beim Tippen vorbereiten, damit der Klick claude.ai sofort öffnen kann
  useEffect(() => {
    if (silent && !idea.trim()) {
      setPromptText("");
      return;
    }
    let alive = true;
    const t = setTimeout(() => {
      api.reelPrompt(id, idea, lang).then((r) => alive && setPromptText(r.prompt)).catch(() => alive && setPromptText(""));
    }, 400);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [id, idea, lang, silent]);
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

  const onClaudeAnswer = async (text: string) => {
    const r = await api.importReelTexts(id, text, idea, lang);
    setTexts(r.texts);
    setFull(r.full_caption);
    setMsg("Antwort von Claude übernommen ✓ – Vorschläge stehen unten.");
  };
  const claude = useClaudeRoundtrip(["scenes", "caption"], onClaudeAnswer);

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
          {busy === "overlays" || (msg ?? "").startsWith("Texte") ? <Status busy={busy} err={err} msg={msg} /> : null}
        </div>

        <div className="card">
          <h3>Deine Idee & Texte</h3>
          {silent && <div className="banner small">In diesem Clip sprichst du nicht. Schreib kurz deine Idee, daraus entstehen die Texte im Video, Caption, Hashtags und Cover.</div>}
          <label className="small idea-box">
            Idee / Anweisung {silent ? "" : "(optional – sonst nimmt die App, was du im Video sagst)"}
            <textarea
              rows={3}
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              placeholder="z. B. Sonntags-Scaries: polarisierender Hook, 3 kurze Aussagen, am Ende mein Notizbuch erwähnen"
            />
          </label>
          <label className="small">
            Sprache{" "}
            <select value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="en">Englisch (@carina.dorca)</option>
              <option value="de">Deutsch (@carinadorca.coach)</option>
            </select>
          </label>
          <div className="row-buttons">
            <button className="btn" disabled={!!busy} onClick={() => {
              if (silent && !idea.trim()) { setErr("Bitte zuerst oben deine Idee eintragen (in diesem Clip wird nicht gesprochen)."); return; }
              act("ollama", async () => { applyTexts(await api.reelTextsOllama(id, idea, lang)); setMsg("Fertig ✓ – Vorschläge stehen unten."); });
            }}>
              {busy === "ollama" ? "Lokale KI schreibt … (1–2 Min)" : "Mit lokaler KI erstellen (Ollama)"}
            </button>
            <button className="btn ghost" disabled={!!busy} onClick={() => {
              if (silent && !idea.trim()) { setErr("Bitte zuerst oben deine Idee eintragen (in diesem Clip wird nicht gesprochen)."); return; }
              setErr(null);
              setMsg(null);
              if (!promptText) { setErr("Der Auftrag wird noch vorbereitet – bitte in 1–2 Sekunden nochmal klicken."); return; }
              claude.start(promptText);
            }}>
              Mit Claude erstellen (claude.ai)
            </button>
          </div>
          <Status busy={busy} err={err} msg={msg} />
          {claude.waiting && (
            <ClaudeWaiting hint={claude.hint} promptText={promptText} onCancel={claude.cancel}
              onPaste={(text) => act("import", async () => { await onClaudeAnswer(text); claude.cancel(); })} />
          )}
          {!!texts?.scenes?.length && (
            <div className="scenes">
              <h4>Vorgeschlagene Texte fürs Video</h4>
              <ol className="small">
                {texts.scenes.map((sc, i) => (
                  <li key={i}>{sc}</li>
                ))}
              </ol>
              <button className="btn" disabled={!!busy} onClick={() => act("scenes", async () => {
                const r = await api.applyScenes(id);
                onCuts(r);
                setMsg(r.warnings?.length ? r.warnings.join(" ") : "Texte ins Video übernommen ✓ – links kannst du sie noch ändern.");
              })}>
                Passt – ins Video übernehmen
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

export function Status({ busy, err, msg }: { busy: string | null; err: string | null; msg: string | null }) {
  if (!busy && !err && !msg) return null;
  return (
    <div className={`banner small ${err ? "error" : ""}`} role="status">
      {busy ? "⏳ Läuft … bitte warten." : err ? `⚠ ${err}` : msg}
    </div>
  );
}

/** Anleitung, solange die App auf die Antwort von claude.ai wartet (mit Einfügen als Notlösung). */
export function ClaudeWaiting({ hint, promptText, onCancel, onPaste }: {
  hint: string | null; promptText: string; onCancel: () => void; onPaste: (text: string) => void;
}) {
  const [paste, setPaste] = useState("");
  return (
    <div className="paste-box">
      <p className="small">
        <strong>claude.ai ist im neuen Tab offen.</strong> Dort: <strong>Enter</strong> drücken (steht der Auftrag nicht im Feld:
        Strg+V), warten bis die Antwort fertig ist, darunter auf <strong>„Kopieren“</strong> klicken – und einfach hierher zurück.
        Die App übernimmt die Antwort dann von selbst.
      </p>
      <p className="small muted">⏳ Warte auf die Antwort von Claude …</p>
      {hint && <p className="small error-text">{hint}</p>}
      <details className="small">
        <summary>Klappt nicht? Antwort hier einfügen</summary>
        <textarea rows={4} value={paste} onChange={(e) => setPaste(e.target.value)} placeholder='{"…": … }' />
        <button className="btn" disabled={!paste.trim()} onClick={() => onPaste(paste)}>Antwort übernehmen</button>
        <details>
          <summary>Auftrag anzeigen</summary>
          <textarea rows={5} readOnly value={promptText} onFocus={(e) => e.currentTarget.select()} />
        </details>
      </details>
      <button className="link" onClick={onCancel}>abbrechen</button>
    </div>
  );
}
