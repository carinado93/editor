// Hochladen in Stücken. Läuft weiter, auch wenn man die Seite innerhalb der App wechselt.
// Mehrere Videos werden nacheinander hochgeladen (Batch).

import { api, type Mode } from "./api";

const CHUNK = 8 * 1024 * 1024; // 8 MB

export interface UploadState {
  key: string;
  name: string;
  projectId?: string;
  sent: number;
  size: number;
  error?: string;
  done: boolean;
}

type Listener = (list: UploadState[]) => void;

const uploads: UploadState[] = [];
const listeners = new Set<Listener>();
let running = false;
const waiting: { state: UploadState; file: File; mode: Mode; model: string; language: string }[] = [];

function emit() {
  const copy = uploads.map((u) => ({ ...u }));
  listeners.forEach((l) => l(copy));
}

export function subscribe(l: Listener): () => void {
  listeners.add(l);
  l(uploads.map((u) => ({ ...u })));
  return () => listeners.delete(l);
}

export function queueFiles(files: File[], mode: Mode, model: string, language: string) {
  for (const file of files) {
    const state: UploadState = { key: `${file.name}-${Date.now()}-${Math.random()}`, name: file.name, sent: 0, size: file.size, done: false };
    uploads.unshift(state);
    waiting.push({ state, file, mode, model, language });
  }
  emit();
  void pump();
}

export function dismiss(key: string) {
  const i = uploads.findIndex((u) => u.key === key);
  if (i >= 0 && (uploads[i].done || uploads[i].error)) uploads.splice(i, 1);
  emit();
}

async function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

async function pump() {
  if (running) return;
  running = true;
  while (waiting.length) {
    const job = waiting.shift()!;
    const { state, file } = job;
    try {
      const name = file.name.replace(/\.[^.]+$/, "");
      const project = await api.create({ name, mode: job.mode, filename: file.name, size: file.size, model: job.model, language: job.language });
      state.projectId = project.id;
      emit();
      let offset = 0;
      let failures = 0;
      while (offset < file.size) {
        try {
          const res = await api.uploadChunk(project.id, offset, file.slice(offset, offset + CHUNK));
          offset = res.uploaded;
          failures = 0;
        } catch (e) {
          if (++failures > 5) throw e;
          await sleep(1000 * failures);
        }
        state.sent = offset;
        emit();
      }
      await api.uploadDone(project.id);
      state.done = true;
    } catch (e) {
      state.error = e instanceof Error ? e.message : String(e);
    }
    emit();
  }
  running = false;
}
