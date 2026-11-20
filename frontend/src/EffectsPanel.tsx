import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, formatTime, type TranslateRow, type CutView, type EffectType, type FxStyle, type Overlay, type RenderOptions, type SpeedRange } from "./api";
import { Status } from "./ReelPackage";
import { TimeRange } from "./TimeRange";

const GROUP_LABEL: Record<string, string> = {
  A: "Boxes & cards",
  B: "Text over the video",
  C: "You cut out (needs more render time)",
  D: "Tripod tricks (film on a tripod + a few seconds of the empty room)",
  E: "Studio – day in my life (trained with Claude, Nov 2026)",
};

const PLACE_LABEL = { scene: "Full screen", side: "Next to you" };

const HINT: Record<string, string> = {
  steps: "one step per line",
  cards: "one card per line, optional: Title|small line",
  tags: "one tag per line",
  scores: "one per line: Text|score 1-10",
  checklist: "one point per line",
  endcard: "the big call to action, e.g. Comment CALM",
  bigwords: "with speech: key words that turn purple · without speech: your own lines, one per line",
  clothesline: "one card per line, optional: Big word|small line",
  repeat: "the repeating phrase, e.g. & again (empty = '&' + your last word)",
  wordswap: "the changing words, one per line (heavy, slow, uncertain …)",
  switch: "small line in the pill below (optional, your words)",
  stickers: "one sticker per line",
  outro: "optional, one per line: Like | Subscribe | Subscribed (empty = these words)",
  battery: "optional: Label|Line 1|Line 2|Line 3 (empty = brain battery|Low Battery|3% remaining|connect to coffee)",
  codechips: "one code line per line (empty = funny examples)",
  nightfall: "Start|End|line, e.g. 18:00|21:47|wait… it's night?",
  logoff: "optional, e.g. logging off",
  sportpill: "SPORT|time, e.g. ZUMBA|30 min",
  ringtimer: "Text|minutes, e.g. meditation time|30 – or count up: Text|from|to, e.g. Gedanken|1|190000",
  circleword: "the word that circles, e.g. Gedanken",
  loop: "one step per line (3–6), e.g. Gedanken benennen / Beweise prüfen / …",
  countup: "Text|from|to, e.g. Gedanken =|1|190000",
  savedcard: "Title|Button, e.g. WORKOUT SAVED|RESUME: WORK · lines: Label|value",
  subscribe: "3 lines with |, e.g. any support in the form of|a subscribe or like|would be highly appreciated",
  heartcover: "LEFT|RIGHT word, e.g. THANK|YOU",
  sharestats: "the call to action · lines: Label|value (e.g. Work|11h 00m), optional last line name|CARINA",
};

/** Effekte, die an Carina hängen (oder das ganze Bild füllen) – dort gibt es keine freie Position. */
const NO_POSITION = ["behind", "glow", "background", "poof", "lighttrail", "vanish", "flash", "sticker", "counter",
  "ghost", "whip", "switch", "statement", "card", "endcard",
  // Studio-Effekte, die das ganze Bild verändern
  "nightfall", "savedcard", "subscribe", "heartcover", "sharestats"];

/** Ein Satz pro Effekt: was er macht (unter der Auswahl beim Hinzufügen). */
const DESC: Record<string, string> = {
  steps: "Boxes for each step appear one after another, connected by a line.",
  cards: "White cards with your points pop up around the middle.",
  tags: "Small slanted labels fly in, one per point.",
  scores: "Rating cards with a bar, e.g. “Sleep | 6”.",
  headline: "Big headline line by line like a staircase, *word* in gold italic.",
  checklist: "A checklist; each point gets a tick.",
  endcard: "Full purple closing card with a call to action (e.g. Comment CALM).",
  bigwords: "Big captions of what you say, 1–2 words at a time; key words turn purple. Without speech: your own lines, one after another.",
  pill: "A small pill label at the top, e.g. “+ breathing exercise”.",
  behind: "A big word BEHIND you (you are cut out and stand in front of it). Needs you in the video.",
  glow: "A glowing outline around you. Needs you in the video.",
  background: "Swaps the room behind you for a soft lavender pattern, like a green screen. Needs you in the video.",
  card: "Your video shrinks into a rounded card on lavender, with a headline above.",
  poof: "A soft smoke puff – for a cut where something appears or disappears.",
  clothesline: "Cards hanging on a line next to you.",
  lighttrail: "A light that travels around your outline. Needs you in the video.",
  vanish: "You disappear / appear in smoke (film on a tripod + a few seconds of the empty room).",
  flash: "Your poses pop up around the room (tripod).",
  sticker: "Your head as a sticker on a colourful background (bubble head).",
  counter: "A number counts up behind you (e.g. 0 → 120 days).",
  typewriter: "Text appears letter by letter like a typewriter.",
  ghost: "See-through copies of you trail behind your movement – only visible when you move (turn, walk, jump).",
  whip: "A quick zoom-blur transition between two parts.",
  statement: "Full-screen card in soft purple with one short line in capitals.",
  battery: "A tall 'brain battery' drains from 40 % to 3 % (lilac → red), then an iPhone 'Low Battery – connect to coffee' popup. For yawning / tired moments.",
  codechips: "Dark code chips type themselves next to you. For working on the computer.",
  nightfall: "The room gets a night tint, the sun sets, the moon rises and the clock counts up.",
  logoff: "A glitch on the picture, then a lilac 'logging off…' pill. For shutting the computer down.",
  sportpill: "A lilac pill top left with a ticking stopwatch: sport + duration. Put one on each sport scene.",
  ringtimer: "A ring timer counts down (e.g. 30:00 → 00:00) – or a number counts up in the ring (e.g. 1 → 190.000) – while the title writes itself.",
  loop: "Your steps as a cycle: dots in a circle with arrows; the step you talk about lights up and is shown big in the middle. Make it as long as you talk about the steps.",
  circleword: "A word written around a circle that keeps turning – e.g. 'Gedanken' for Gedankenkreisen.",
  countup: "A text with a number that counts up faster and faster, e.g. 'Gedanken = 190.000'.",
  savedcard: "The video dims and a lilac 'WORKOUT SAVED' card pops up with 3 values; a cursor clicks the button. Keep it ≥ 2 s.",
  subscribe: "Lilac fills the screen from the middle (best when something covers the lens), 'a subscribe or like' + buttons get clicked, then the video opens again.",
  heartcover: "THANK / YOU drop in behind you, then a lilac heart grows from your face and covers the whole screen. Needs you in the video.",
  sharestats: "Strava-style ending: background turns dark, you stay cut out, a phone 'Share Activity' shows your day stats, a tap on Story sends the sticker next to you.",
  quote: "A quote in elegant serif over the clip.",
  switch: "Your own headline revealed with a switch effect (your exact text).",
  repeat: "A line that repeats (“& again … & again”).",
  wordswap: "One sentence where the last word keeps changing.",
  label: "A purple box with white capitals – a key message or SEO word.",
  quotepill: "A cream pill with a calm quote, *word* in purple italic.",
  number: "A word with a big number, e.g. “Burnout | ×3”.",
  name: "Your name + title as a lower third.",
  stickers: "Handwritten white notes appear one under the other – one per line.",
  buzzword: "One key word pops up next to your face.",
  outro: "“Thank you for watching” + Like & Subscribe buttons with a mouse click.",
};

/** Studio-Effekte: ein eigenes Feld für jeden Text (gespeichert wie vorher als "a|b|c" bzw. Zeilen "Label|Wert"). */
type StudioSpec = {
  title?: [string, string][];          // [Feldname, Standardtext]
  items?: [string, string][];          // feste Einzelzeilen (z. B. Knopf-Texte)
  rows?: { labels: [string, string]; defaults: [string, string][] };  // Zeilen "Label|Wert", beliebig viele
  name?: [string, string];             // zusätzliche Zeile "name|…" (Statistik-Sticker)
};
const STUDIO_FIELDS: Record<string, StudioSpec> = {
  battery: { title: [["Label", "brain battery"], ["Popup title", "Low Battery"], ["Popup line 2", "3% remaining"], ["Popup line 3", "connect to coffee"]] },
  nightfall: { title: [["Start time", "18:00"], ["End time", "21:47"], ["Sentence", "wait… it's night?"]] },
  logoff: { title: [["Text", "logging off"]] },
  subscribe: { title: [["Line 1", "any support in the form of"], ["Line 2", "a subscribe or like"], ["Line 3", "would be highly appreciated"]],
    items: [["Button", "SUBSCRIBE"], ["Button after the click", "SUBSCRIBED"]] },
  heartcover: { title: [["Left word", "THANK"], ["Right word", "YOU"]] },
  savedcard: { title: [["Heading", "WORKOUT SAVED"], ["Button", "RESUME: WORK"]],
    rows: { labels: ["Label", "Value"], defaults: [["Time", "2h 00m"], ["Activities", "3"], ["Mood", "reset"]] } },
  circleword: { title: [["Word that circles", "Gedanken"], ["Text in the middle (optional)", ""]] },
  countup: { title: [["Text", "Gedanken ="], ["From", "1"], ["To", "190000"]] },
  sharestats: { title: [["Call to action", "give kudos & follow for part 2"]],
    rows: { labels: ["Activity", "Time"], defaults: [["Work", "11h 00m"], ["Sports", "2h 00m"], ["Meditation", "30m"]] },
    name: ["Name on the sticker", "CARINA"] },
};

function StudioFields({ o, spec, onChange }: { o: Overlay; spec: StudioSpec; onChange: (p: Partial<Overlay>) => void }) {
  const parts = (o.title ?? "").split("|");
  const setPart = (k: number, v: string) => {
    const n = spec.title?.length ?? 0;
    const next = Array.from({ length: n }, (_, j) => (j === k ? v : parts[j] ?? ""));
    const t = next.join("|").replace(/\|+$/, "");
    onChange({ title: t, text: t || o.type || "fx" });
  };
  const items = o.items ?? [];
  const nameLine = spec.name ? items.find((x) => x.toLowerCase().startsWith("name|")) : undefined;
  const plain = spec.name ? items.filter((x) => !x.toLowerCase().startsWith("name|")) : items;
  const rows: [string, string][] = spec.rows
    ? (plain.length ? plain.map((x) => [(x.split("|")[0] ?? ""), (x.split("|")[1] ?? "")] as [string, string]) : spec.rows.defaults.map((d) => [...d] as [string, string]))
    : [];
  const saveRows = (rs: [string, string][], nm = nameLine) =>
    onChange({ items: [...rs.map(([a, b]) => `${a}|${b}`), ...(nm ? [nm] : [])] });
  return (
    <div className="studio-fields small">
      {spec.title?.map(([label, def], k) => (
        <label key={label}>{label}
          <input value={parts[k] ?? ""} placeholder={def} onChange={(e) => setPart(k, e.target.value)} />
        </label>
      ))}
      {spec.items?.map(([label, def], k) => (
        <label key={label}>{label}
          <input value={items[k] ?? ""} placeholder={def}
            onChange={(e) => onChange({ items: spec.items!.map((_, j) => (j === k ? e.target.value : items[j] ?? "")) })} />
        </label>
      ))}
      {spec.rows && (
        <div className="studio-rows">
          <span className="muted">{spec.rows.labels[0]} · {spec.rows.labels[1]}</span>
          {rows.map(([a, b], k) => (
            <div key={k} className="studio-row">
              <input value={a} placeholder={spec.rows!.labels[0]} onChange={(e) => saveRows(rows.map((r, j) => (j === k ? [e.target.value, r[1]] : r)))} />
              <input value={b} placeholder={spec.rows!.labels[1]} onChange={(e) => saveRows(rows.map((r, j) => (j === k ? [r[0], e.target.value] : r)))} />
              <button className="link danger" disabled={rows.length <= 1} onClick={() => saveRows(rows.filter((_, j) => j !== k))}>✕</button>
            </div>
          ))}
          {rows.length < 5 && <button className="link" onClick={() => saveRows([...rows, ["", ""]])}>+ add a line</button>}
        </div>
      )}
      {spec.name && (
        <label>{spec.name[0]}
          <input value={nameLine ? nameLine.split("|")[1] ?? "" : ""} placeholder={spec.name[1]}
            onChange={(e) => saveRows(rows, e.target.value ? `name|${e.target.value}` : undefined)} />
        </label>
      )}
    </div>
  );
}

/** Vorschau-Bild, das sich bei jeder Änderung selbst neu zeichnet (kurz warten, dann neu laden). */
type PreviewFn = (item: Overlay, signal: AbortSignal) => Promise<string>;

function FxPreview({ preview, item }: { preview: PreviewFn; item: Overlay }) {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const last = useRef<string | null>(null);
  const key = JSON.stringify([item.type, item.place, item.title, item.items, item.start, item.end, item.scale, item.pos_x, item.pos_y, item.nudge_x, item.nudge_y, item.color, item.item_t]);
  useEffect(() => {
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      setFailed(false);
      try {
        const url = await preview(item, ctrl.signal);
        if (last.current) URL.revokeObjectURL(last.current);
        last.current = url;
        setSrc(url);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setFailed(true);
      } finally {
        setLoading(false);
      }
    }, 900);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return (
    <div className="fx-preview-box">
      {src && <video className={`fx-preview ${loading ? "loading" : ""}`} src={src} autoPlay loop muted playsInline />}
      {!src && <div className="fx-preview placeholder small muted">{failed ? "No preview" : "Building preview video …"}</div>}
      {src && loading && <span className="fx-preview-busy small">updating …</span>}
    </div>
  );
}

const SPEED_LABEL: Record<number, string> = { 0.25: "¼× slow", 0.5: "½× slow", 2: "2× fast", 4: "4× fast", 8: "8× fast" };

/** Frühere Stände der Effekte wiederherstellen (z. B. wenn Claude etwas überschrieben hat). */
function FxVersions({ id, onCuts }: { id: string; onCuts: (c: CutView) => void }) {
  const [open, setOpen] = useState(false);
  const [list, setList] = useState<Awaited<ReturnType<typeof api.fxVersions>>["versions"] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = () => api.fxVersions(id).then((r) => setList(r.versions)).catch((e) => setErr(e.message));
  return (
    <div className="fx-versions small">
      <button className="link" onClick={() => { setOpen(!open); if (!open) void load(); }}>🕘 Earlier versions (restore)</button>
      {open && (
        <div className="fx-versions-list">
          {err && <div className="banner error">{err}</div>}
          {list && !list.length && <p className="muted">No earlier versions saved yet.</p>}
          {list?.map((v, k) => (
            <div key={k} className="fx-version">
              <div>
                <strong>{v.ts ? new Date(v.ts * 1000).toLocaleString() : "earlier"}</strong> · {v.label} · {v.count} items ({v.fx} effects)
                <ul>{v.summary.map((x, j) => <li key={j}>{x}</li>)}</ul>
              </div>
              <button className="btn small-btn" onClick={async () => {
                if (!confirm("Restore this version? Your current effects are saved as a version first, so you can go back.")) return;
                try { onCuts(await api.fxRestore(id, k)); setOpen(false); } catch (e) { setErr((e as Error).message); }
              }}>↺ restore</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Große Effekte im ganzen Video (YouTube / Reel veredeln) plus Zeitraffer/Zeitlupe. */
export function EffectsPanel({ id, cuts, onCuts, time, outTime, toSrc, toOut, onSeek, keep }: {
  id: string; cuts: CutView; onCuts: (c: CutView) => void; time: number; outTime?: number | null; onSeek: (t: number) => void;
  toSrc?: (t: number) => number; toOut?: (t: number) => number;
  keep?: [number, number][];
}) {
  const [busy, setBusy] = useState(false);
  const fxItems = (cuts.cutlist.overlays ?? []).filter((o) => o.kind === "fx");
  const speed = cuts.cutlist.speed ?? [];
  const removeSpeed = async (r: SpeedRange) => {
    setBusy(true);
    try {
      onCuts(await api.setSpeed(id, speed.filter((x) => x !== r)));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="card fx-card" id="step-effects">
      <h3>Effects</h3>
      <FxVersions id={id} onCuts={onCuts} />
      <EffectsEditor
        renderOptions={cuts.cutlist.render_options as unknown as Record<string, unknown>}
        onRenderOptions={async (r) => onCuts(await api.renderOptions(id, r as Partial<RenderOptions>))}
        keep={keep}
        endAt={keep?.length ? keep[keep.length - 1][1] : cuts.evaluation.old_duration}
        items={fxItems}
        allowedInit={cuts.cutlist.fx_allowed}
        time={time}
        outTime={outTime}
        toSrc={toSrc}
        toOut={toOut}
        onSeek={onSeek}
        preview={(item, signal) => api.effectPreviewLive(id, item, signal)}
        onSave={async (list) => {
          const others = (cuts.cutlist.overlays ?? []).filter((o) => o.kind !== "fx");
          onCuts(await api.setOverlays(id, [...others, ...list]));
        }}
        onSuggest={async (engine, allowed, wish) => {
          const v = await api.suggestEffects(id, engine, allowed, wish);
          onCuts(v);
          return (v.cutlist.overlays ?? []).filter((o) => o.kind === "fx").length;
        }}
      >
        <h4 style={{ marginTop: 20 }}>Fast & slow motion</h4>
        <p className="small muted">
          In the transcript, select the words (click, Shift+click) and choose a speed in the bar that appears. Time-lapse
          is muted, slow motion keeps your voice.
        </p>
        {!speed.length && <p className="small muted">No speed changes yet.</p>}
        {speed.map((r, k) => (
          <div key={k} className="small fx-speed">
            <button className="time" onClick={() => onSeek(r.start)}>{formatTime(r.start)}</button>
            – {formatTime(r.end)} · <strong>{SPEED_LABEL[r.factor] ?? `${r.factor}×`}</strong>
            {r.mute ? " · muted" : ""}{" "}
            <button className="link danger" disabled={busy} onClick={() => removeSpeed(r)}>remove</button>
          </div>
        ))}
      </EffectsEditor>
      <LanguageVersion id={id} cuts={cuts} onCuts={onCuts} />
    </section>
  );
}

/** Sprachversion: alle Bildschirm-Texte übersetzen – erst Tabelle prüfen, dann übernehmen (Original bleibt gespeichert). */
function LanguageVersion({ id, cuts, onCuts }: { id: string; cuts: CutView; onCuts: (c: CutView) => void }) {
  const [lang, setLang] = useState("de");
  const [rows, setRows] = useState<TranslateRow[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const current = cuts.cutlist.text_language;
  const run = async (engine: "claude" | "ollama") => {
    setErr(null);
    setBusy(engine === "claude" ? "Claude is translating … (about 20–60 s)" : "Local AI is translating …");
    try {
      setRows((await api.translatePropose(id, engine, lang)).rows);
    } catch (e) {
      setErr(String((e as Error).message ?? e));
    } finally {
      setBusy(null);
    }
  };
  return (
    <div className="fx-tool" style={{ marginTop: 20 }}>
      <h4>Language version</h4>
      <p className="small muted">
        All on-screen texts in another language – same effects, same timing. You check every line first; your
        original texts stay saved.{current ? ` Texts are now in ${current === "de" ? "German" : "English"}.` : ""}
      </p>
      <div className="fx-add-row">
        <select value={lang} onChange={(e) => setLang(e.target.value)}>
          <option value="de">German</option>
          <option value="en">English</option>
        </select>
        <button className="btn" disabled={!!busy} onClick={() => run("claude")}>{busy ?? "Translate with Claude"}</button>
        <button className="btn ghost" disabled={!!busy} onClick={() => run("ollama")}>Free with Ollama</button>
        {current && (
          <button className="btn ghost" disabled={!!busy} onClick={async () => onCuts(await api.translateRestore(id))}>
            Back to original texts
          </button>
        )}
      </div>
      {err && <p className="small danger">{err}</p>}
      {rows && (
        <div className="small" style={{ marginTop: 10 }}>
          {rows.map((r, k) => (
            <div key={r.key} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 6 }}>
              <span className="muted">{r.src}</span>
              <input value={r.dst} onChange={(e) => setRows(rows.map((x, j) => (j === k ? { ...x, dst: e.target.value } : x)))} />
            </div>
          ))}
          <button className="btn" onClick={async () => { onCuts(await api.translateApply(id, lang, rows)); setRows(null); }}>
            ✓ Use these texts
          </button>{" "}
          <button className="btn ghost" onClick={() => setRows(null)}>Cancel</button>
        </div>
      )}
    </div>
  );
}

/** Die Effekt-Liste selbst (für das ganze Video und für jedes Reel). Du wählst, Claude schlägt vor. */
/** Zeit im Original ↔ Zeit im geschnittenen Video (so wie der Player mit "Play preview with cuts" zählt). */
function toCut(keep: [number, number][] | undefined, t: number): number {
  if (!keep?.length) return t;
  let acc = 0;
  for (const [a, b] of keep) {
    if (t >= b) acc += b - a;
    else {
      if (t > a) acc += t - a;
      break;
    }
  }
  return acc;
}
function toOrig(keep: [number, number][] | undefined, n: number): number {
  if (!keep?.length) return n;
  let acc = 0;
  for (const [a, b] of keep) {
    if (n <= acc + (b - a)) return a + Math.max(0, n - acc);
    acc += b - a;
  }
  return keep[keep.length - 1][1];
}
function inCutPart(keep: [number, number][] | undefined, t: number): boolean {
  return !!keep?.length && !keep.some(([a, b]) => t >= a - 0.05 && t <= b + 0.05);
}

export function EffectsEditor({ items: source, allowedInit, time, outTime, toSrc, toOut, onSeek, preview, onSave, onSuggest, children, compact, exclude, keep, endAt, renderOptions, onRenderOptions }: {
  items: Overlay[];
  allowedInit?: string[];
  time: number;
  outTime?: number | null;
  toSrc?: (t: number) => number;
  toOut?: (t: number) => number;
  onSeek: (t: number) => void;
  preview: PreviewFn;
  onSave: (list: Overlay[]) => Promise<void>;
  onSuggest: (engine: "claude" | "ollama", allowed: string[], wish: string) => Promise<number>;
  children?: ReactNode;
  compact?: boolean;
  exclude?: string[];
  keep?: [number, number][];
  /** Ende des Videos (Original-Zeit) – für "Like & Subscribe am Ende" */
  endAt?: number;
  /** Render-Einstellungen des Projekts (nur beim ganzen Video, nicht bei Reels) – für gespeicherte Stile */
  renderOptions?: Record<string, unknown>;
  onRenderOptions?: (r: FxStyle["render"]) => Promise<void>;
}) {
  const [types, setTypes] = useState<EffectType[]>([]);
  const [allowed, setAllowed] = useState<string[]>(allowedInit ?? []);
  const [items, setItems] = useState<Overlay[]>(source);
  const [dirty, setDirty] = useState(false);
  const [addType, setAddType] = useState("headline");
  const [addText, setAddText] = useState("");
  const [wish, setWish] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api.effectTypes().then((r) => {
      r.types = r.types.filter((t) => !(exclude ?? []).includes(t.key))
        .sort((x, y) => x.label.localeCompare(y.label, "en", { sensitivity: "base" }));  // A–Z in allen Listen
      setTypes(r.types);
      setAllowed((a) => (a.length ? a : r.types.filter((t) => t.group !== "C" && t.group !== "E").map((t) => t.key)));
    }).catch(() => {});
  }, []);
  // ---------- gespeicherte Stile ----------
  const [styles, setStyles] = useState<FxStyle[]>([]);
  const [styleId, setStyleId] = useState<string>(() => {
    try { return localStorage.getItem("fx-style") ?? ""; } catch { return ""; }
  });
  const sizesAfterSuggest = useRef<Record<string, number> | null>(null);
  useEffect(() => {
    api.styles().then((r) => setStyles(r.styles)).catch(() => {});
  }, []);
  const withSizes = (list: Overlay[], sizes: Record<string, number>) =>
    list.map((o) => (o.type && sizes[o.type] ? { ...o, scale: sizes[o.type] } : o));

  useEffect(() => {
    if (sizesAfterSuggest.current) {  // neue Vorschläge von Claude gleich in den Größen des Stils
      const sz = sizesAfterSuggest.current;
      sizesAfterSuggest.current = null;
      const list = withSizes(source, sz);
      setItems(list);
      if (JSON.stringify(list) !== JSON.stringify(source)) void onSave(list);
      return;
    }
    if (!dirty) setItems(source);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(source)]);

  const act = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setErr(null);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const save = (list = items) =>
    act("save", async () => {
      await onSave(list);
      setDirty(false);
      setMsg("Saved ✓ – the effects are built in when you render.");
    });

  const suggest = (engine: "claude" | "ollama") =>
    act(engine, async () => {
      const st = styles.find((x) => x.id === styleId);
      if (st && Object.keys(st.sizes).length) sizesAfterSuggest.current = st.sizes;
      const n = await onSuggest(engine, allowed, wish);
      setDirty(false);
      setMsg(`${n} effects suggested ✓ – check them below, change the type or remove what doesn't fit.`);
    });

  const upd = (i: number, patch: Partial<Overlay>) => {
    setDirty(true);
    setItems(items.map((o, j) => (j === i ? { ...o, ...patch } : o)));
  };

  const LIST_TYPES = ["steps", "cards", "tags", "scores", "checklist", "endcard", "bigwords", "clothesline", "wordswap", "stickers", "loop"];
  const add = () => {
    const t = types.find((x) => x.key === addType);
    const dur = addType === "poof" ? 1 : addType === "whip" ? 0.6 : addType === "loop" ? 40 : 4;
    const start = Math.max(0, addType === "poof" ? time - 0.25 : addType === "whip" ? time - 0.3 : time);
    // Dein Text macht den Effekt: bei Listen eine Zeile pro Punkt, sonst wird er zur Überschrift
    const lines = addText.split("\n").map((x) => x.trim()).filter(Boolean);
    const isList = LIST_TYPES.includes(addType);
    const title = isList ? "" : lines.join("|");
    setDirty(true);
    setItems([...items, {
      id: `fx-${Date.now()}`, kind: "fx", type: addType, place: t?.places[0] ?? "scene", on: true,
      title, text: title || addType, items: isList ? lines : [], item_t: [], start, end: start + dur,
      bg_t: null, pose_t: [], mode: "vanish" as const,
    }].sort((a, b) => a.start - b.start));
    setAddText("");
  };

  // Schluss: "Thank you for watching" + Like & Subscribe in den letzten 6 Sekunden (des geschnittenen Videos)
  const addOutro = () => {
    if (endAt == null) return;
    const endCut = toCut(keep, endAt);
    const start = Math.round(toOrig(keep, Math.max(0, endCut - 6)) * 100) / 100;
    const nid = `fx-${Date.now()}`;
    const list = [...items.filter((o) => o.type !== "outro"), {
      id: nid, kind: "fx", type: "outro", place: "side" as const, on: true,
      title: "Thank you for watching", text: "Thank you for watching", items: [], item_t: [],
      start, end: Math.round((start + 6) * 100) / 100, bg_t: null, pose_t: [], mode: "vanish" as const,
    }].sort((a, b) => a.start - b.start);
    setItems(list);
    setDirty(true);
    onSeek(start);
    // gleich speichern und zum neuen Effekt springen, damit man ihn sieht
    void act("save", async () => {
      await onSave(list);
      setDirty(false);
      setMsg("Like & Subscribe added at the end and saved ✓ – it's shown below (last effect in the list).");
    });
    setTimeout(() => document.getElementById(nid)?.scrollIntoView({ behavior: "smooth", block: "center" }), 300);
  };


  const applyStyle = (st: FxStyle) =>
    act("style", async () => {
      if (st.allowed.length) setAllowed(st.allowed.filter((k) => types.some((t) => t.key === k)));
      setWish(st.wish);
      let list = withSizes(items, st.sizes);
      if (st.outro && endAt != null && !list.some((o) => o.type === "outro")) {
        const endCut = toCut(keep, endAt);
        const start = Math.round(toOrig(keep, Math.max(0, endCut - 6)) * 100) / 100;
        list = [...list, {
          id: `fx-${Date.now()}`, kind: "fx", type: "outro", place: "side" as const, on: true,
          title: "Thank you for watching", text: "Thank you for watching", items: [], item_t: [],
          start, end: Math.round((start + 6) * 100) / 100, bg_t: null, pose_t: [], mode: "vanish" as const,
        }].sort((a, b) => a.start - b.start);
      }
      setItems(list);
      await onSave(list);
      setDirty(false);
      if (onRenderOptions && Object.keys(st.render).length) await onRenderOptions(st.render);
      setStyleId(st.id);
      try { localStorage.setItem("fx-style", st.id); } catch { /* egal */ }
      setMsg(`Style “${st.name}” applied ✓ – effect choice, wish, sizes${st.outro ? ", outro" : ""}${onRenderOptions && Object.keys(st.render).length ? " and render settings" : ""}. Now let Claude suggest, or add effects yourself.`);
    });

  const saveStyle = () => {
    const name = prompt("Name for this style (e.g. “My YouTube style”). The same name overwrites an existing style.",
      styles.find((x) => x.id === styleId)?.name ?? "");
    if (!name?.trim()) return;
    // Größe pro Effekt-Typ: wie Carina sie in diesem Video eingestellt hat (Durchschnitt)
    const acc: Record<string, number[]> = {};
    items.forEach((o) => { if (o.type && o.scale && o.scale !== 1) (acc[o.type] ??= []).push(o.scale); });
    const sizes = Object.fromEntries(Object.entries(acc).map(([k, v]) => [k, Math.round((v.reduce((a, b) => a + b, 0) / v.length) * 100) / 100]));
    const render: FxStyle["render"] = {};
    if (renderOptions) {
      for (const k of ["zoom", "loudness", "denoise", "declick", "karaoke"] as const) if (k in renderOptions) render[k] = !!renderOptions[k];
      if (typeof renderOptions.subtitles === "string") render.subtitles = renderOptions.subtitles;
    }
    act("style", async () => {
      const r = await api.styleSave({ name: name.trim(), allowed, wish, sizes, outro: items.some((o) => o.type === "outro"), render });
      setStyles(r.styles);
      const st = r.styles.find((x) => x.name.toLowerCase() === name.trim().toLowerCase());
      if (st) {
        setStyleId(st.id);
        try { localStorage.setItem("fx-style", st.id); } catch { /* egal */ }
      }
      setMsg(`Style “${name.trim()}” saved ✓ – use it on your next video with one click.`);
    });
  };

  const groups = ["A", "B", "C", "D", "E"];
  const typeOf = (k?: string) => types.find((t) => t.key === k);

  return (
    <div className={compact ? "fx-editor compact" : "fx-editor"}>
      <p className="small muted">
        Big effects in your purple, sage and gold. Let Claude suggest moments, or add one yourself at the current
        video position. Every effect below can be changed: type, text, times and size.
      </p>

      <div className="fx-style-row small">
        <strong>Style</strong>
        <select value={styleId} onChange={(e) => setStyleId(e.target.value)}>
          <option value="">– choose a saved style –</option>
          {styles.map((st) => <option key={st.id} value={st.id}>{st.name}</option>)}
        </select>
        <button className="btn small-btn" disabled={!!busy || !styleId} onClick={() => {
          const st = styles.find((x) => x.id === styleId);
          if (st) applyStyle(st);
        }}>Apply</button>
        <button className="btn ghost small-btn" disabled={!!busy} onClick={saveStyle}
          title="Saves the ticked effects, your wish, the sizes you set, the outro and (for the whole video) the render settings">
          Save current as style
        </button>
        {styleId && (
          <button className="link danger" onClick={() => {
            const st = styles.find((x) => x.id === styleId);
            if (st && confirm(`Delete the style “${st.name}”?`)) act("style", async () => { setStyles((await api.styleDelete(st.id)).styles); setStyleId(""); });
          }}>delete style</button>
        )}
      </div>

      <div className="fx-tool">
        <div className="fx-tool-title">✨ Let Claude suggest</div>
        <textarea rows={2} value={wish} placeholder={'Wish (optional), e.g. "a checklist when I list the limits of a coach, BURNOUT behind me at the start"'}
          onChange={(e) => setWish(e.target.value)} />
        <div className="row-buttons">
          <button className="btn" disabled={!!busy || !allowed.length} onClick={() => suggest("claude")}>
            {busy === "claude" ? "Claude is planning … (about 30–90 s)" : "Suggest with Claude"}
          </button>
          <button className="btn ghost" disabled={!!busy || !allowed.length} onClick={() => suggest("ollama")}>
            {busy === "ollama" ? "Local AI is planning … (several minutes)" : "Free with Ollama"}
          </button>
        </div>
        <details className="fx-palette-box small">
          <summary>Which effects Claude may use ({allowed.length} of {types.length} ticked)</summary>
          <div className="fx-palette">
            {groups.map((g) => (
              <div key={g} className="fx-group">
                <strong className="small">{GROUP_LABEL[g]}</strong>
                <div className="fx-chips">
                  {types.filter((t) => t.group === g).map((t) => (
                    <label key={t.key} className={`fx-chip ${allowed.includes(t.key) ? "on" : ""}`}>
                      <input
                        type="checkbox"
                        checked={allowed.includes(t.key)}
                        onChange={(e) => setAllowed(e.target.checked ? [...allowed, t.key] : allowed.filter((x) => x !== t.key))}
                      />
                      {t.label}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </details>
      </div>

      <div className="fx-tool">
        <div className="fx-tool-title">＋ Add an effect yourself <span className="muted small">
          {outTime != null
            ? <>at {formatTime(outTime)} in your finished video (= {formatTime(time)} in the original)</>
            : <>at {formatTime(time)} (pause the video – or your finished video – where it should start)</>}</span></div>
        <div className="fx-add-row">
          <select value={addType} onChange={(e) => setAddType(e.target.value)}>
            {types.map((t) => (
              <option key={t.key} value={t.key}>{t.label}</option>
            ))}
          </select>
          <textarea className="fx-add-text" rows={1} value={addText}
            placeholder={HINT[addType] ? `Your text (optional) – ${HINT[addType]}` : "Your text (optional)"}
            onChange={(e) => setAddText(e.target.value)} />
          <button className="btn" onClick={add}>+ Add at {formatTime(outTime ?? time)}{outTime != null ? " (finished video)" : ""}</button>
        </div>
        {DESC[addType] && <div className="small muted fx-desc">ⓘ {DESC[addType]}</div>}
        {endAt != null && (
          <button className="btn ghost" onClick={addOutro} title="'Thank you for watching' + Like & Subscribe buttons in the last 6 seconds">
            + Like &amp; Subscribe at the end
          </button>
        )}
      </div>

      <div className="fx-save-row">
        <strong>{items.length ? `${items.length} effect${items.length > 1 ? "s" : ""}` : "No effects yet"}</strong>
        <button className={`btn ${dirty ? "" : "ghost"}`} disabled={!!busy || !dirty} onClick={() => save()}
          title={dirty ? "" : "Everything is saved"}>
          {dirty ? "Save effects" : "Saved ✓"}
        </button>
      </div>
      <Status busy={busy} err={err} msg={msg} />
      {err?.includes("Settings") && <a className="small" href="#/einstellungen">→ go to Settings</a>}

      <div className="fx-list">
        {items.map((o, i) => {
          const t = typeOf(o.type);
          const listType = ["steps", "cards", "tags", "scores", "checklist", "endcard", "bigwords", "clothesline", "repeat", "wordswap", "switch", "stickers", "loop"].includes(o.type ?? "");
          return (
            <div key={o.id} id={o.id} className={`fx-row ${o.on ? "" : "off"}`}>
              <FxPreview preview={preview} item={o} />
              <div className="fx-row-main">
              <div className="fx-row-head">
                <input type="checkbox" checked={o.on} onChange={(e) => upd(i, { on: e.target.checked })} />
                <select value={o.type} onChange={(e) => {
                  const nt = typeOf(e.target.value);
                  upd(i, { type: e.target.value, place: nt && !nt.places.includes(o.place ?? "scene") ? nt.places[0] : o.place });
                }}>
                  {types.map((x) => (
                    <option key={x.key} value={x.key}>{x.label}</option>
                  ))}
                </select>
                {t && t.places.length > 1 && (
                  <select value={o.place} onChange={(e) => upd(i, { place: e.target.value as "scene" | "side" })}>
                    {t.places.map((p) => (
                      <option key={p} value={p}>{PLACE_LABEL[p]}</option>
                    ))}
                  </select>
                )}
                <TimeRange start={toCut(keep, o.start)} end={toCut(keep, o.start) + (o.end - o.start)} now={toCut(keep, time)}
                  onSeek={() => onSeek(o.start)}
                  onChange={(st, en) => {
                    // eingegeben wird in der Zeit des geschnittenen Videos, gespeichert in Original-Zeit
                    const so = Math.round(toOrig(keep, st) * 100) / 100;
                    const d = so - o.start;  // Listenpunkte wandern mit
                    upd(i, { start: so, end: Math.round((so + (en - st)) * 100) / 100,
                             item_t: (o.item_t ?? []).map((x) => Math.round((x + d) * 10) / 10) });
                  }} />
                {inCutPart(keep, o.start) && <span className="small error-text">starts in a cut part – shown at the next kept spot</span>}
                <button className="link danger" onClick={() => { setDirty(true); setItems(items.filter((_, j) => j !== i)); }}>
                  remove
                </button>
              </div>
              {DESC[o.type ?? ""] && <div className="small muted fx-desc">ⓘ {DESC[o.type ?? ""]}</div>}
              {STUDIO_FIELDS[o.type ?? ""] && <StudioFields o={o} spec={STUDIO_FIELDS[o.type ?? ""]} onChange={(p) => upd(i, p)} />}
              {o.type === "loop" && (o.items ?? []).length > 0 && (() => {
                const n = (o.items ?? []).length;
                const cur = (o.item_t ?? []).length === n ? [...(o.item_t ?? [])]
                  : Array.from({ length: n }, (_, j) => Math.round((o.start + 0.6 + j * Math.max(0.5, (o.end - o.start - 0.6) / n)) * 10) / 10);
                const out = (t: number) => (toOut ? toOut(t) : t);
                const src = (t: number) => (toSrc ? toSrc(t) : t);
                const setAt = (k: number, srcT: number) => { const nx = [...cur]; nx[k] = Math.round(srcT * 10) / 10; upd(i, { item_t: nx }); };
                return (
                  <div className="fx-loop-times small">
                    <span className="muted">When does each step light up? Time {toOut ? "in your finished video" : ""} (m:ss):</span>
                    {(o.items ?? []).map((st, k) => (
                      <div key={k} className="fx-loop-time">
                        <span>{k + 1}. {st.slice(0, 32)}</span>
                        <input key={`${k}-${cur[k]}`} defaultValue={formatTime(out(cur[k]))} placeholder="2:31"
                          onBlur={(e) => {
                            const p2 = e.target.value.trim().split(":").map(Number);
                            const sec = p2.length === 2 ? p2[0] * 60 + p2[1] : p2[0];
                            if (!Number.isNaN(sec)) setAt(k, src(sec));
                          }} />
                        <button className="link" onClick={() => setAt(k, time)}>← now ({formatTime(outTime ?? out(time))})</button>
                        {(o.item_t ?? []).length !== n && <span className="muted">auto</span>}
                      </div>
                    ))}
                  </div>
                );
              })()}
              {o.type === "ringtimer" && (() => {
                const [nm, tm = "", upto = ""] = (o.title ?? "").split("|");
                const up = upto.trim() !== "";
                const mins = (tm.match(/\d+([.,]\d+)?/) ?? [""])[0];
                const setT = (n: string, m: string, u2?: string) =>
                  upd(i, { title: u2 !== undefined && u2 !== "" ? `${n.trim()}|${m || "1"}|${u2}` : `${n.trim()}|${m || "30"}`, text: n || "meditation" });
                return (
                  <div className="fx-sport small">
                    <input className="fx-title" placeholder="Text, e.g. meditation time" value={nm} onChange={(e) => setT(e.target.value, tm, up ? upto : undefined)} />
                    <select value={up ? "up" : "down"} onChange={(e) => (e.target.value === "up" ? setT(nm, "1", "190000") : setT(nm, "30"))}>
                      <option value="down">counts down (minutes)</option><option value="up">counts up (number)</option>
                    </select>
                    {up ? (<>
                      <label>from<input type="number" value={tm} onChange={(e) => setT(nm, e.target.value, upto)} /></label>
                      <label>to<input type="number" value={upto} onChange={(e) => setT(nm, tm, e.target.value)} /></label>
                    </>) : (
                      <label>⏱ Minutes
                        <input type="number" min={1} max={600} value={mins} placeholder="30" onChange={(e) => setT(nm, e.target.value)} />
                      </label>
                    )}
                  </div>
                );
              })()}
              {["behind", "typewriter", "circleword", "countup", "ringtimer"].includes(o.type ?? "") && (
                <span className="fx-colors small">Colour:
                  {([["white", "#fffdf9"], ["pink", "#f096b9"], ["yellow", "#fae28c"], ["lilac", "#c9b3ec"], ["green", "#a0d696"]] as const).map(([c, hex]) => (
                    <button key={c} title={c} className={`fx-color ${(o.color ?? "") === c || (!o.color && c === "white") ? "on" : ""}`}
                      style={{ background: hex }} onClick={() => upd(i, { color: c })} />
                  ))}
                </span>
              )}
              {o.type === "sportpill" && (() => {
                // Sport-Label: Name und Minuten getrennt eingeben (gespeichert als "NAME|30 min")
                const [nm, tm = ""] = (o.title ?? "").split("|");
                const mins = (tm.match(/\d+([.,]\d+)?/) ?? [""])[0];
                const setT = (n: string, m: string) => {
                  const t = `${n.trim()}|${m ? `${m} min` : "30 min"}`;
                  upd(i, { title: t, text: n || "sport" });
                };
                return (
                  <div className="fx-sport small">
                    <input className="fx-title" placeholder="Sport / text, e.g. ZUMBA" value={nm} onChange={(e) => setT(e.target.value, mins)} />
                    <label>⏱ Minutes
                      <input type="number" min={1} max={600} value={mins} placeholder="30" onChange={(e) => setT(nm, e.target.value)} />
                    </label>
                  </div>
                );
              })()}
              {!["poof", "glow", "bigwords", "lighttrail", "ghost", "whip", "vanish", "flash", "sticker", "sportpill", "ringtimer"].includes(o.type ?? "") && !STUDIO_FIELDS[o.type ?? ""] && (
                <input
                  className="fx-title"
                  placeholder={
                    o.type === "headline" || o.type === "card" ? "Headline – lines with | , *word* = gold italic"
                      : o.type === "switch" ? "Big headline in the glowing box (your words)"
                      : o.type === "statement" ? "Your short line, e.g. But you didn't."
                      : o.type === "quote" ? "Your quote, e.g. \u201eIf I could go back …\u201c"
                      : o.type === "repeat" ? "Your sentence, e.g. Don't forget to try again"
                      : o.type === "wordswap" ? "The fixed part, e.g. trust the timing of your life even when it feels"
                      : o.type === "label" ? "Purple label text, e.g. BURNOUT = JUST TIRED?"
                      : o.type === "quotepill" ? "Quote, *word* = purple italic"
                      : o.type === "number" ? "Word|number, e.g. Burnout|×3"
                      : o.type === "name" ? "Name|title, e.g. Carina Dorca|Stress & Burnout Coach"
                      : o.type === "buzzword" ? "The word, e.g. Burnout"
                      : "Title (optional)"}
                  value={o.title ?? ""}
                  onChange={(e) => upd(i, { title: e.target.value, text: e.target.value || o.type || "fx" })}
                />
              )}
              {listType && !STUDIO_FIELDS[o.type ?? ""] && (
                <textarea
                  rows={Math.max(2, (o.items ?? []).length)}
                  placeholder={HINT[o.type ?? ""]}
                  value={(o.items ?? []).join("\n")}
                  onChange={(e) => upd(i, { items: e.target.value.split("\n") })}
                />
              )}
              {o.type === "switch" && (
                <div className="small fx-tripod">
                  <span>
                    Tap moment (switch turns on): <strong>{o.item_t?.length ? formatTime(o.item_t[0]) : "after ~0.8 s"}</strong>{" "}
                    <button className="link" onClick={() => upd(i, { item_t: [time] })}>use current position ({formatTime(time)})</button>
                  </span>
                  <span className="muted">Move the video to the moment you tap the wall, then click the button.</span>
                </div>
              )}
              {(o.type === "vanish" || o.type === "flash") && (
                <div className="small fx-tripod">
                  {o.type === "vanish" && (
                    <select value={o.mode ?? "vanish"} onChange={(e) => upd(i, { mode: e.target.value as "vanish" | "appear" })}>
                      <option value="vanish">Disappear (you → smoke → empty room)</option>
                      <option value="appear">Appear (empty room → smoke → you)</option>
                    </select>
                  )}
                  <span>
                    Empty room: <strong>{o.bg_t != null ? formatTime(o.bg_t) : "not set"}</strong>{" "}
                    <button className="link" onClick={() => upd(i, { bg_t: time })}>use current position ({formatTime(time)})</button>
                    {o.bg_t != null && <> · <button className="link" onClick={() => onSeek(o.bg_t!)}>show</button></>}
                  </span>
                  {o.type === "flash" && (
                    <span>
                      Poses:{" "}
                      {(o.pose_t ?? []).map((pt, k) => (
                        <span key={k} className="pill">
                          <button className="link" onClick={() => onSeek(pt)}>{formatTime(pt)}</button>
                          <button className="link danger" onClick={() => {
                            const pose_t = (o.pose_t ?? []).filter((_, j) => j !== k);
                            upd(i, { pose_t, end: o.start + Math.max(0.9, pose_t.length * 0.45) });
                          }}>×</button>
                        </span>
                      ))}
                      <button className="link" onClick={() => {
                        const pose_t = [...(o.pose_t ?? []), time];
                        upd(i, { pose_t, end: o.start + Math.max(0.9, pose_t.length * 0.45) });
                      }}>+ pose at current position ({formatTime(time)})</button>
                    </span>
                  )}
                  <span className="muted">
                    Move the video to a moment where the room is empty (or where you hold a pose) and click the button.
                  </span>
                </div>
              )}
              <label className="small fx-size">
                Size
                <input type="range" min={0.5} max={2} step={0.1} value={o.scale ?? 1}
                  onChange={(e) => upd(i, { scale: Number(e.target.value) })} />
                <span className="muted">{Math.round((o.scale ?? 1) * 100)} %</span>
                {(o.scale ?? 1) !== 1 && <button className="link" onClick={() => upd(i, { scale: 1 })}>reset</button>}
              </label>
              {!NO_POSITION.includes(o.type ?? "") && (
                <span className="small fx-pos">
                  Position
                  <span className="seg">
                    {(["auto", "left", "center", "right"] as const).map((v) => (
                      <button key={v} className={(o.pos_x ?? "auto") === v ? "on" : ""} onClick={() => upd(i, { pos_x: v })}>
                        {v === "auto" ? "auto" : v === "left" ? "⇤ left" : v === "center" ? "center" : "right ⇥"}
                      </button>
                    ))}
                  </span>
                  <span className="seg">
                    {(["auto", "top", "middle", "bottom"] as const).map((v) => (
                      <button key={v} className={(o.pos_y ?? "auto") === v ? "on" : ""} onClick={() => upd(i, { pos_y: v })}>
                        {v === "auto" ? "auto" : v === "top" ? "↑ top" : v === "middle" ? "middle" : "bottom ↓"}
                      </button>
                    ))}
                  </span>
                  <span className="nudge" title="Move a little with every click (Shift+click = bigger step)">
                    {([["←", -1, 0], ["↑", 0, -1], ["↓", 0, 1], ["→", 1, 0]] as const).map(([lbl, ddx, ddy]) => (
                      <button key={lbl} onClick={(e) => {
                        const step = e.shiftKey ? 0.05 : 0.01;
                        const r = (v: number) => Math.round(Math.max(-1, Math.min(1, v)) * 1000) / 1000;
                        upd(i, { nudge_x: r((o.nudge_x ?? 0) + ddx * step), nudge_y: r((o.nudge_y ?? 0) + ddy * step) });
                      }}>{lbl}</button>
                    ))}
                    {(!!o.nudge_x || !!o.nudge_y) && (
                      <button className="link" onClick={() => upd(i, { nudge_x: 0, nudge_y: 0 })}>reset</button>
                    )}
                  </span>
                </span>
              )}
              {o.why && <div className="small muted">{o.why}</div>}
              </div>
            </div>
          );
        })}
      </div>

      {children}
    </div>
  );
}
