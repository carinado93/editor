// Verbindung zum Python-Motor.

export type Mode = "youtube" | "reel" | "idee";

export interface VideoInfo {
  duration: number;
  size: number;
  width: number;
  height: number;
  fps: number;
  video_codec: string;
  has_audio: boolean;
}

export interface Project {
  id: string;
  name: string;
  mode: Mode;
  created: number;
  original_name: string;
  size: number;
  uploaded: number;
  status: "hochladen" | "warteschlange" | "arbeitet" | "fertig" | "fehler";
  step: string;
  progress: number;
  message: string;
  error: string | null;
  info: VideoInfo | null;
  settings: { model: string; language: string };
  transcript: { language: string; model: string; device: string; words: number } | null;
}

export interface Word {
  w: string;
  s: number;
  e: number;
  p: number;
}

export interface Segment {
  s: number;
  e: number;
  text: string;
  words: Word[];
}

export interface Transcript {
  language: string;
  model: string;
  device: string;
  duration: number;
  segments: Segment[];
}

export interface SystemInfo {
  ffmpeg: boolean;
  video_encoder: string;
  gpu: boolean;
  default_model: string;
  models: Record<string, string>;
  modes: Record<Mode, string>;
  disk_free_gb: number;
}

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new Error("Keine Verbindung zum Motor. Läuft das schwarze Fenster von start.bat noch?");
  }
  if (!res.ok) {
    let msg = `Fehler ${res.status}`;
    try {
      const body = await res.json();
      msg = body.fehler || body.detail || msg;
    } catch {
      /* keine JSON-Antwort */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  system: () => call<SystemInfo>("/api/system"),
  projects: () => call<Project[]>("/api/projects"),
  project: (id: string) => call<Project>(`/api/projects/${id}`),
  transcript: (id: string) => call<Transcript>(`/api/projects/${id}/transcript`),
  create: (body: { name: string; mode: Mode; filename: string; size: number; model: string; language: string }) =>
    call<Project>("/api/projects", json(body)),
  uploadChunk: (id: string, offset: number, chunk: Blob) =>
    call<{ uploaded: number }>(`/api/projects/${id}/upload?offset=${offset}`, { method: "PUT", body: chunk }),
  uploadDone: (id: string) => call<Project>(`/api/projects/${id}/upload/done`, { method: "POST" }),
  retry: (id: string) => call<Project>(`/api/projects/${id}/retry`, { method: "POST" }),
  remove: (id: string) => call<{ ok: boolean }>(`/api/projects/${id}`, { method: "DELETE" }),
  proxyUrl: (id: string) => `/api/projects/${id}/vorschau.mp4`,
  thumbUrl: (id: string) => `/api/projects/${id}/bild.jpg`,
};

export function formatTime(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  const mm = h ? String(m).padStart(2, "0") : String(m);
  return (h ? `${h}:` : "") + `${mm}:${String(r).padStart(2, "0")}`;
}

export function formatSize(bytes: number): string {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  return `${Math.round(bytes / 1e6)} MB`;
}
