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
      setMsg("Schlüssel geprüft und gespeichert ✓ – Claude ist bereit.");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <h2>Einstellungen</h2>
      <section className="card settings-card">
        <h3>Claude (beste Texte)</h3>
        {st?.configured ? (
          <p className="status ok">✓ Claude ist eingerichtet ({st.masked}).</p>
        ) : (
          <p className="muted">Noch nicht eingerichtet. Einmalig ca. 5 Minuten:</p>
        )}
        <ol className="small steps">
          <li>
            Auf <a href="https://console.anthropic.com/" target="_blank" rel="noreferrer">console.anthropic.com</a> anmelden (gleiche E-Mail wie
            bei claude.ai geht).
          </li>
          <li>
            Links <strong>„Billing“</strong> → Guthaben aufladen, z. B. <strong>10 $</strong> (reicht für ca. 100–200 Reels). Kein Abo.
          </li>
          <li>
            Links <strong>„API Keys“</strong> → <strong>„Create Key“</strong> → Name z. B. „Video-Editor“ → Schlüssel kopieren (beginnt mit
            „sk-ant-“).
          </li>
          <li>Hier einfügen und speichern. Die App prüft ihn sofort.</li>
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
            {busy ? "Prüfe …" : "Speichern"}
          </button>
        </div>
        {msg && <div className="banner small">{msg}</div>}
        {err && <div className="banner error small">⚠ {err}</div>}
        {st?.configured && (
          <button
            className="link danger"
            onClick={async () => {
              if (confirm("Claude-Schlüssel von diesem PC löschen?")) setSt(await api.claudeDeleteKey());
            }}
          >
            Schlüssel löschen
          </button>
        )}
        <p className="small muted">
          Der Schlüssel bleibt nur auf deinem PC (Datei <code>.env</code> im App-Ordner), er wird nirgendwo hochgeladen außer an Claude
          selbst. Kosten: etwa 0,05–0,10 $ pro Reel-Text, ca. 3–8 $ im Monat. Den Verbrauch siehst du auf console.anthropic.com.
        </p>
      </section>
    </div>
  );
}
