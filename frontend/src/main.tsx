import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/cormorant-garamond/600.css";
import "@fontsource/cormorant-garamond/600-italic.css";
import "@fontsource/jost/400.css";
import "@fontsource/jost/500.css";
import "@fontsource/poppins/latin-600.css";
import "./styles.css";
import { api, type SystemInfo } from "./api";
import { ProjectList } from "./ProjectList";
import { ProjectView } from "./ProjectView";

function useHash() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

function UpdateBanner() {
  const [st, setSt] = useState<{ available: boolean; behind: number } | null>(null);
  const [phase, setPhase] = useState<"idle" | "laeuft" | "neustart" | "fehler">("idle");
  const [err, setErr] = useState("");

  useEffect(() => {
    const check = () => api.updateStatus().then(setSt).catch(() => {});
    check();
    const t = setInterval(check, 15 * 60 * 1000);
    return () => clearInterval(t);
  }, []);

  const go = async () => {
    setPhase("laeuft");
    try {
      const old = (await api.version()).version;
      await api.updateNow();
      setPhase("neustart");
      // Warten, bis der Motor mit der neuen Version wieder da ist, dann Seite neu laden
      const start = Date.now();
      const poll = setInterval(async () => {
        try {
          const v = (await api.version()).version;
          if (v !== old || Date.now() - start > 120000) {
            clearInterval(poll);
            window.location.reload();
          }
        } catch {
          /* Motor startet noch */
        }
      }, 2000);
    } catch (e) {
      setErr((e as Error).message);
      setPhase("fehler");
    }
  };

  if (!st?.available && phase === "idle") return null;
  return (
    <div className="update-banner">
      {phase === "idle" && (
        <>
          ✨ Es gibt eine neue Version der App.
          <button className="btn" onClick={go}>
            Jetzt aktualisieren
          </button>
        </>
      )}
      {phase === "laeuft" && <>⏳ Neue Version wird geladen …</>}
      {phase === "neustart" && <>⏳ Die App startet neu, die Seite lädt gleich von selbst neu …</>}
      {phase === "fehler" && (
        <>
          ⚠ {err}{" "}
          <button className="link" onClick={() => setPhase("idle")}>
            ok
          </button>
        </>
      )}
    </div>
  );
}

function App() {
  const hash = useHash();
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    api.system().then(setSystem).catch(() => setOffline(true));
  }, []);

  const match = hash.match(/^#\/p\/([a-z0-9-]+)/);

  return (
    <>
      <header className="topbar">
        <a href="#/" className="brand">
          <span className="brand-mark">C</span>
          <span>
            <span className="brand-name">Video-Editor</span>
            <span className="brand-sub">für Carina Dorca</span>
          </span>
        </a>
        {system && (
          <div className="sysinfo small" title="Womit dein PC rechnet">
            <span className={`dot ${system.gpu ? "on" : ""}`} />
            Spracherkennung: {system.gpu ? "Grafikkarte" : "Prozessor"} · Video: {system.video_encoder} · frei: {system.disk_free_gb} GB
          </div>
        )}
      </header>
      <UpdateBanner />
      {offline && <div className="banner error page">Keine Verbindung zum Motor. Bitte starte die App mit start.bat.</div>}
      {system && !system.ffmpeg && <div className="banner error page">ffmpeg fehlt. Bitte die App mit start.bat starten, das installiert es.</div>}
      {match ? <ProjectView id={match[1]} /> : <ProjectList system={system} />}
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
