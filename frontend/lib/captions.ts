import type { CaptionStyle, Word } from "./api";

/** Mirrors backend/app/services/captions.py grouping so the preview matches the export. */
export const NUMBERISH = /^[$€£₹]?\d[\d,.]*[%kKmMbB]?$/;
export const EMOJI_MAP: Record<string, string> = { money: "💰", love: "❤️", fire: "🔥", win: "🏆", success: "🚀", idea: "💡", time: "⏰", secret: "🤫", growth: "📈", mind: "🧠", wow: "😮", happy: "😊" };
export const ANIMATIONS = [
  { id: "none", label: "None (static)" }, { id: "highlight", label: "Word highlight" }, { id: "pop", label: "Pop highlight" },
  { id: "reveal", label: "Word-by-word reveal" }, { id: "fade", label: "Fade in" }, { id: "karaoke", label: "Karaoke sweep" },
];

export function groupWords<T extends { w: string; s: number; e: number }>(words: T[], n: number): T[][] {
  const groups: T[][] = []; let cur: T[] = [];
  words.forEach((w, i) => {
    cur.push(w);
    const nx = words[i + 1];
    if (cur.length >= n || !nx || /[.!?।]$/.test(w.w) || nx.s - w.e > 0.7) { groups.push(cur); cur = []; }
  });
  return groups;
}

export interface ShownWord { w: string; active: boolean; kw: boolean; visible: boolean }
export interface Shown { lines: ShownWord[][]; emoji: string; fade: boolean; pop: boolean; karaokeProgress?: number[] }

export function isKeyword(style: CaptionStyle, word: string): boolean {
  const bare = word.replace(/[^\w$€£₹%.,]/g, "").replace(/^[.,]+|[.,]+$/g, "").toLowerCase();
  const kws = (style.keywords || "").split(/[,\n]/).map((k) => k.trim().toLowerCase()).filter(Boolean);
  return kws.includes(bare) || (!!style.autoKeywords && NUMBERISH.test(bare));
}

/** What the captions look like at clip-relative time t. */
export function captionAt(words: Word[], t: number, style: CaptionStyle): Shown | null {
  const ws = words.filter((w) => w.w !== "");
  const groups = groupWords(ws, Math.max(1, style.wordsAtTime || 3));
  for (let gi = 0; gi < groups.length; gi++) {
    const g = groups[gi];
    const nextStart = groups[gi + 1]?.[0].s ?? Infinity;
    const gEnd = Math.min(Math.max(g[g.length - 1].e + 0.12, g[g.length - 1].s + 0.25), nextStart);
    if (t < g[0].s || t >= gEnd) continue;
    let ai = 0;
    g.forEach((w, i) => { if (t >= w.s) ai = i; });
    const anim = style.animation || "pop";
    const mw = Math.max(1, style.maxWordsPerLine || 3);
    const lines: ShownWord[][] = [];
    for (let i = 0; i < g.length; i += mw) {
      lines.push(g.slice(i, i + mw).map((w, k) => {
        const idx = i + k;
        return { w: style.uppercase ? w.w.toUpperCase() : w.w, active: ["highlight", "pop", "karaoke", "reveal"].includes(anim) && idx === ai, kw: isKeyword(style, w.w), visible: anim !== "reveal" || idx <= ai };
      }));
    }
    let emoji = "";
    if (style.emoji) for (const w of g) { const m = EMOJI_MAP[w.w.replace(/\W/g, "").toLowerCase()]; if (m) { emoji = m; break; } }
    return { lines, emoji, fade: anim === "fade", pop: anim === "pop" && t - g[ai].s < 0.1 };
  }
  return null;
}

export const FALLBACK_FONTS = ["Arial", "Helvetica Neue", "Impact", "Georgia", "Verdana", "Trebuchet MS"];
