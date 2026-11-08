import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/cormorant-garamond/600.css";
import "@fontsource/cormorant-garamond/600-italic.css";
import "@fontsource/jost/400.css";
import "@fontsource/jost/500.css";
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
