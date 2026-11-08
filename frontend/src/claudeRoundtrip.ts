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

  /** Direkt im Klick aufrufen, mit dem schon vorbereiteten Auftrag: claude.ai öffnet sich sofort (kein leerer Tab). */
  const start = useCallback((prompt: string) => {
    lastPrompt.current = prompt;
    const encoded = encodeURIComponent(prompt);
    // Sehr lange Adressen lehnen Browser/claude.ai ab → dann ohne Auftrag in der Adresse (Strg+V aus der Zwischenablage)
    const url = encoded.length < 7000 ? "https://claude.ai/new?q=" + encoded : "https://claude.ai/new";
    // ZUERST kopieren (solange die App das aktive Fenster ist), DANN claude.ai öffnen –
    // sonst verbietet der Browser das Kopieren.
    navigator.clipboard.writeText(prompt).catch(() => {
      setHint("Kopieren hat der Browser nicht erlaubt – bitte unten „Auftrag kopieren“ klicken.");
    });
    window.open(url, "_blank");
    setWaiting(true);
    setHint(encoded.length < 7000 ? null : "Der Auftrag ist lang – bitte in claude.ai mit Strg+V einfügen.");
  }, []);

  /** Falls der Auftrag noch nicht fertig ist: claude.ai trotzdem sofort öffnen (ohne leeren Tab),
   * den Auftrag danach in die Zwischenablage legen → in claude.ai mit Strg+V einfügen. */
  const startLate = useCallback(async (getPrompt: () => Promise<string>) => {
    window.open("https://claude.ai/new", "_blank");
    setWaiting(true);
    setHint("Auftrag wird vorbereitet …");
    const prompt = await getPrompt();
    lastPrompt.current = prompt;
    // claude.ai hat jetzt den Fokus → der Browser erlaubt kein Kopieren. Deshalb: Knopf "Auftrag kopieren" in der App.
    setHint("Bitte unten auf „Auftrag kopieren“ klicken, dann in claude.ai Strg+V und Enter.");
    return prompt;
  }, []);

  const copyAgain = useCallback(async (prompt: string) => {
    lastPrompt.current = prompt;
    try {
      await navigator.clipboard.writeText(prompt);
      setHint("Auftrag kopiert ✓ – jetzt in claude.ai Strg+V und Enter.");
    } catch {
      setHint("Kopieren ging nicht – bitte „Auftrag anzeigen“ öffnen, Strg+A und Strg+C.");
    }
  }, []);

  const cancel = useCallback(() => setWaiting(false), []);
  return { waiting, hint, start, startLate, copyAgain, cancel, check };
}
