import { useEffect, useState } from "react";
import { api, type PlanItem } from "./api";

const TYPE_LABEL: Record<string, string> = { reel: "🎬 Reel", carousel: "🖼 Carousel", youtube: "▶ YouTube", letter: "✉ Letter", story: "◯ Story" };
const STATUS_LABEL: Record<string, string> = { idea: "idea", doing: "in progress", done: "done ✓" };
const DAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function monday(d: Date) {
  const x = new Date(d);
  x.setHours(12, 0, 0, 0);
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return x;
}
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Wochen-Plan: Claude plant die Woche, Ideen aus dem Chat landen hier, "Start" öffnet das passende Werkzeug. */
export function PlanPage() {
  const [items, setItems] = useState<PlanItem[]>([]);
  // ab Freitag wird meist die nächste Woche geplant
  const [week, setWeek] = useState(() => monday(new Date(Date.now() + ([5, 6, 0].includes(new Date().getDay()) ? 3 : 0) * 86400000)));
  const [focus, setFocus] = useState("");
  const [counts, setCounts] = useState({ reel: 3, carousel: 2, youtube: 1, letter: 0, story: 0 });
  const [language, setLanguage] = useState("en");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api.plan().then((r) => setItems(r.items)).catch(() => {});
  }, []);

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
  const upd = (id: string, patch: Partial<PlanItem>) => act("upd", async () => setItems((await api.planUpdate(id, patch)).items));

  const days = Array.from({ length: 7 }, (_, k) => {
    const d = new Date(week);
    d.setDate(d.getDate() + k);
    return iso(d);
  });
  const box = items.filter((it) => !it.date);

  const start = (it: PlanItem) => {
    // passendes Werkzeug öffnen, die Idee ist schon eingetragen
    try { localStorage.setItem("plan-start", JSON.stringify({ title: it.title, idea: it.idea, id: it.id })); } catch { /* egal */ }
    if (it.status === "idea") void api.planUpdate(it.id, { status: "doing" }).then((r) => setItems(r.items));
    if (it.type === "carousel") window.location.hash = "#/karussell";
    else if (it.type === "letter") window.location.hash = "#/briefe";
    else {
      setMsg(it.type === "youtube" || it.type === "reel"
        ? "Film it, then drop the video on the Projects page (YouTube for long videos, “Enhance a reel” for a reel). The idea is copied – paste it as your wish."
        : "The idea is copied.");
      navigator.clipboard.writeText(`${it.title}\n\n${it.idea}`).catch(() => {});
    }
  };

  const card = (it: PlanItem) => (
    <div key={it.id} className={`plan-card ${it.status}`}>
      <div className="plan-card-head">
        <span className="small">{TYPE_LABEL[it.type] ?? it.type}</span>
        <button className="link small" onClick={() => setOpen(open === it.id ? null : it.id)}>{open === it.id ? "close" : "edit"}</button>
      </div>
      <strong className="plan-title">{it.title}</strong>
      {it.account && <span className="muted small">{it.account}</span>}
      {open === it.id ? (
        <div className="plan-edit small">
          <input defaultValue={it.title} onBlur={(e) => e.target.value !== it.title && upd(it.id, { title: e.target.value })} />
          <textarea rows={4} defaultValue={it.idea} onBlur={(e) => e.target.value !== it.idea && upd(it.id, { idea: e.target.value })} />
          <div className="row-buttons">
            <select value={it.type} onChange={(e) => upd(it.id, { type: e.target.value as PlanItem["type"] })}>
              {Object.keys(TYPE_LABEL).map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
            </select>
            <input type="date" value={it.date} onChange={(e) => upd(it.id, { date: e.target.value })} />
            {it.date && <button className="link" onClick={() => upd(it.id, { date: "" })}>→ idea box</button>}
            <button className="link danger" onClick={() => act("del", async () => setItems((await api.planDelete(it.id)).items))}>delete</button>
          </div>
        </div>
      ) : (
        it.idea && <p className="small plan-idea">{it.idea}</p>
      )}
      <div className="row-buttons small">
        <button className="btn small-btn" onClick={() => start(it)}>Start</button>
        <select value={it.status} onChange={(e) => upd(it.id, { status: e.target.value as PlanItem["status"] })}>
          {Object.keys(STATUS_LABEL).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
      </div>
    </div>
  );

  return (
    <div className="page plan-page">
      <section className="card">
        <h2>Plan</h2>
        <p className="small muted">
          Your content week. Let Claude plan it, or collect ideas from “Social Media Content” (button “→ Plan” under each answer).
          “Start” opens the right tool with the idea already filled in.
        </p>
        <div className="plan-gen">
          <label className="small grow">What should this week be about? (optional)
            <input value={focus} placeholder="e.g. Sunday scaries, boundaries at work, my book launch" onChange={(e) => setFocus(e.target.value)} />
          </label>
          {(["reel", "carousel", "youtube", "letter", "story"] as const).map((t) => (
            <label key={t} className="small num">{TYPE_LABEL[t]}
              <input type="number" min={0} max={7} value={counts[t]} onChange={(e) => setCounts({ ...counts, [t]: Number(e.target.value) })} />
            </label>
          ))}
          <label className="small num">Language
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="en">English</option>
              <option value="de">German</option>
            </select>
          </label>
          <button className="btn" disabled={!!busy} onClick={() => act("week", async () => {
            setItems((await api.planWeek("claude", { start: iso(week), focus, counts, language })).items);
            setMsg("Your week is planned ✓ – change, move or delete anything.");
          })}>{busy === "week" ? "Claude is planning … (about 30–60 s)" : "✨ Plan this week"}</button>
        </div>
        {err && <div className="banner error small">{err}</div>}
        {msg && <div className="banner small">{msg}</div>}
      </section>

      <section className="card">
        <div className="plan-week-head">
          <button className="btn ghost small-btn" onClick={() => setWeek(new Date(week.getTime() - 7 * 86400000))}>← previous week</button>
          <strong>Week of {week.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })}</strong>
          <button className="btn ghost small-btn" onClick={() => setWeek(new Date(week.getTime() + 7 * 86400000))}>next week →</button>
          <button className="link" onClick={() => act("add", async () => setItems((await api.planAdd({ date: days[0], type: "reel", title: "New idea", idea: "" })).items))}>+ add an idea</button>
        </div>
        <div className="plan-grid">
          {days.map((d, k) => (
            <div key={d} className={`plan-day ${d === iso(new Date()) ? "today" : ""}`}>
              <div className="plan-day-head small"><strong>{DAY[k]}</strong> {new Date(d + "T12:00").getDate()}.</div>
              {items.filter((it) => it.date === d).map(card)}
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h3>Idea box <span className="muted small">({box.length} without a day – give them a date in “edit”)</span></h3>
        <div className="plan-box">{box.map(card)}</div>
        {!box.length && <p className="small muted">Empty. In “Social Media Content”, press “→ Plan” under an answer with ideas.</p>}
      </section>
    </div>
  );
}
