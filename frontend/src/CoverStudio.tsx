import { useEffect, useState } from "react";
import { api, type CoverPhoto } from "./api";

type Kind = "youtube" | "center" | "meditation" | "reel";

const KIND_LABEL: Record<Kind, string> = {
  youtube: "Statement",
  center: "You in the middle",
  meditation: "Meditation",
  reel: "Reel cover",
};

const COLOR_LABEL: Record<string, string> = { lila: "Purple", hell: "Light", oliv: "Olive" };

/** Thumbnails & Reel-Cover im Stil von Carinas bisherigen Designs (3 Varianten aus verschiedenen Standbildern). */
export function CoverStudio({ id, kinds }: { id: string; kinds: Kind[] }) {
  const [kind, setKind] = useState<Kind>(kinds[0]);
  const [form, setForm] = useState({ text: "", pill: "", subtitle: "", top_pill: "", top_label: "", color: "auto", theme: "rosa" });
  const [defaults, setDefaults] = useState<Record<string, Record<string, string>> | null>(null);
  const [nextColor, setNextColor] = useState("hell");
  const [files, setFiles] = useState<string[]>([]);
  const [usedColor, setUsedColor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [photos, setPhotos] = useState<CoverPhoto[]>([]);
  const [hooks, setHooks] = useState<string[]>([]);

  // Thumbnail-Hooks von Claude (aus "Title, description …") – Klick übernimmt den Text
  useEffect(() => {
    const load = () => api.coverDefaults(id).then((d) => setHooks((d as unknown as { thumb_hooks?: string[] }).thumb_hooks ?? [])).catch(() => {});
    void load();
    const use = (e: Event) => {
      const t = (e as CustomEvent<string>).detail;
      setKind((k) => (k === "reel" || k === "meditation" ? "youtube" : k));
      setTimeout(() => setForm((f) => ({ ...f, text: t })), 0);
    };
    window.addEventListener("meta-updated", load);
    window.addEventListener("use-thumb-hook", use);
    return () => {
      window.removeEventListener("meta-updated", load);
      window.removeEventListener("use-thumb-hook", use);
    };
  }, [id]);
  const [picked, setPicked] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    api.coverPhotos(id).then((r) => setPhotos(r.photos)).catch(() => {});
  }, [id]);

  const upload = async (list: FileList | null) => {
    if (!list?.length) return;
    setUploading(true);
    setErr(null);
    try {
      let last: CoverPhoto[] = photos;
      for (const f of Array.from(list)) last = (await api.addCoverPhoto(id, f)).photos;
      setPhotos(last);
      // neue Fotos gleich auswählen
      const fresh = last.slice(-list.length).map((p) => p.file);
      setPicked((p) => [...p, ...fresh]);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

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
      const r = await api.covers(id, { kind, ...form, photos: picked });
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
        {kind !== "reel" && kind !== "meditation" && !!hooks.length && (
          <span className="hook-chips">
            <span className="muted">Ideas from Claude:</span>
            {hooks.map((h) => (
              <button key={h} type="button" className={`chip ${form.text === h ? "on" : ""}`} onClick={() => setForm({ ...form, text: h })}>
                {h.replace(/\*/g, "")}
              </button>
            ))}
          </span>
        )}
        {kind === "center" && (
          <span className="muted">Up to 3 slanted bars: left, middle (big, in front of you), right. Put the big word in *asterisks*, e.g. "I can't *anymore*".</span>
        )}
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
        {kind !== "reel" && (
          <label>
            Colour
            <span className="theme-pick">
              {([["rosa", "Pink", "#c9506a"], ["lila", "Lilac", "#6444a5"], ["gruen", "Green", "#8b9a6b"]] as const).map(([k, l, c]) => (
                <button key={k} type="button" className={`btn ghost ${form.theme === k ? "on" : ""}`}
                  style={{ borderColor: c, color: form.theme === k ? "#fff" : c, background: form.theme === k ? c : undefined }}
                  onClick={() => setForm({ ...form, theme: k })}>{l}</button>
              ))}
            </span>
          </label>
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
      <div className="small" style={{ margin: "12px 0" }}>
        <strong>Your own photos</strong> (optional) – tick the ones to use. Without a tick, 3 stills from the video are used.
        <div className="cover-own">
          {photos.map((p) => (
            <label key={p.file} className={`cover-own-item ${picked.includes(p.file) ? "on" : ""}`}>
              <img src={api.coverPhotoUrl(id, p.file)} alt="Your photo" />
              <span>
                <input type="checkbox" checked={picked.includes(p.file)}
                  onChange={(e) => setPicked(e.target.checked ? [...picked, p.file] : picked.filter((x) => x !== p.file))} />
                {p.face ? " use" : " use (no face found – centred)"}
              </span>
              <button className="link danger" onClick={async (e) => {
                e.preventDefault();
                if (!confirm("Remove this photo from the app? (The file on your PC stays.)")) return;
                setPhotos((await api.deleteCoverPhoto(id, p.file)).photos);
                setPicked(picked.filter((x) => x !== p.file));
              }}>remove</button>
            </label>
          ))}
          <label className="btn ghost cover-own-add">
            {uploading ? "Uploading …" : "+ Add photos"}
            <input type="file" accept="image/*" multiple hidden disabled={uploading}
              onChange={(e) => { void upload(e.target.files); e.target.value = ""; }} />
          </label>
        </div>
      </div>
      <button className="btn" disabled={busy || uploading || !form.text.trim()} onClick={generate}>
        {busy ? "Designing …" : picked.length ? `Create ${picked.length} variant${picked.length > 1 ? "s" : ""} from your photos` : "Create 3 variants"}
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
          <p className="small muted">
            Saved on your Desktop: SOCIAL MEDIA APP › Thumbnails.{" "}
            <button className="link" onClick={() => api.openOutbox("thumbnails").catch(() => {})}>📁 Open folder</button>
          </p>
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
