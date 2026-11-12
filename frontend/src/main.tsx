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
import { ContentChat } from "./ContentChat";
import { CarouselStudio } from "./CarouselStudio";
import { Settings } from "./Settings";

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
          ✨ A new version of the app is available.
          <button className="btn" onClick={go}>
            Update now
          </button>
        </>
      )}
      {phase === "laeuft" && <>⏳ Loading the new version …</>}
      {phase === "neustart" && <>⏳ The app is restarting, the page will reload by itself in a moment …</>}
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
            <span className="brand-sub">for Carina Dorca</span>
          </span>
        </a>
        <nav className="topnav">
          <a href="#/" className={!hash.startsWith("#/content") && !hash.startsWith("#/einstellungen") && !hash.startsWith("#/karussell") ? "on" : ""}>
            Projects
          </a>
          <a href="#/karussell" className={hash.startsWith("#/karussell") ? "on" : ""}>
            Carousel
          </a>
          <a href="#/content" className={hash.startsWith("#/content") ? "on" : ""}>
            Social Media Content
          </a>
          <a href="#/einstellungen" className={hash.startsWith("#/einstellungen") ? "on" : ""}>
            Settings
          </a>
        </nav>
        {system && (
          <div className="sysinfo small" title="What your PC uses">
            <span className={`dot ${system.gpu ? "on" : ""}`} />
            Speech recognition: {system.gpu ? "graphics card" : "processor"} · Video: {system.video_encoder} · free: {system.disk_free_gb} GB
          </div>
        )}
      </header>
      <UpdateBanner />
      {offline && <div className="banner error page">No connection to the engine. Please start the app with start.bat.</div>}
      {system && !system.ffmpeg && <div className="banner error page">ffmpeg is missing. Please start the app with start.bat, it installs it.</div>}
      {hash.startsWith("#/karussell") ? (
        <CarouselStudio />
      ) : hash.startsWith("#/content") ? (
        <ContentChat />
      ) : hash.startsWith("#/einstellungen") ? (
        <Settings />
      ) : match ? (
        <ProjectView id={match[1]} />
      ) : (
        <ProjectList system={system} />
      )}
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
