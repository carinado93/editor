import { useEffect, useState } from "react";

/** "1:23.4" oder "83.4" → Sekunden */
export function parseTime(s: string): number | null {
  const t = s.trim().replace(",", ".");
  if (!t) return null;
  const parts = t.split(":").map(Number);
  if (parts.some((x) => Number.isNaN(x))) return null;
  return parts.reduce((acc, x) => acc * 60 + x, 0);
}

export function showTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

function TimeBox({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [txt, setTxt] = useState(showTime(value));
  useEffect(() => setTxt(showTime(value)), [value]);
  return (
    <input
      className="time-box"
      value={txt}
      onChange={(e) => setTxt(e.target.value)}
      onBlur={() => {
        const v = parseTime(txt);
        if (v != null && v >= 0) onChange(Math.round(v * 10) / 10);
        else setTxt(showTime(value));
      }}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
    />
  );
}

/** Von–bis bearbeiten: eintippen (z. B. 1:23.4) oder die aktuelle Videoposition übernehmen. */
export function TimeRange({ start, end, now, onChange, onSeek }: {
  start: number; end: number; now: number;
  onChange: (start: number, end: number) => void; onSeek?: (t: number) => void;
}) {
  const len = Math.max(0.5, end - start);
  return (
    <span className="time-range small">
      <span>from</span>
      <TimeBox value={start} onChange={(v) => onChange(v, v + len)} />
      <button className="link" title="Start at the current video position (keeps the length)" onClick={() => onChange(now, now + len)}>
        ← now
      </button>
      <span>to</span>
      <TimeBox value={end} onChange={(v) => onChange(start, Math.max(start + 0.5, v))} />
      <button className="link" title="End at the current video position" onClick={() => onChange(start, Math.max(start + 0.5, now))}>
        ← now
      </button>
      <span className="muted">({len.toFixed(1)} s)</span>
      {onSeek && <button className="link" onClick={() => onSeek(start)}>▶ jump</button>}
    </span>
  );
}
