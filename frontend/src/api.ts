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
  render?: { status: "warteschlange" | "arbeitet" | "fertig" | "fehler"; progress: number; message: string; error: string | null; quality: string; file?: string };
  thumbnails?: { file: string; t: number }[];
  exports?: { file: string; duration: number; segments: number; size: number; quality: string; created: number }[];
}

export type CutType = "retake" | "signal" | "doppelt" | "fragment" | "fuellwort" | "blick" | "manuell";

export interface Detection {
  id: string;
  type: Exclude<CutType, "manuell">;
  start: number;
  end: number;
  sure: boolean;
  reason: string;
  active: boolean;
}

export interface CutSettings {
  tempo: "locker" | "normal" | "straff";
  max_gap: number;
  signal_words: string[];
  fillers: Record<string, boolean>;
}

export interface YoutubeMeta {
  titles: string[];
  chapters: { time: string; title: string; t?: number }[];
  description: string;
  tags: string[];
  hashtags: string[];
  warnings?: string[];
  source?: string;
}

export interface Overlay {
  id: string;
  kind: string;
  start: number;
  end: number;
  text: string;
  on: boolean;
}

export interface ReelTexts {
  caption: string;
  hashtags: string[];
  cover_text: string;
  shorts_title: string;
  warnings?: string[];
}

export interface RenderOptions {
  zoom: boolean;
  loudness: boolean;
  denoise: boolean;
  subtitles: "aus" | "srt" | "einbrennen";
  karaoke: boolean;
}

export interface Pause {
  after: number;
  start: number;
  end: number;
  length: number;
  kept: boolean;
  noise?: boolean;
}

export interface CutView {
  cutlist: {
    settings: CutSettings;
    detections: Detection[];
    manual: { cut: number[]; keep: number[] };
    pause_keep: number[];
    buzzwords: { start: number; end: number }[];
    overlays?: Overlay[];
    render_options: RenderOptions;
  };
  evaluation: { flags: (CutType | null)[]; keep: [number, number][]; pauses: Pause[]; new_duration: number; old_duration: number };
  can_undo: boolean;
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
  cuts: (id: string) => call<CutView>(`/api/projects/${id}/cuts`),
  toggleCut: (id: string, det: string, active: boolean) => call<CutView>(`/api/projects/${id}/cuts/toggle`, json({ id: det, active })),
  cutWords: (id: string, indices: number[], cut: boolean) => call<CutView>(`/api/projects/${id}/cuts/words`, json({ indices, cut })),
  setPause: (id: string, after: number, keep: boolean) => call<CutView>(`/api/projects/${id}/cuts/pause`, json({ after, keep })),
  cutSettings: (id: string, settings: Partial<CutSettings>) =>
    call<CutView>(`/api/projects/${id}/cuts/settings`, { ...json(settings), method: "PUT" }),
  resetCuts: (id: string) => call<CutView>(`/api/projects/${id}/cuts/reset`, { method: "POST" }),
  undo: (id: string) => call<CutView>(`/api/projects/${id}/cuts/undo`, { method: "POST" }),
  renderOptions: (id: string, o: Partial<RenderOptions>) =>
    call<CutView>(`/api/projects/${id}/cuts/render-options`, { ...json(o), method: "PUT" }),
  buzzword: (id: string, start: number, end: number, on: boolean) => call<CutView>(`/api/projects/${id}/cuts/buzzword`, json({ start, end, on })),
  suggestBuzz: (id: string) => call<CutView>(`/api/projects/${id}/cuts/buzzwords-suggest`, { method: "POST" }),
  blick: (id: string) => call<{ events: { start: number; end: number }[]; face_box: number[] | null; ready: boolean }>(`/api/projects/${id}/blick`),
  youtubeTexts: (id: string) => call<{ prompt: string; meta: YoutubeMeta | null; full_description: string }>(`/api/projects/${id}/youtube-texte`),
  youtubeTextsOllama: (id: string) =>
    call<{ prompt: string; meta: YoutubeMeta; full_description: string }>(`/api/projects/${id}/youtube-texte/ollama`, { method: "POST" }),
  importYoutubeTexts: (id: string, text: string) =>
    call<{ meta: YoutubeMeta; full_description: string }>(`/api/projects/${id}/youtube-texte/import`, json({ text })),
  saveYoutubeTexts: (id: string, m: YoutubeMeta) =>
    call<{ meta: YoutubeMeta; full_description: string }>(`/api/projects/${id}/youtube-texte`, {
      ...json({ titles: m.titles, chapters: m.chapters, description: m.description, tags: m.tags, hashtags: m.hashtags }),
      method: "PUT",
    }),
  thumbnails: (id: string) => call<{ thumbnails: { file: string; t: number }[] }>(`/api/projects/${id}/thumbnails`, { method: "POST" }),
  thumbnailUrl: (id: string, file: string) => `/api/projects/${id}/thumbnails/${encodeURIComponent(file)}`,
  coverDefaults: (id: string) =>
    call<{ youtube: { text: string; pill: string }; meditation: Record<string, string>; reel: { text: string; color: string }; next_color: string }>(
      `/api/projects/${id}/cover-vorschlag`,
    ),
  covers: (id: string, body: Record<string, string>) => call<{ files: string[]; color: string | null }>(`/api/projects/${id}/covers`, json(body)),
  coverUrl: (id: string, file: string) => `/api/projects/${id}/cover/${encodeURIComponent(file)}`,
  coverColorUsed: (used: string) => call<{ next: string }>(`/api/cover-farbe/verwendet`, json({ used })),
  setOverlays: (id: string, overlays: Overlay[]) =>
    call<CutView>(`/api/projects/${id}/cuts/overlays`, { ...json({ overlays }), method: "PUT" }),
  reelTexts: (id: string) => call<{ prompt: string; texts: ReelTexts | null; full_caption: string }>(`/api/projects/${id}/reel-texte`),
  reelTextsOllama: (id: string) => call<{ texts: ReelTexts; full_caption: string }>(`/api/projects/${id}/reel-texte/ollama`, { method: "POST" }),
  importReelTexts: (id: string, text: string) => call<{ texts: ReelTexts; full_caption: string }>(`/api/projects/${id}/reel-texte/import`, json({ text })),
  saveReelTexts: (id: string, t: ReelTexts) =>
    call<{ texts: ReelTexts; full_caption: string }>(`/api/projects/${id}/reel-texte`, {
      ...json({ caption: t.caption, hashtags: t.hashtags, cover_text: t.cover_text, shorts_title: t.shorts_title }),
      method: "PUT",
    }),
  render: (id: string, quality: string) => call<Project>(`/api/projects/${id}/render`, json({ quality })),
  openFolder: (id: string) => call<{ ok: boolean }>(`/api/projects/${id}/open-folder`, { method: "POST" }),
  exportUrl: (id: string, file: string) => `/api/projects/${id}/export/${encodeURIComponent(file)}`,
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
