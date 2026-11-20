"use client";
import { useEffect, useRef, useState } from "react";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export const url = (p: string) => (p?.startsWith("http") ? p : API + p);

export class ApiError extends Error {}

async function handle(r: Response) {
  if (!r.ok) {
    let msg = `Request failed (${r.status})`;
    try { const j = await r.json(); msg = j.detail || j.message || msg; if (typeof msg !== "string") msg = JSON.stringify(msg); } catch {}
    throw new ApiError(msg);
  }
  return r.json();
}
export async function api<T = any>(path: string, opts: { method?: string; body?: any } = {}): Promise<T> {
  let r: Response;
  try {
    r = await fetch(API + "/api" + path, {
      method: opts.method || (opts.body !== undefined ? "POST" : "GET"),
      headers: opts.body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError("Cannot reach the Frameflow backend. Is it running? (start it with ./start.sh)");
  }
  return handle(r);
}

/** Upload a file as a raw body with real progress events. */
export function upload<T = any>(path: string, file: File, onProgress: (pct: number) => void): { promise: Promise<T>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<T>((resolve, reject) => {
    xhr.open("POST", API + "/api" + path);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress((e.loaded / e.total) * 100);
    xhr.onload = () => {
      try {
        const j = JSON.parse(xhr.responseText);
        xhr.status < 300 ? resolve(j) : reject(new ApiError(typeof j.detail === "string" ? j.detail : "Upload failed"));
      } catch { reject(new ApiError("Upload failed")); }
    };
    xhr.onerror = () => reject(new ApiError("Cannot reach the Frameflow backend. Is it running?"));
    xhr.onabort = () => reject(new ApiError("Upload cancelled"));
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.send(file);
  });
  return { promise, abort: () => xhr.abort() };
}

export interface Job { id: string; project_id: string; clip_id: string | null; kind: string; status: "queued" | "running" | "done" | "error" | "cancelled"; stage: string; progress: number; message: string | null; error: string | null; result: any }

/** Polls a job until it finishes. Progress values are the backend's real measurements. */
export function useJob(jobId: string | null, onDone?: (j: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  const cb = useRef(onDone); cb.current = onDone;
  useEffect(() => {
    if (!jobId) { setJob(null); return; }
    let stop = false;
    const tick = async () => {
      try {
        const j = await api<Job>(`/jobs/${jobId}`);
        if (stop) return;
        setJob(j);
        if (["done", "error", "cancelled"].includes(j.status)) { cb.current?.(j); return; }
      } catch { /* transient; retry */ }
      if (!stop) setTimeout(tick, 900);
    };
    tick();
    return () => { stop = true; };
  }, [jobId]);
  return job;
}

export interface Clip {
  id: string; project_id: string; idx: number; title: string; start: number; end: number; score: number; scores: Record<string, number>;
  reason: string; hook: string; caption: string; kind: string; selected: boolean; settings: ClipSettings; social: any; exports: ExportEntry[]; project_name?: string;
}
export interface ExportEntry { file: string; srt: string; url: string; srt_url: string; at: number; width: number; height: number; fps: number; resolution: number; codec: string; quality: string; duration: number; size: number; notes: string[]; layout_used: string; upscale: number }
export interface CaptionStyle { preset: string; font?: string; size?: number; bold?: boolean; color?: string; highlight?: string; keyword?: string; bg?: string; bgOpacity?: number; outline?: number; outlineColor?: string; shadow?: number; blur?: number; position?: number; lineSpacing?: number; maxWordsPerLine?: number; wordsAtTime?: number; animation?: string; uppercase?: boolean; autoKeywords?: boolean; keywords?: string; emoji?: boolean; spacing?: number; show?: boolean; hidden?: { start: number; end: number }[] }
export interface ClipSettings {
  format: string; layout: string; fill_color?: string; facecam?: { share: number; content: string; hide: boolean; caption: string };
  export: { resolution: number; fps: number; codec: string; quality: string };
  enhance: { stabilize: boolean; brightness: number; contrast: number; saturation: number; sharpness: number; normalize_audio: boolean; denoise_audio: boolean; fade_in: number; fade_out: number; zoom: string };
  hook: { enabled: boolean; text: string; duration: number; style: string };
  ending: { enabled: boolean; text: string; duration: number };
  caption: CaptionStyle;
  audio: { music?: { file: string; volume: number }; sfx?: { file: string; volume: number } };
}
export interface Project {
  id: string; name: string; source_type: string; source_url: string; status: string; stage: string; progress: number; error: string | null; language: string | null;
  meta: any; analysis: any; prefs: any; created_at: number; has_video: boolean; can_render: boolean; yt_authorized: boolean; yt_mode: string; source_deleted: boolean; proxy_url: string; thumb_url: string; clip_count?: number; export_count?: number;
}
export interface Word { w: string; s: number; e: number; i: number }
export interface Preset { id: string; name: string; style: CaptionStyle & Record<string, any> }
export interface FontInfo { name: string; css: string; weight: number; url: string | null }

export function useFonts() {
  const [fonts, setFonts] = useState<FontInfo[]>([]);
  useEffect(() => {
    api<{ fonts: FontInfo[] }>("/fonts").then(async (r) => {
      setFonts(r.fonts);
      for (const f of r.fonts) {
        if (!f.url) continue;
        for (const fam of new Set([f.name, f.css])) {
          try { const ff = new FontFace(fam, `url(${url(f.url)})`, { weight: fam === f.css ? String(f.weight) : "normal" }); await ff.load(); document.fonts.add(ff); } catch {}
        }
      }
    }).catch(() => {});
  }, []);
  return fonts;
}
