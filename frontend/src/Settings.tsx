import { useEffect, useState } from "react";
import { api } from "./api";

export function Settings() {
  const [st, setSt] = useState<{ configured: boolean; masked: string; model: string } | null>(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.claudeSettings().then(setSt).catch((e) => setErr(e.message));
  }, []);

  const save = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      setSt(await api.claudeSaveKey(key));
      setKey("");
      setMsg("Key checked and saved ✓ – Claude is ready.");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <h2>Settings</h2>
      <section className="card settings-card">
        <h3>Claude (best texts)</h3>
        {st?.configured ? (
          <p className="status ok">✓ Claude is set up ({st.masked}).</p>
        ) : (
          <p className="muted">Not set up yet. One time, about 5 minutes:</p>
        )}
        <ol className="small steps">
          <li>
            Sign in at <a href="https://console.anthropic.com/" target="_blank" rel="noreferrer">console.anthropic.com</a> (the same e-mail
            as on claude.ai works).
          </li>
          <li>
            On the left <strong>"Billing"</strong> → add credit, e.g. <strong>$10</strong> (enough for about 100–200 reels). No subscription.
          </li>
          <li>
            On the left <strong>"API Keys"</strong> → <strong>"Create Key"</strong> → name e.g. "Video editor" → copy the key (starts with
            "sk-ant-").
          </li>
          <li>Paste it here and save. The app checks it right away.</li>
        </ol>
        <div className="key-row">
          <input
            type="password"
            value={key}
            placeholder="sk-ant-…"
            onChange={(e) => setKey(e.target.value)}
            autoComplete="off"
          />
          <button className="btn" disabled={busy || !key.trim()} onClick={save}>
            {busy ? "Checking …" : "Save"}
          </button>
        </div>
        {msg && <div className="banner small">{msg}</div>}
        {err && <div className="banner error small">⚠ {err}</div>}
        {st?.configured && (
          <button
            className="link danger"
            onClick={async () => {
              if (confirm("Delete the Claude key from this PC?")) setSt(await api.claudeDeleteKey());
            }}
          >
            Delete key
          </button>
        )}
        <p className="small muted">
          The key stays only on your PC (file <code>.env</code> in the app folder); it is sent nowhere except to Claude itself.
          Cost: about $0.05–0.10 per reel text, roughly $3–8 per month. You can see your usage on console.anthropic.com.
        </p>
      </section>
      <PublishSettings />
    </div>
  );
}

/** Zugangsdaten zum Veröffentlichen der Brief-Karussells (GitHub für die Bild-Links, Metricool zum Planen). */
function PublishSettings() {
  const [st, setSt] = useState<Record<string, string>>({});
  const [vals, setVals] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.publishSettings().then(setSt).catch(() => {});
  }, []);
  const field = (k: string, label: string, secret: boolean, placeholder: string) => (
    <label className="small" key={k}>
      {label} {st[k] ? <span className="status ok">✓ {secret ? st[k] : "set"}</span> : null}
      <input type={secret ? "password" : "text"} value={vals[k] ?? (secret ? "" : st[k] ?? "")} placeholder={placeholder}
        autoComplete="off" onChange={(e) => setVals({ ...vals, [k]: e.target.value })} />
    </label>
  );
  return (
    <section className="card settings-card">
      <h3>Publishing (letter carousels)</h3>
      <p className="small muted">
        The app puts the finished slides into your GitHub repo <code>carinado93/app</code> (branch <code>carousel-media</code>, folder
        <code> media/letters/</code>, like before). Claude then schedules them with your Metricool connection and makes pictures with your
        Canva connection – no Metricool API plan needed. The token stays only on your PC in the <code>.env</code> file.
      </p>
      <ol className="small steps">
        <li>GitHub → Settings → Developer settings → <strong>Fine-grained tokens</strong> → Generate: only repository <code>carinado93/app</code>,
          permission <strong>Contents: Read and write</strong>. Copy the token.</li>
      </ol>
      <div className="publish-fields">
        {field("GITHUB_TOKEN", "GitHub token", true, "github_pat_…")}
        {field("GITHUB_MEDIA_BRANCH", "Branch in carinado93/app (optional)", false, "carousel-media")}
      </div>
      <button className="btn" onClick={async () => {
        setErr(null);
        try {
          setSt(await api.publishSettingsSave(vals));
          setVals({});
          setMsg("Saved ✓");
        } catch (e) {
          setErr((e as Error).message);
        }
      }}>Save</button>
      {msg && <div className="banner small">{msg}</div>}
      {err && <div className="banner error small">⚠ {err}</div>}
    </section>
  );
}
