import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";

/* ------------------------------------------------------------------ Tooltips (wie in CapCut)
 * Jedes Element mit title="…" bekommt eine schöne Blase statt des grauen Browser-Hinweises.
 * Schreibweise: "Name – was es tut" → Name fett, Erklärung darunter.
 * Knöpfe, die nur aus einem Symbol bestehen und keinen title haben, bekommen einen Standard-Text. */

const SYMBOL_TIPS: Record<string, string> = {
  "←": "Move left – earlier / to the left",
  "→": "Move right – later / to the right",
  "↑": "Move up",
  "↓": "Move down",
  "✕": "Remove – delete this line",
  "×": "Close",
  "✓": "Done / confirm",
  "▶": "Play",
  "⏸": "Pause",
  "↻": "Refresh – build it again",
  "⇄": "Swap – use another one here",
  "+": "Add",
  "−": "Smaller / less",
  "–": "Smaller / less",
  "⬇": "Download",
  "⬆": "Upload / render",
  "✎": "Edit",
  "🗑": "Delete",
  "⋯": "More options",
  "…": "More options",
  "?": "Help – what is this?",
  "ⓘ": "Info",
};

export function autoTip(el: HTMLElement): string {
  if (!(el instanceof HTMLButtonElement) && !el.classList.contains("chip")) return "";
  const t = (el.textContent ?? "").trim();
  return SYMBOL_TIPS[t] ?? "";
}

export function Tooltips() {
  const [tip, setTip] = useState<{ text: string; x: number; y: number; below: boolean } | null>(null);
  useEffect(() => {
    let cur: HTMLElement | null = null;
    let timer = 0;
    const hide = () => { cur = null; window.clearTimeout(timer); setTip(null); };
    const over = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      const el = target?.closest?.<HTMLElement>("[title],[data-tip],button,.chip") ?? null;
      if (!el) { if (cur) hide(); return; }
      if (el.hasAttribute("title")) {          // Browser-Hinweis abschalten, Text merken
        const t = el.getAttribute("title") ?? "";
        el.removeAttribute("title");
        if (t) el.dataset.tip = t;
      }
      const text = el.dataset.tip || autoTip(el);
      if (!text) { if (cur) hide(); return; }
      if (el === cur) return;
      cur = el;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        if (cur !== el || !el.isConnected) return;
        const r = el.getBoundingClientRect();
        const below = r.top < 90;
        setTip({ text, x: Math.min(window.innerWidth - 150, Math.max(150, r.left + r.width / 2)), y: below ? r.bottom + 8 : r.top - 8, below });
      }, 250);
    };
    const out = (e: MouseEvent) => {
      if (cur && !cur.contains(e.relatedTarget as Node | null)) hide();
    };
    document.addEventListener("mouseover", over);
    document.addEventListener("mouseout", out);
    document.addEventListener("mousedown", hide);
    window.addEventListener("scroll", hide, true);
    return () => {
      document.removeEventListener("mouseover", over);
      document.removeEventListener("mouseout", out);
      document.removeEventListener("mousedown", hide);
      window.removeEventListener("scroll", hide, true);
    };
  }, []);
  if (!tip) return null;
  const [head, ...rest] = tip.text.split(" – ");
  return (
    <div className={`tip-bubble ${tip.below ? "below" : ""}`} style={{ left: tip.x, top: tip.y }} role="tooltip">
      <strong>{head}</strong>
      {rest.length > 0 && <span>{rest.join(" – ")}</span>}
    </div>
  );
}

/* ------------------------------------------------------------------ Auswahl mit Beispiel-Kacheln
 * Statt einer langen Liste: ein Knopf mit kleinem Beispiel; Klick öffnet ein Raster mit
 * Kategorien links, Suche oben und einem Beispiel pro Möglichkeit (wie die CapCut-Raster). */

export type PickOpt = { value: string; label: string; desc?: string; group?: string };

export function ExamplePicker({ value, options, onChange, example, groupLabels, disabled, search = true, tile = "md", tip }: {
  value: string;
  options: PickOpt[];
  onChange: (v: string) => void;
  /** Beispiel für eine Möglichkeit; small = Mini-Bild im Knopf */
  example: (o: PickOpt, small: boolean) => ReactNode;
  groupLabels?: Record<string, string>;
  disabled?: boolean;
  search?: boolean;
  tile?: "sm" | "md" | "lg" | "tall";
  tip?: string;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [grp, setGrp] = useState("");
  const box = useRef<HTMLDivElement>(null);
  const cur = options.find((o) => o.value === value) ?? { value, label: value || "–" };
  const groups = useMemo(() => [...new Set(options.map((o) => o.group).filter(Boolean))] as string[], [options]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  const shown = options.filter((o) =>
    (!grp || o.group === grp) &&
    (!q || `${o.label} ${o.desc ?? ""}`.toLowerCase().includes(q.toLowerCase())));

  return (
    <div className="pick" ref={box}>
      <button type="button" className="pick-btn" disabled={disabled} onClick={() => setOpen(!open)}
        title={tip ?? `${cur.label} – click to see all options with an example`}>
        <span className="pick-mini">{example(cur, true)}</span>
        <span className="pick-label">{cur.label}</span>
        <span className="pick-caret">▾</span>
      </button>
      {open && (
        <div className="pick-pop" onClick={(e) => e.preventDefault() /* steht der Picker in einem <label>, nicht den Knopf auslösen */}>
          {groups.length > 1 && (
            <div className="pick-groups small">
              <button type="button" className={!grp ? "on" : ""} onClick={() => setGrp("")}>All</button>
              {groups.map((g) => (
                <button type="button" key={g} className={grp === g ? "on" : ""} onClick={() => setGrp(g)}>{groupLabels?.[g] ?? g}</button>
              ))}
            </div>
          )}
          <div className="pick-main">
            {search && options.length > 8 && (
              <input className="pick-search" autoFocus placeholder="🔍 Search …" value={q} onChange={(e) => setQ(e.target.value)} />
            )}
            <div className={`pick-grid ${tile}`}>
              {shown.map((o) => (
                <button type="button" key={o.value} className={`pick-tile ${o.value === value ? "on" : ""}`}
                  title={o.desc ? `${o.label} – ${o.desc}` : o.label}
                  onClick={() => { onChange(o.value); setOpen(false); }}>
                  <span className="pick-ex">{example(o, false)}</span>
                  <span className="pick-name">{o.label}</span>
                </button>
              ))}
              {!shown.length && <span className="small muted">Nothing found.</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Beispiele */

/** Schrift mit Beispieltext in genau dieser Schrift */
export function FontExample({ font, text, small }: { font: string; text: string; small?: boolean }) {
  return (
    <span className={`ex-font ${small ? "small" : ""}`} style={{ fontFamily: `"${font}", sans-serif` }}>
      {small ? "Aa" : text}
    </span>
  );
}

/** Titel-Animation (rein / raus) als kleine Endlos-Animation */
export function TextAnimExample({ kind, dir, text = "SRI LANKA", font, small }: {
  kind: string; dir: "in" | "out"; text?: string; font?: string; small?: boolean;
}) {
  const style: CSSProperties = font ? { fontFamily: `"${font}", sans-serif` } : {};
  const t = small ? "Aa" : text;
  if (kind === "letters" && dir === "in") {
    return (
      <span className="ex-anim" style={style}>
        {[...t].map((c, i) => <span key={i} className="ex-letter" style={{ animationDelay: `${i * 0.12}s` }}>{c === " " ? " " : c}</span>)}
      </span>
    );
  }
  return <span className={`ex-anim ex-${dir}-${kind}`} style={style}>{t}</span>;
}

/** Untertitel-Stil als Beispielzeile */
export function CaptionExample({ style, small }: { style: string; small?: boolean }) {
  if (small) return <span className={`ex-cap ex-cap-${style}`}>Aa</span>;
  if (style === "karaoke") {
    return (
      <span className="ex-cap ex-cap-karaoke">
        {"this is how it looks".split(" ").map((w, i) => <span key={i} style={{ animationDelay: `${i * 0.45}s` }}>{w} </span>)}
      </span>
    );
  }
  return <span className={`ex-cap ex-cap-${style}`}>{style === "bold" ? "THIS IS HOW" : "this is how it looks"}</span>;
}

/** Übergang: Bild A → Bild B als kleine Endlos-Animation */
export function TransitionExample({ kind, small }: { kind: string; small?: boolean }) {
  const k = transitionFamily(kind);
  return (
    <span className={`ex-trans ${small ? "small" : ""} ex-t-${k}`}>
      <span className="ex-a">A</span>
      <span className="ex-b">B</span>
    </span>
  );
}

function transitionFamily(kind: string): string {
  const k = kind.toLowerCase();
  const exact: Record<string, string> = {
    cut: "cut", dissolve: "fade", fade: "fade", fade_black: "black", flash: "flash", fade_grays: "grey",
    swipe_left: "left", slide_left: "left", wipe_left: "wipeleft", swipe_right: "right", wipe_right: "wiperight",
    swipe_up: "up", slide_up: "up", swipe_down: "down", zoom_in: "zoom", zoom: "zoom", blur: "blur", whip: "blur",
    circle: "circle", circle_close: "circleclose", open_horizontal: "openh", open_vertical: "openv",
    diagonal: "diag", radial: "radial", pixelize: "pixel", squeeze: "squeeze", distance: "melt", cover: "black",
    smoke: "grey", split: "openv", rope: "left", placed: "fade", iris: "circleclose",
  };
  if (exact[k]) return exact[k];
  if (k.includes("black")) return "black";
  if (k.includes("white") || k.includes("flash") || k.includes("light")) return "flash";
  if (k.includes("zoom")) return "zoom";
  if (k.includes("slide") || k.includes("swipe") || k.includes("push")) return "left";
  if (k.includes("wipe")) return "wipeleft";
  if (k.includes("blur") || k.includes("whip")) return "blur";
  if (k.includes("spin") || k.includes("rot")) return "spin";
  if (k.includes("glitch") || k.includes("pixel")) return "pixel";
  if (k.includes("circle") || k.includes("heart")) return "circle";
  if (k === "none" || k === "" || k.includes("cut")) return "cut";
  return "fade";
}

/** Farb-Look: Bild mit ungefährem Look (CSS-Filter) – das echte Ergebnis rechnet der Motor. */
const LOOK_FILTER: Record<string, string> = {
  none: "none",
  vivid_travel: "saturate(1.45) contrast(1.08)",
  natural_plus: "saturate(1.12) contrast(1.04)",
  tropical_pop: "saturate(1.6) hue-rotate(-8deg) brightness(1.05)",
  golden_hour: "sepia(0.35) saturate(1.3) brightness(1.05)",
  teal_orange: "contrast(1.15) saturate(1.2) hue-rotate(-12deg)",
  epic_mountains: "contrast(1.25) saturate(0.9) brightness(0.95)",
  deep_blue_ocean: "hue-rotate(12deg) saturate(1.35) brightness(0.95)",
  emerald_jungle: "hue-rotate(-20deg) saturate(1.3)",
  moody_dusk: "brightness(0.8) contrast(1.15) saturate(0.85)",
  bw_drama: "grayscale(1) contrast(1.35)",
  vintage_film: "sepia(0.45) contrast(0.92) brightness(1.05) saturate(0.85)",
};

export function LookExample({ look, img, small }: { look: string; img?: string; small?: boolean }) {
  return (
    <span className={`ex-look ${small ? "small" : ""}`}
      style={{ backgroundImage: img ? `url(${img})` : undefined, filter: LOOK_FILTER[look] ?? "none" }} />
  );
}

/** Farbfeld */
export function SwatchExample({ colors, small }: { colors: string[]; small?: boolean }) {
  return (
    <span className={`ex-swatch ${small ? "small" : ""}`}>
      {colors.map((c, i) => <span key={i} style={{ background: c }} />)}
    </span>
  );
}

/** Text-Animation in Reels (Pop, Karte, Wort für Wort …) */
export function OverlayAnimExample({ kind, small }: { kind: string; small?: boolean }) {
  if (kind === "wort" && !small) {
    return (
      <span className="ex-ov ex-ov-wort">
        {"one word at a time".split(" ").map((w, i) => <span key={i} style={{ animationDelay: `${i * 0.35}s` }}>{w} </span>)}
      </span>
    );
  }
  return <span className={`ex-ov ex-ov-${kind}`}>{small ? "Aa" : "Your text"}</span>;
}

/** Effekt-Beispielbild vom Motor (mit Ersatz, falls es keins gibt) */
export function ImageExample({ src, label, small }: { src: string; label: string; small?: boolean }) {
  const [bad, setBad] = useState(false);
  useEffect(() => setBad(false), [src]);
  if (bad) return <span className={`ex-img none ${small ? "mini" : ""} small muted`}>{small ? "✨" : label}</span>;
  return <img className={`ex-img ${small ? "mini" : ""}`} src={src} alt={label} loading="lazy" onError={() => setBad(true)} />;
}
