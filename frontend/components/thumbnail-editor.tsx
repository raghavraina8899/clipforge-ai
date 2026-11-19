"use client";
import { useEffect, useRef, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { api, Clip, FontInfo, url } from "@/lib/api";
import { FALLBACK_FONTS } from "@/lib/captions";
import { Button, Input, Label, Notice, Select, Slider, Switch } from "@/components/ui";
import { cn } from "@/lib/utils";

export function ThumbnailEditor({ clip, fonts, hasVideo }: { clip: Clip; fonts: FontInfo[]; hasVideo: boolean }) {
  const [frames, setFrames] = useState<{ i: number; url: string; t: number }[]>([]);
  const [err, setErr] = useState(""); const [loading, setLoading] = useState(false);
  const [o, setO] = useState({ frame: 0, text: clip.hook || clip.title, font: "Anton", size: 0.09, color: "#FFFFFF", shape: "bar", shapeColor: "#E11D48", contrast: 1.1, brightness: 1, y: 0.72, aspect: "9:16", focus: 0.5, uppercase: true });
  const [prev, setPrev] = useState(""); const [busy, setBusy] = useState(false); const [done, setDone] = useState("");
  const tm = useRef<any>(undefined);
  useEffect(() => {
    if (!hasVideo) return;
    setLoading(true);
    api<{ frames: any[] }>(`/clips/${clip.id}/thumbnails`).then((r) => setFrames(r.frames)).catch((e) => setErr(e.message)).finally(() => setLoading(false));
  }, [clip.id, clip.start, clip.end, hasVideo]);
  useEffect(() => {
    if (!frames.length) return;
    clearTimeout(tm.current);
    tm.current = setTimeout(() => { api<{ url: string }>(`/clips/${clip.id}/thumbnail`, { body: { ...o, final: false } }).then((r) => setPrev(url(r.url) + "&r=" + Date.now())).catch((e) => setErr(e.message)); }, 250);
  }, [o, frames.length, clip.id]);
  const set = (p: Partial<typeof o>) => setO((x) => ({ ...x, ...p }));
  const exportIt = async () => { setBusy(true); setErr(""); try { const r = await api<{ url: string }>(`/clips/${clip.id}/thumbnail`, { body: { ...o, final: true } }); setDone(url(r.url)); window.open(url(r.url), "_blank"); } catch (e: any) { setErr(e.message); } setBusy(false); };
  if (!hasVideo) return <Notice kind="warn">Thumbnails use frames from your original video. Attach the video file to this project first.</Notice>;
  return (
    <div className="space-y-4">
      {err && <Notice kind="error">{err}</Notice>}
      {loading && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Extracting frames from the video…</p>}
      <div><Label>Choose a frame</Label><div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        {frames.map((f) => <button key={f.i} onClick={() => set({ frame: f.i })} className={cn("overflow-hidden rounded border-2", o.frame === f.i ? "border-primary" : "border-transparent")}><img src={url(f.url)} alt="" className="aspect-video w-full object-cover" /></button>)}
      </div></div>
      <div className="grid gap-4 md:grid-cols-[220px_1fr]">
        <div>{prev ? <img src={prev} alt="Thumbnail preview" className="w-full rounded-md border" /> : <div className="aspect-[9/16] rounded-md bg-muted" />}</div>
        <div className="space-y-3">
          <div><Label>Title text</Label><Input value={o.text} onChange={(e) => set({ text: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Font</Label><Select value={o.font} onChange={(e) => set({ font: e.target.value })}>{[...fonts.map((f) => f.name), ...FALLBACK_FONTS.filter((f) => ["Impact", "Arial", "Georgia", "Verdana"].includes(f))].filter((v, i, a) => a.indexOf(v) === i).map((n) => <option key={n}>{n}</option>)}</Select></div>
            <div><Label>Background shape</Label><Select value={o.shape} onChange={(e) => set({ shape: e.target.value })}><option value="bar">Full-width bar</option><option value="box">Rounded box</option><option value="gradient">Bottom gradient</option><option value="none">None</option></Select></div>
            <div><Label>Aspect</Label><Select value={o.aspect} onChange={(e) => set({ aspect: e.target.value })}><option>9:16</option><option>16:9</option><option>1:1</option><option>4:5</option></Select></div>
            <div className="flex items-end gap-3"><div><Label>Text</Label><input type="color" value={o.color} onChange={(e) => set({ color: e.target.value })} /></div><div><Label>Shape</Label><input type="color" value={o.shapeColor} onChange={(e) => set({ shapeColor: e.target.value })} /></div></div>
            <Slider label="Text size" value={o.size} min={0.04} max={0.18} step={0.005} onChange={(v) => set({ size: v })} />
            <Slider label="Text height" value={o.y} min={0} max={1} step={0.02} onChange={(v) => set({ y: v })} />
            <Slider label="Contrast" value={o.contrast} min={0.6} max={1.6} step={0.05} onChange={(v) => set({ contrast: v })} />
            <Slider label="Crop focus (left ↔ right)" value={o.focus} min={0} max={1} step={0.02} onChange={(v) => set({ focus: v })} />
          </div>
          <Switch label="UPPERCASE" checked={o.uppercase} onChange={(v) => set({ uppercase: v })} />
          <Button onClick={exportIt} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}Export thumbnail (PNG)</Button>
          {done && <a className="ml-3 text-xs text-primary underline" href={done}>Download again</a>}
        </div>
      </div>
    </div>
  );
}
