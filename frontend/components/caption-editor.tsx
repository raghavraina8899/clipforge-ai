"use client";
import { useEffect, useState } from "react";
import { api, CaptionStyle, FontInfo, Preset, Word } from "@/lib/api";
import { ANIMATIONS, FALLBACK_FONTS } from "@/lib/captions";
import { Input, Label, Select, Slider, Switch } from "@/components/ui";
import { hexA } from "@/components/clip-preview";
import { cn } from "@/lib/utils";

export function usePresets() {
  const [p, setP] = useState<Preset[]>([]);
  useEffect(() => { api<{ presets: Preset[] }>("/presets").then((r) => setP(r.presets)).catch(() => {}); }, []);
  return p;
}

export function StyleSample({ style, text = "Make every word count", className }: { style: CaptionStyle; text?: string; className?: string }) {
  const words = text.split(" ");
  const fs = Math.min(20, ((style.size || 66) as number) * 0.2); const kk = fs / (style.size || 66);
  const st = style as any;
  return (
    <div className={cn("flex h-24 items-center justify-center overflow-hidden rounded-md bg-gradient-to-br from-slate-700 to-slate-900 p-2", className)}>
      <div className="caption-text max-w-full text-center" style={{
        fontFamily: `"${st.font}", sans-serif`, fontSize: fs, fontWeight: st.bold ? 700 : 400, lineHeight: st.lineSpacing || 1.1, letterSpacing: (st.spacing || 0) * kk, color: st.color,
        WebkitTextStroke: !st.bg && st.outline ? `${st.outline * 2 * kk}px ${st.outlineColor}` : undefined,
        background: st.bg ? hexA(st.bg, st.bgOpacity ?? 0.6) : undefined, padding: st.bg ? "2px 6px" : undefined,
        textShadow: [st.shadow ? `${st.shadow * kk}px ${st.shadow * kk}px 0 rgba(0,0,0,.6)` : "", st.blur ? `0 0 ${st.blur * kk * 3}px ${st.outlineColor}` : ""].filter(Boolean).join(",") || undefined,
      }}>
        {words.map((w, i) => <span key={i} style={{ color: i === 1 ? st.highlight : undefined, marginRight: "0.28em" }}>{st.uppercase ? w.toUpperCase() : w}</span>)}
      </div>
    </div>
  );
}

export function PresetGallery({ value, onPick }: { value: string; onPick: (p: Preset) => void }) {
  const presets = usePresets();
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {presets.map((p) => (
        <button key={p.id} onClick={() => onPick(p)} className={cn("rounded-lg border p-1.5 text-left transition-colors", value === p.id ? "border-primary bg-primary/10" : "hover:border-primary/50")}>
          <StyleSample style={p.style} className="h-16" text="Make every word" />
          <div className="mt-1 px-1 text-xs font-medium">{p.name}</div>
        </button>
      ))}
    </div>
  );
}

export function CaptionControls({ style, onChange, fonts }: { style: CaptionStyle; onChange: (patch: Partial<CaptionStyle>) => void; fonts: FontInfo[] }) {
  const s = style as Required<CaptionStyle>;
  const names = [...fonts.map((f) => f.name), ...FALLBACK_FONTS.filter((f) => !fonts.some((x) => x.name === f))];
  const color = (label: string, key: keyof CaptionStyle) => (
    <div><Label>{label}</Label><div className="flex items-center gap-2"><input type="color" value={(style[key] as string) || "#ffffff"} onChange={(e) => onChange({ [key]: e.target.value })} /><span className="text-xs tabular-nums text-muted-foreground">{(style[key] as string) || ""}</span></div></div>
  );
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div><Label>Font</Label><Select value={s.font} onChange={(e) => onChange({ font: e.target.value })}>{names.map((n) => <option key={n}>{n}</option>)}</Select></div>
        <div><Label>Animation</Label><Select value={s.animation} onChange={(e) => onChange({ animation: e.target.value })}>{ANIMATIONS.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}</Select></div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Slider label="Font size" value={s.size} min={30} max={140} step={1} onChange={(v) => onChange({ size: v })} />
        <Slider label="Position (from top)" value={s.position} min={8} max={95} step={1} suffix="%" onChange={(v) => onChange({ position: v })} />
        <Slider label="Words shown at a time" value={s.wordsAtTime} min={1} max={10} step={1} onChange={(v) => onChange({ wordsAtTime: v })} />
        <Slider label="Max words per line" value={s.maxWordsPerLine} min={1} max={8} step={1} onChange={(v) => onChange({ maxWordsPerLine: v })} />
        <Slider label="Line spacing" value={s.lineSpacing} min={0.8} max={1.8} step={0.05} onChange={(v) => onChange({ lineSpacing: v })} />
        <Slider label="Letter spacing" value={s.spacing || 0} min={0} max={10} step={0.5} onChange={(v) => onChange({ spacing: v })} />
        <Slider label="Outline" value={s.outline} min={0} max={16} step={0.5} onChange={(v) => onChange({ outline: v })} />
        <Slider label="Shadow" value={s.shadow} min={0} max={10} step={0.5} onChange={(v) => onChange({ shadow: v })} />
        <Slider label="Glow" value={s.blur || 0} min={0} max={8} step={0.5} onChange={(v) => onChange({ blur: v })} />
      </div>
      <div className="grid grid-cols-3 gap-3">
        {color("Text colour", "color")}{color("Highlight colour", "highlight")}{color("Keyword colour", "keyword")}{color("Outline colour", "outlineColor")}
        <div><Label>Background box</Label><div className="flex items-center gap-2">
          <input type="checkbox" checked={!!s.bg} onChange={(e) => onChange({ bg: e.target.checked ? "#000000" : "" })} />
          {s.bg && <input type="color" value={s.bg} onChange={(e) => onChange({ bg: e.target.value })} />}</div></div>
        {s.bg && <Slider label="Box opacity" value={s.bgOpacity} min={0.1} max={1} step={0.05} onChange={(v) => onChange({ bgOpacity: v })} />}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Switch label="Bold" checked={!!s.bold} onChange={(v) => onChange({ bold: v })} />
        <Switch label="UPPERCASE" checked={!!s.uppercase} onChange={(v) => onChange({ uppercase: v })} />
        <Switch label="Highlight numbers" checked={!!s.autoKeywords} onChange={(v) => onChange({ autoKeywords: v })} />
        <Switch label="Emoji accents" checked={!!s.emoji} onChange={(v) => onChange({ emoji: v })} />
      </div>
      <div><Label>Keywords to highlight (comma separated)</Label><Input value={s.keywords || ""} placeholder="money, secret, free" onChange={(e) => onChange({ keywords: e.target.value })} /></div>
    </div>
  );
}

export function WordEditor({ projectId, words, onSaved, onSeek }: { projectId: string; words: Word[]; onSaved: () => void; onSeek: (t: number) => void }) {
  const [sel, setSel] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const save = async (i: number, patch: { w?: string; s?: number; e?: number }) => {
    try { await api(`/projects/${projectId}/words`, { method: "PUT", body: { edits: [{ i, ...patch }] } }); setErr(""); onSaved(); } catch (e: any) { setErr(e.message); }
  };
  const cur = words.find((w) => w.i === sel);
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">Click a word to fix its spelling or timing. Edits change the transcript for this project, so they apply to every clip that uses these words. Clear the text to remove a word.</p>
      <div className="flex max-h-56 flex-wrap gap-1 overflow-y-auto rounded-md border p-2">
        {words.map((w) => (
          <button key={w.i} onClick={() => { setSel(w.i); onSeek(w.s); }} className={cn("rounded px-1.5 py-0.5 text-sm", sel === w.i ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-accent")}>{w.w}</button>
        ))}
        {!words.length && <span className="text-sm text-muted-foreground">No transcript words in this range.</span>}
      </div>
      {cur && (
        <div key={cur.i} className="grid grid-cols-[1fr_auto_auto] items-end gap-2 rounded-md border p-3">
          <div><Label>Word</Label><Input defaultValue={cur.w} onBlur={(e) => e.target.value !== cur.w && save(cur.i, { w: e.target.value })} onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} /></div>
          <div><Label>Start (s)</Label><Input className="w-24" type="number" step={0.05} defaultValue={cur.s} onBlur={(e) => parseFloat(e.target.value) !== cur.s && save(cur.i, { s: parseFloat(e.target.value) })} /></div>
          <div><Label>End (s)</Label><Input className="w-24" type="number" step={0.05} defaultValue={cur.e} onBlur={(e) => parseFloat(e.target.value) !== cur.e && save(cur.i, { e: parseFloat(e.target.value) })} /></div>
        </div>
      )}
      {err && <p className="text-xs text-danger">{err}</p>}
    </div>
  );
}
