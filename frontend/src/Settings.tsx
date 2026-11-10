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
    </div>
  );
}
