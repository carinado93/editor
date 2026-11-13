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
          Language{" "}
          <select value={lang} onChange={(e) => setLang(e.target.value)}>
            <option value="en">English</option>
            <option value="de">German</option>
          </select>
        </label>
        {!!msgs.length && (
          <button className="link" onClick={() => confirm("Start a new chat? The current one will be deleted.") && setMsgs([])}>
            New chat
          </button>
        )}
      </div>
      {configured === false && (
        <div className="banner">
          The chat needs your Claude key once. <a href="#/einstellungen">→ Settings</a>
        </div>
      )}
      <div className="card chat">
        {!msgs.length && (
          <div className="muted chat-empty">
            <p>Ask Claude for ideas, hooks, reel scripts, captions or carousel texts. Your rules and your style are always included.</p>
            <p className="small">Examples: "5 polarizing hooks about Sunday scaries" · "Carousel: coping tools vs. causes, 7 slides" · "Make this caption shorter: …"</p>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            <div className="bubble-text">{m.content}</div>
            {m.role === "assistant" && (
              <span className="row-buttons small">
                <button className="link small" onClick={() => navigator.clipboard.writeText(m.content)}>
                  copy
                </button>
                <button className="link small" disabled={busy} title="Put the ideas from this answer into your Plan (idea box)"
                  onClick={async () => {
                    setErr(null);
                    try {
                      const r = await api.planExtract("claude", m.content, lang);
                      setErr(null);
                      alert(`${r.items.filter((x) => !x.date).length} ideas are now in your Plan → Idea box.`);
                    } catch (e) {
                      setErr((e as Error).message);
                    }
                  }}>→ Plan</button>
              </span>
            )}
          </div>
        ))}
        {busy && <div className="bubble assistant muted">Claude is writing …</div>}
        <div ref={end} />
      </div>
      {err && <div className="banner error small">⚠ {err}</div>}
      <div className="chat-input">
        <textarea
          rows={3}
          value={input}
          placeholder="Your idea or question … (Enter = send, Shift+Enter = new line)"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <button className="btn" disabled={busy || !input.trim()} onClick={send}>
          Send
        </button>
      </div>
    </div>
  );
}
