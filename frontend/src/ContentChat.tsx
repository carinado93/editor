import { useEffect, useRef, useState } from "react";
import { api } from "./api";

interface Msg {
  role: "user" | "assistant";
  content: string;
}

const STORE = "content-chat-v1";

/** "Social Media Content": Chat mit Claude direkt in der App, mit Carinas Regeln und Stil. */
export function ContentChat() {
  const [msgs, setMsgs] = useState<Msg[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(STORE) || "[]");
    } catch {
      return [];
    }
  });
  const [input, setInput] = useState("");
  const [lang, setLang] = useState("en");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.claudeSettings().then((s) => setConfigured(s.configured)).catch(() => setConfigured(false));
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(STORE, JSON.stringify(msgs.slice(-60)));
    } catch {
      /* Speicher nicht verfügbar */
    }
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    const next = [...msgs, { role: "user" as const, content: text }];
    setMsgs(next);
    setInput("");
    setBusy(true);
    setErr(null);
    try {
      const r = await api.claudeChat(next, lang);
      setMsgs([...next, { role: "assistant", content: r.text }]);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page chat-page">
      <div className="chat-head">
        <h2>Social Media Content</h2>
        <label className="small">
          Sprache{" "}
          <select value={lang} onChange={(e) => setLang(e.target.value)}>
            <option value="en">Englisch</option>
            <option value="de">Deutsch</option>
          </select>
        </label>
        {!!msgs.length && (
          <button className="link" onClick={() => confirm("Neuen Chat beginnen? Der bisherige wird gelöscht.") && setMsgs([])}>
            Neuer Chat
          </button>
        )}
      </div>
      {configured === false && (
        <div className="banner">
          Für den Chat braucht die App einmalig deinen Claude-Schlüssel. <a href="#/einstellungen">→ Einstellungen</a>
        </div>
      )}
      <div className="card chat">
        {!msgs.length && (
          <div className="muted chat-empty">
            <p>Frag Claude nach Ideen, Hooks, Reel-Skripten, Captions oder Karussell-Texten. Deine Regeln und dein Stil sind immer dabei.</p>
            <p className="small">Beispiele: „5 polarisierende Hooks über Sonntags-Scaries“ · „Karussell: Coping-Tools vs. Ursachen, 7 Folien“ · „Mach diese Caption kürzer: …“</p>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            <div className="bubble-text">{m.content}</div>
            {m.role === "assistant" && (
              <button className="link small" onClick={() => navigator.clipboard.writeText(m.content)}>
                kopieren
              </button>
            )}
          </div>
        ))}
        {busy && <div className="bubble assistant muted">Claude schreibt …</div>}
        <div ref={end} />
      </div>
      {err && <div className="banner error small">⚠ {err}</div>}
      <div className="chat-input">
        <textarea
          rows={3}
          value={input}
          placeholder="Deine Idee oder Frage … (Enter = senden, Umschalt+Enter = neue Zeile)"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <button className="btn" disabled={busy || !input.trim()} onClick={send}>
          Senden
        </button>
      </div>
    </div>
  );
}
