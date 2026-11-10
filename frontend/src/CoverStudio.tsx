import { useEffect, useState } from "react";
import { api } from "./api";

type Kind = "youtube" | "meditation" | "reel";

const KIND_LABEL: Record<Kind, string> = {
  youtube: "YouTube: statement",
  meditation: "YouTube: Meditation",
  reel: "Reel cover",
};

const COLOR_LABEL: Record<string, string> = { lila: "Purple", hell: "Light", oliv: "Olive" };

/** Thumbnails & Reel-Cover im Stil von Carinas bisherigen Designs (3 Varianten aus verschiedenen Standbildern). */
export function CoverStudio({ id, kinds }: { id: string; kinds: Kind[] }) {
  const [kind, setKind] = useState<Kind>(kinds[0]);
  const [form, setForm] = useState({ text: "", pill: "", subtitle: "", top_pill: "", top_label: "", color: "auto" });
  const [defaults, setDefaults] = useState<Record<string, Record<string, string>> | null>(null);
  const [nextColor, setNextColor] = useState("hell");
  const [files, setFiles] = useState<string[]>([]);
  const [usedColor, setUsedColor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    api
      .coverDefaults(id)
      .then((d) => {
        setDefaults(d as unknown as Record<string, Record<string, string>>);
        setNextColor(d.next_color);
      })
      .catch((e) => setErr(e.message));
  }, [id]);

  useEffect(() => {
    if (!defaults) return;
    const d = defaults[kind] ?? {};
    setForm((f) => ({ ...f, text: d.text ?? "", pill: d.pill ?? "", subtitle: d.subtitle ?? "", top_pill: d.top_pill ?? "", top_label: d.top_label ?? "" }));
    setFiles([]);
  }, [kind, defaults]);

  const generate = async () => {
    setBusy(true);
    setErr(null);
    setInfo(null);
    try {
      const r = await api.covers(id, { kind, ...form });
      setFiles(r.files);
      setUsedColor(r.color);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const markUsed = async () => {
    if (!usedColor) return;
    const r = await api.coverColorUsed(usedColor);
    setNextColor(r.next);
    setInfo(`Noted. Next reel cover: ${COLOR_LABEL[r.next] ?? r.next}.`);
  };

  return (
    <div className="cover-studio">
      {kinds.length > 1 && (
        <div className="tempo" role="tablist">
          {kinds.map((k) => (
            <button key={k} className={kind === k ? "on" : ""} onClick={() => setKind(k)}>
              {KIND_LABEL[k]}
            </button>
          ))}
        </div>
      )}
      {err && <div className="banner error small">{err}</div>}
      {info && <div className="banner small">{info}</div>}
      <div className="cover-form small">
        <label>
          {kind === "meditation" ? "Title" : "Text"}
          <input value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} />
        </label>
        {kind === "youtube" && (
          <>
            <span className="muted">A word in *asterisks* becomes pink and bigger, e.g. "Rest didn't fix my *burnout*".</span>
            <label>
              Pill below (optional)
              <input value={form.pill} placeholder="e.g. YOUR BODY REMEMBERS" onChange={(e) => setForm({ ...form, pill: e.target.value })} />
            </label>
          </>
        )}
        {kind === "meditation" && (
          <>
            <label>
              Subtitle (italic)
              <input value={form.subtitle} placeholder="e.g. Gentle Words, Calm Mind" onChange={(e) => setForm({ ...form, subtitle: e.target.value })} />
            </label>
            <label>
              Small line at the top
              <span className="two">
                <input value={form.top_pill} placeholder="5 MINUTES" onChange={(e) => setForm({ ...form, top_pill: e.target.value })} />
                <input value={form.top_label} placeholder="GUIDED MEDITATION" onChange={(e) => setForm({ ...form, top_label: e.target.value })} />
              </span>
            </label>
          </>
        )}
        {kind === "reel" && (
          <label>
            Colour
            <select value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })}>
              <option value="auto">automatic (next: {COLOR_LABEL[nextColor] ?? nextColor})</option>
              <option value="lila">Purple</option>
              <option value="hell">Light</option>
              <option value="oliv">Olive</option>
            </select>
          </label>
        )}
      </div>
      <button className="btn" disabled={busy || !form.text.trim()} onClick={generate}>
        {busy ? "Designing …" : "Create 3 variants"}
      </button>
      {!!files.length && (
        <>
          <div className={`cover-grid ${kind === "reel" ? "tall" : ""}`}>
            {files.map((f) => (
              <a key={f} href={api.coverUrl(id, f)} download={f} title="Click = download">
                <img src={api.coverUrl(id, f)} alt="Cover variant" />
              </a>
            ))}
          </div>
          <p className="small muted">Click an image to download it.</p>
          {kind === "reel" && usedColor && (
            <button className="link" onClick={markUsed}>
              ✓ Used one of them → next cover in the next colour
            </button>
          )}
        </>
      )}
    </div>
  );
}
