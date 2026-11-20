import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }

export function fmtTime(t: number, ms = false): string {
  if (!isFinite(t)) return "0:00";
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  const base = `${m}:${String(s).padStart(2, "0")}`;
  return ms ? `${base}.${Math.floor((t % 1) * 10)}` : base;
}
export function parseTime(s: string): number | null {
  const parts = s.trim().split(":").map(Number);
  if (parts.some((p) => isNaN(p))) return null;
  return parts.reduce((acc, p) => acc * 60 + p, 0);
}
export function fmtBytes(n: number): string {
  if (n <= 0) return "0 KB";
  if (n > 1e9) return (n / 1e9).toFixed(2) + " GB";
  if (n > 1e6) return (n / 1e6).toFixed(1) + " MB";
  return Math.max(1, Math.round(n / 1e3)) + " KB";
}
export function timeAgo(ts: number): string {
  const s = Date.now() / 1000 - ts;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

export function deepMerge<T>(a: T, b: any): T {
  if (b === null || typeof b !== "object" || Array.isArray(b)) return b;
  const out: any = { ...(a as any) };
  for (const k of Object.keys(b)) out[k] = typeof b[k] === "object" && b[k] !== null && !Array.isArray(b[k]) ? deepMerge(out[k] ?? {}, b[k]) : b[k];
  return out;
}


/** Start/end seconds carried by a YouTube link (?t=, start=, end=), like the backend. */
export function ytLinkRange(link: string): { start: number; end: number } {
  try {
    const u = new URL(link.trim());
    const secs = (v: string | null) => {
      if (!v) return 0; v = v.toLowerCase();
      if (/^\d+(\.\d+)?s?$/.test(v)) return parseFloat(v);
      const m = v.match(/^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/);
      return m ? (+(m[1] || 0)) * 3600 + (+(m[2] || 0)) * 60 + (+(m[3] || 0)) : 0;
    };
    const frag = new URLSearchParams(u.hash.replace(/^#/, ""));
    const start = secs(u.searchParams.get("start") || u.searchParams.get("t") || frag.get("t"));
    const end = secs(u.searchParams.get("end"));
    return { start, end: end > start ? end : 0 };
  } catch { return { start: 0, end: 0 }; }
}
