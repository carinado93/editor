// Verbindung zum Python-Motor.

export type Mode = "youtube" | "reel" | "idee" | "kombi";

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
  idea_note?: string;
  manual_cut?: boolean;
  clip_starts?: { n: number; t: number; name: string }[];
  from_idea?: boolean;
  render?: { status: "warteschlange" | "arbeitet" | "fertig" | "fehler" | "abgebrochen"; progress: number; message: string; error: string | null; quality: string; file?: string };
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
  tempo: "locker" | "normal" | "straff" | "original";
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
  seo_keyword?: string;
  thumb_hooks?: string[];
  title_seo?: string[][];
  hook_seo?: string[][];
}

export interface Overlay {
  id: string;
  kind: string;
  start: number;
  end: number;
  text: string;
  on: boolean;
  anim?: "pop" | "karte" | "wort" | "slide";
  /** nur YouTube-Animationen (kind "yt") */
  style?: "label" | "sticker" | "check" | "quote" | "number" | "name";
  number?: string;
  list?: { text: string; t: number }[];
  /** nur große Effekte (kind "fx") */
  type?: string;
  place?: "scene" | "side";
  title?: string;
  items?: string[];
  item_t?: number[];
  why?: string;
  /** Stativ-Tricks: leerer Raum, Posen (Original-Zeit), Verschwinden oder Auftauchen */
  bg_t?: number | null;
  pose_t?: number[];
  mode?: "vanish" | "appear";
  /** Größe des Effekts (1 = normal) */
  scale?: number;
  pos_x?: "auto" | "left" | "center" | "right";
  pos_y?: "auto" | "top" | "middle" | "bottom";
}

export interface EffectType {
  key: string;
  group: "A" | "B" | "C" | "D";
  label: string;
  places: ("scene" | "side")[];
}

export interface SpeedRange {
  start: number;
  end: number;
  factor: number;
  mute: boolean;
}

export interface ReelTexts {
  caption: string;
  hashtags: string[];
  cover_text: string;
  shorts_title: string;
  scenes?: string[];
  warnings?: string[];
}

export interface Clip {
  id: string;
  title: string;
  hook_text: string;
  texts?: string[];
  fx?: Overlay[];
  parts: number[][];
  segments: [number, number][];
  duration: number;
  why: string;
  caption: string;
  hashtags: string[];
  shorts_title: string;
  text: string;
  warnings?: string[];
  status: "vorschlag" | "warteschlange" | "arbeitet" | "fertig" | "fehler";
  progress?: number;
  message?: string;
  error?: string | null;
  file?: string;
  size?: number;
  srt?: string;
  subs?: boolean;
  own?: boolean;
}

export interface RenderOptions {
  zoom: boolean;
  loudness: boolean;
  denoise: boolean;
  subtitles: "aus" | "srt" | "einbrennen";
  karaoke: boolean;
  declick?: boolean;
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
    speed?: SpeedRange[];
    fx_allowed?: string[];
    render_options: RenderOptions;
    time_cuts?: [number, number][];
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

export interface LetterSlide {
  lines: string[];
  bg: "cream" | "sage";
  image: string | null;
  motif: string;
  zoom: number;
  fx: number;
  fy: number;
  wants_art?: boolean;
}

export interface LetterPart {
  text: string;
  style: "storyteller" | "painted";
  acrylic: number;
  time: string;
  caption: string;
  slides: LetterSlide[];
  auto_split: boolean;
  files: string[];
  scheduled: { ok: boolean; waiting?: boolean; error?: string | null; planner?: string | null } | null;
}

export interface Letter {
  id: string;
  title: string;
  number: string;
  langs: string[];
  parts: Record<string, LetterPart[]>;
}

export interface LetterSummary {
  id: string;
  title: string;
  number: string;
  langs: string[];
}

export interface CarouselSlide {
  title: string;
  lines: string[];
}

export interface Carousel {
  id: string;
  topic: string;
  language: string;
  theme: string;
  cover_title: string;
  teaser: string;
  slides: CarouselSlide[];
  caption: string;
  hashtags: string[];
  files: string[];
}

export interface CarouselSummary {
  id: string;
  topic: string;
  cover_title: string;
  created: number;
  files: string[];
}

export interface PlanItem {
  id: string;
  date: string;
  type: "reel" | "carousel" | "youtube" | "letter" | "story";
  title: string;
  idea: string;
  account: string;
  status: "idea" | "doing" | "done";
}

export interface FxStyle {
  id: string;
  name: string;
  allowed: string[];
  wish: string;
  sizes: Record<string, number>;
  outro: boolean;
  render: Partial<Record<"zoom" | "loudness" | "denoise" | "declick" | "karaoke", boolean> & { subtitles: string }>;
}

export interface CoverPhoto {
  file: string;
  face: number[] | null;
}

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new Error("No connection to the engine. Is the black start.bat window still open?");
  }
  if (!res.ok) {
    let msg = `Error ${res.status}`;
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
  claudeSettings: () => call<{ configured: boolean; masked: string; model: string }>("/api/einstellungen/claude"),
  claudeSaveKey: (key: string) =>
    call<{ configured: boolean; masked: string; model: string }>("/api/einstellungen/claude", { ...json({ key }), method: "PUT" }),
  claudeDeleteKey: () => call<{ configured: boolean; masked: string; model: string }>("/api/einstellungen/claude", { method: "DELETE" }),
  claudeChat: (messages: { role: string; content: string }[], language: string) =>
    call<{ text: string }>("/api/claude/chat", json({ messages, language })),
  reelTextsClaude: (id: string, idea: string, language: string) =>
    call<{ texts: ReelTexts; full_caption: string; cuts?: CutView & { warnings?: string[] } }>(`/api/projects/${id}/reel-texte/claude`, json({ idea, language })),
  youtubeTextsClaude: (id: string) =>
    call<{ prompt: string; meta: YoutubeMeta; full_description: string }>(`/api/projects/${id}/youtube-texte/claude`, { method: "POST" }),
  updateStatus: (force = false) =>
    call<{ current: string; available: boolean; behind: number; can_update: boolean; reason: string }>(`/api/update/status${force ? "?force=true" : ""}`),
  updateNow: () => call<{ ok: boolean; version: string }>("/api/update", { method: "POST" }),
  version: () => call<{ version: string }>("/api/version"),
  projects: () => call<Project[]>("/api/projects"),
  ideaReelNew: () => call<{ draft: string }>("/api/idea-reel", { method: "POST" }),
  ideaReelPhoto: (draft: string, k: number, file: File) => call<{ ok: boolean }>(`/api/idea-reel/${draft}/photo/${k}`, { method: "PUT", body: file }),
  ideaReelBuild: (draft: string, body: { name: string; idea: string; seconds: number; language: string }) =>
    call<Project>(`/api/idea-reel/${draft}/build`, json(body)),
  plan: () => call<{ items: PlanItem[] }>("/api/plan"),
  planAdd: (it: Partial<PlanItem>) => call<{ items: PlanItem[] }>("/api/plan", json(it)),
  planUpdate: (id: string, patch: Partial<PlanItem>) => call<{ items: PlanItem[] }>(`/api/plan/${id}`, { ...json(patch), method: "PUT" }),
  planDelete: (id: string) => call<{ items: PlanItem[] }>(`/api/plan/${id}`, { method: "DELETE" }),
  planWeek: (engine: string, body: { start: string; focus: string; counts: Record<string, number>; language: string }) =>
    call<{ items: PlanItem[] }>(`/api/plan/week/${engine}`, json(body)),
  planExtract: (engine: string, text: string, language: string) => call<{ items: PlanItem[] }>(`/api/plan/extract/${engine}`, json({ text, language })),
  styles: () => call<{ styles: FxStyle[] }>("/api/styles"),
  styleSave: (st: Omit<FxStyle, "id">) => call<{ styles: FxStyle[] }>("/api/styles", json(st)),
  styleDelete: (sid: string) => call<{ styles: FxStyle[] }>(`/api/styles/${sid}`, { method: "DELETE" }),
  openOutbox: (kind = "") => call<{ folder: string }>(`/api/outbox/open?kind=${kind}`, { method: "POST" }),
  letters: () => call<{ letters: LetterSummary[] }>("/api/letters"),
  letterNew: (title: string, number: string, langs: string[]) => call<Letter>("/api/letters", json({ title, number, langs })),
  letter: (lid: string) => call<Letter>(`/api/letter/${lid}`),
  letterMeta: (lid: string, patch: { title?: string; number?: string }) => call<Letter>(`/api/letter/${lid}`, { ...json(patch), method: "PUT" }),
  letterDelete: (lid: string) => call<{ letters: LetterSummary[] }>(`/api/letter/${lid}`, { method: "DELETE" }),
  letterPart: (lid: string, lang: string, idx: number, patch: Partial<LetterPart>) =>
    call<Letter>(`/api/letter/${lid}/${lang}/${idx}`, { ...json(patch), method: "PUT" }),
  letterPreviewUrl: (lid: string, lang: string, idx: number, k: number, v: string) => `/api/letter/${lid}/${lang}/${idx}/preview/${k}?v=${encodeURIComponent(v)}`,
  letterImage: (lid: string, lang: string, idx: number, k: number, file: File) =>
    call<Letter>(`/api/letter/${lid}/${lang}/${idx}/image/${k}`, { method: "PUT", body: file }),
  letterImageDelete: (lid: string, lang: string, idx: number, k: number) =>
    call<Letter>(`/api/letter/${lid}/${lang}/${idx}/image/${k}`, { method: "DELETE" }),
  letterPrompt: (lid: string, lang: string, idx: number, k: number) => call<{ prompt: string }>(`/api/letter/${lid}/${lang}/${idx}/prompt/${k}`),
  letterSuggest: (lid: string, lang: string, engine: string) => call<Letter>(`/api/letter/${lid}/suggest/${engine}?lang=${lang}`, { method: "POST" }),
  letterRender: (lid: string) => call<Letter>(`/api/letter/${lid}/render`, { method: "POST" }),
  letterZip: (lid: string) => `/api/letter/${lid}/zip`,
  letterSend: (lid: string) => call<{ letter: Letter; sentence: string }>(`/api/letter/${lid}/send`, { method: "POST" }),
  letterPictures: (lid: string) => call<{ letter: Letter; sentence: string }>(`/api/letter/${lid}/pictures`, { method: "POST" }),
  letterSync: (lid: string) => call<{ letter: Letter; pictures: number; scheduled: number }>(`/api/letter/${lid}/sync`, { method: "POST" }),
  publishSettings: () => call<Record<string, string>>("/api/einstellungen/publish"),
  publishSettingsSave: (values: Record<string, string>) => call<Record<string, string>>("/api/einstellungen/publish", { ...json({ values }), method: "PUT" }),
  carousels: () => call<{ carousels: CarouselSummary[] }>("/api/carousels"),
  carouselDraft: (engine: string, body: { topic: string; points: number; language: string; project: string }) =>
    call<Carousel>(`/api/carousels/${engine}`, json(body)),
  carousel: (cid: string) => call<Carousel>(`/api/carousel/${cid}`),
  carouselEdit: (cid: string, patch: Partial<Carousel>) => call<Carousel>(`/api/carousel/${cid}`, { ...json(patch), method: "PUT" }),
  carouselDelete: (cid: string) => call<{ carousels: CarouselSummary[] }>(`/api/carousel/${cid}`, { method: "DELETE" }),
  carouselFile: (cid: string, name: string) => `/api/carousel/${cid}/file/${encodeURIComponent(name)}`,
  carouselZip: (cid: string) => `/api/carousel/${cid}/zip`,
  project: (id: string) => call<Project>(`/api/projects/${id}`),
  transcript: (id: string) => call<Transcript>(`/api/projects/${id}/transcript`),
  create: (body: { name: string; mode: Mode; filename: string; size: number; model: string; language: string }) =>
    call<Project>("/api/projects", json(body)),
  combineNew: () => call<{ draft: string }>("/api/combine", { method: "POST" }),
  combineChunk: (draft: string, k: number, name: string, offset: number, chunk: Blob) =>
    call<{ uploaded: number }>(`/api/combine/${draft}/clip/${k}?name=${encodeURIComponent(name)}&offset=${offset}`, { method: "PUT", body: chunk }),
  combinePlan: (description: string, names: string[]) =>
    call<{ transitions: string[]; note: string }>("/api/combine/plan/claude", json({ description, names })),
  combineBuild: (draft: string, body: { name: string; manual: boolean; language: string; model: string; transitions: string[] }) =>
    call<Project>(`/api/combine/${draft}/build`, json(body)),
  assistant: (id: string, wish: string) =>
    call<{ view: CutView; message: string; done: string[] }>(`/api/projects/${id}/assistant/claude`, json({ wish })),
  timeCuts: (id: string, ranges: [number, number][]) => call<CutView>(`/api/projects/${id}/cuts/time`, { ...json({ ranges }), method: "PUT" }),
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
  queue: () => call<{ running: { lane: string; project: string; name: string; kind: string; seconds: number }[] }>(`/api/queue`),
  effectTypes: () => call<{ types: EffectType[] }>(`/api/effects/types`),
  suggestEffects: (id: string, engine: "claude" | "ollama", allowed: string[], wish: string) =>
    call<CutView>(`/api/projects/${id}/effects/${engine}`, json({ allowed, wish })),
  effectPreviewUrl: (id: string, fid: string, v: number) => `/api/projects/${id}/effects/preview/${fid}?v=${v}`,
  /** Vorschau-Bild eines Effekts, so wie er gerade im Formular steht (ohne Speichern) */
  effectPreviewLive: async (id: string, item: Overlay, signal?: AbortSignal): Promise<string> => {
    const r = await fetch(`/api/projects/${id}/effects-preview`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ item }), signal,
    });
    if (!r.ok) throw new Error("Preview not possible");
    return URL.createObjectURL(await r.blob());
  },
  setClipEffects: (id: string, cid: string, items: Overlay[]) =>
    call<{ clips: Clip[] }>(`/api/projects/${id}/clips/${cid}/effects`, { ...json({ items }), method: "PUT" }),
  suggestClipEffects: (id: string, cid: string, engine: "claude" | "ollama", allowed: string[], wish: string) =>
    call<{ clips: Clip[] }>(`/api/projects/${id}/clips/${cid}/effects/${engine}`, json({ allowed, wish })),
  clipEffectPreview: async (id: string, cid: string, item: Overlay, signal?: AbortSignal): Promise<string> => {
    const r = await fetch(`/api/projects/${id}/clips/${cid}/effects-preview`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ item }), signal,
    });
    if (!r.ok) throw new Error("Preview not possible");
    return URL.createObjectURL(await r.blob());
  },
  exportWatchUrl: (id: string, file: string) => `/api/projects/${id}/export/${encodeURIComponent(file)}?inline=1`,
  setSpeed: (id: string, ranges: SpeedRange[]) =>
    call<CutView>(`/api/projects/${id}/cuts/speed`, { ...json({ ranges }), method: "PUT" }),
  suggestAnimations: (id: string, engine: "claude" | "ollama") =>
    call<CutView>(`/api/projects/${id}/animations/${engine}`, { method: "POST" }),
  suggestBuzz: (id: string) => call<CutView>(`/api/projects/${id}/cuts/buzzwords-suggest`, { method: "POST" }),
  blick: (id: string) => call<{ events: { start: number; end: number }[]; face_box: number[] | null; ready: boolean }>(`/api/projects/${id}/blick`),
  youtubeTexts: (id: string) => call<{ prompt: string; meta: YoutubeMeta | null; full_description: string }>(`/api/projects/${id}/youtube-texte`),
  youtubeTextsOllama: (id: string) =>
    call<{ prompt: string; meta: YoutubeMeta; full_description: string }>(`/api/projects/${id}/youtube-texte/ollama`, { method: "POST" }),
  importYoutubeTexts: (id: string, text: string) =>
    call<{ meta: YoutubeMeta; full_description: string }>(`/api/projects/${id}/youtube-texte/import`, json({ text })),
  saveYoutubeTexts: (id: string, m: YoutubeMeta) =>
    call<{ meta: YoutubeMeta; full_description: string }>(`/api/projects/${id}/youtube-texte`, {
      ...json({ titles: m.titles, chapters: m.chapters, description: m.description, tags: m.tags, hashtags: m.hashtags,
        seo_keyword: m.seo_keyword ?? "", thumb_hooks: m.thumb_hooks ?? [] }),
      method: "PUT",
    }),
  thumbnails: (id: string) => call<{ thumbnails: { file: string; t: number }[] }>(`/api/projects/${id}/thumbnails`, { method: "POST" }),
  thumbnailUrl: (id: string, file: string) => `/api/projects/${id}/thumbnails/${encodeURIComponent(file)}`,
  coverDefaults: (id: string) =>
    call<{ youtube: { text: string; pill: string }; meditation: Record<string, string>; reel: { text: string; color: string }; next_color: string }>(
      `/api/projects/${id}/cover-vorschlag`,
    ),
  coverPhotos: (id: string) => call<{ photos: CoverPhoto[] }>(`/api/projects/${id}/cover-photos`),
  addCoverPhoto: (id: string, file: File) =>
    call<{ photos: CoverPhoto[] }>(`/api/projects/${id}/cover-photos`, { method: "PUT", body: file }),
  deleteCoverPhoto: (id: string, name: string) =>
    call<{ photos: CoverPhoto[] }>(`/api/projects/${id}/cover-photos/${encodeURIComponent(name)}`, { method: "DELETE" }),
  coverPhotoUrl: (id: string, name: string) => `/api/projects/${id}/cover-photos/${encodeURIComponent(name)}`,
  covers: (id: string, body: Record<string, string | string[]>) => call<{ files: string[]; color: string | null }>(`/api/projects/${id}/covers`, json(body)),
  coverUrl: (id: string, file: string) => `/api/projects/${id}/cover/${encodeURIComponent(file)}`,
  coverColorUsed: (used: string) => call<{ next: string }>(`/api/cover-farbe/verwendet`, json({ used })),
  setOverlays: (id: string, overlays: Overlay[]) =>
    call<CutView>(`/api/projects/${id}/cuts/overlays`, { ...json({ overlays }), method: "PUT" }),
  reelTexts: (id: string) =>
    call<{ texts: ReelTexts | null; full_caption: string; silent: boolean; language: string; idea: string }>(`/api/projects/${id}/reel-texte`),
  reelPrompt: (id: string, idea: string, language: string) => call<{ prompt: string }>(`/api/projects/${id}/reel-texte/auftrag`, json({ idea, language })),
  reelTextsOllama: (id: string, idea: string, language: string) =>
    call<{ texts: ReelTexts; full_caption: string; cuts?: CutView & { warnings?: string[] } }>(`/api/projects/${id}/reel-texte/ollama`, json({ idea, language })),
  importReelTexts: (id: string, text: string, idea: string, language: string) =>
    call<{ texts: ReelTexts; full_caption: string }>(`/api/projects/${id}/reel-texte/import`, json({ text, idea, language })),
  applyScenes: (id: string) => call<CutView & { warnings: string[] }>(`/api/projects/${id}/reel-texte/szenen-uebernehmen`, { method: "POST" }),
  saveReelTexts: (id: string, t: ReelTexts) =>
    call<{ texts: ReelTexts; full_caption: string }>(`/api/projects/${id}/reel-texte`, {
      ...json({ caption: t.caption, hashtags: t.hashtags, cover_text: t.cover_text, shorts_title: t.shorts_title }),
      method: "PUT",
    }),
  clips: (id: string) => call<{ clips: Clip[]; feedback: string[] }>(`/api/projects/${id}/clips`),
  suggestClips: (id: string, engine: string, feedback: string) =>
    call<{ clips: Clip[]; feedback: string[] }>(`/api/projects/${id}/clips/vorschlagen`, json({ engine, feedback })),
  editClip: (id: string, cid: string, patch: Partial<Clip>) =>
    call<{ clips: Clip[] }>(`/api/projects/${id}/clips/${cid}`, { ...json(patch), method: "PUT" }),
  clipSentences: (id: string) => call<{ sentences: { id: number; text: string; dur: number; t: number }[] }>(`/api/projects/${id}/clip-sentences`),
  ownClip: (id: string, start: number, end: number, engine = "claude") =>
    call<{ clips: Clip[]; new: string; note: string }>(`/api/projects/${id}/clips/own`, json({ start, end, engine })),
  setClipParts: (id: string, cid: string, parts: number[][]) =>
    call<{ clips: Clip[] }>(`/api/projects/${id}/clips/${cid}/parts`, { ...json({ parts }), method: "PUT" }),
  refineClip: (id: string, cid: string, engine: string, wish: string) =>
    call<{ clips: Clip[] }>(`/api/projects/${id}/clips/${cid}/refine/${engine}`, json({ wish })),
  deleteClip: (id: string, cid: string) => call<{ clips: Clip[] }>(`/api/projects/${id}/clips/${cid}`, { method: "DELETE" }),
  renderClip: (id: string, cid: string) => call<{ clips: Clip[] }>(`/api/projects/${id}/clips/${cid}/render`, { method: "POST" }),
  cancelRender: (id: string) => call<Project>(`/api/projects/${id}/render/cancel`, { method: "POST" }),
  cancelClip: (id: string, cid: string) => call<{ clips: Clip[] }>(`/api/projects/${id}/clips/${cid}/cancel`, { method: "POST" }),
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
