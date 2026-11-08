// Weg B: claude.ai mit Carinas Abo, so automatisch wie möglich.
// 1. Knopf → claude.ai öffnet sich, der Auftrag steht schon im Eingabefeld (und liegt zur Sicherheit in der Zwischenablage).
// 2. Carina drückt Enter und klickt unter der Antwort auf "Kopieren".
// 3. Sobald sie zurück in die App wechselt, liest die App die Zwischenablage und übernimmt die Antwort von selbst.

import { useCallback, useEffect, useRef, useState } from "react";

/** Prüft, ob ein Text wie eine passende Claude-Antwort aussieht (JSON mit den erwarteten Feldern). */
export function looksLikeAnswer(text: string, keys: string[]): boolean {
  const m = text.match(/\{[\s\S]*\}/);
  if (!m) return false;
  try {
    const obj = JSON.parse(m[0]);
    return keys.some((k) => k in obj);
  } catch {
    return false;
  }
}

export function useClaudeRoundtrip(keys: string[], onAnswer: (text: string) => Promise<void>) {
  const [waiting, setWaiting] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const lastPrompt = useRef("");
  const busy = useRef(false);

  const check = useCallback(async () => {
    if (!waiting || busy.current) return;
    let text = "";
    try {
      text = await navigator.clipboard.readText();
    } catch {
      setHint("Bitte erlaube der App einmal, die Zwischenablage zu lesen (Browser fragt oben), oder füge die Antwort unten ein.");
      return;
    }
    if (!text || text === lastPrompt.current) return; // noch der Auftrag, nicht die Antwort
    if (!looksLikeAnswer(text, keys)) return;
    busy.current = true;
    try {
      await onAnswer(text);
      setWaiting(false);
      setHint(null);
    } finally {
      busy.current = false;
    }
  }, [waiting, keys, onAnswer]);

  useEffect(() => {
    if (!waiting) return;
    const onFocus = () => void check();
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onFocus);
    const timer = setInterval(() => document.hasFocus() && void check(), 2000);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onFocus);
      clearInterval(timer);
    };
  }, [waiting, check]);

  /** Muss direkt im Klick aufgerufen werden (sonst blockiert der Browser das neue Fenster). */
  const start = useCallback(async (getPrompt: () => Promise<string>) => {
    const tab = window.open("about:blank", "_blank");
    const prompt = await getPrompt();
    lastPrompt.current = prompt;
    try {
      await navigator.clipboard.writeText(prompt);
    } catch {
      /* Zwischenablage nicht erlaubt: Auftrag steht trotzdem im Eingabefeld */
    }
    const url = "https://claude.ai/new?q=" + encodeURIComponent(prompt);
    if (tab) tab.location.href = url;
    else window.open(url, "_blank");
    setWaiting(true);
    setHint(null);
    return prompt;
  }, []);

  const cancel = useCallback(() => setWaiting(false), []);
  return { waiting, hint, start, cancel, check };
}
