"use client";
import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { api, ClipSettings } from "@/lib/api";
import { Button, Card, CardContent, CardHeader, CardTitle, Label, Notice, PageHeader, Select, Slider, Switch } from "@/components/ui";

export default function VideoSettings() {
  const [v, setV] = useState<ClipSettings | null>(null); const [err, setErr] = useState(""); const [saved, setSaved] = useState(false);
  useEffect(() => { api<any>("/settings").then((s) => setV(s.video)).catch((e) => setErr(e.message)); }, []);
  if (!v) return err ? <Notice kind="error">{err}</Notice> : null;
  const upd = (p: any) => setV({ ...v, ...Object.fromEntries(Object.entries(p).map(([k, val]: any) => [k, typeof val === "object" ? { ...(v as any)[k], ...val } : val])) } as ClipSettings);
  const save = async () => { try { await api("/settings", { method: "PUT", body: { video: v } }); setSaved(true); setTimeout(() => setSaved(false), 2000); } catch (e: any) { setErr(e.message); } };
  const en = v.enhance, ex = v.export;
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Video Settings" subtitle="Defaults for newly created clips. Existing clips keep their own settings." actions={<Button onClick={save}>{saved ? <><Check className="h-4 w-4" />Saved</> : "Save defaults"}</Button>} />
      {err && <div className="mb-4"><Notice kind="error">{err}</Notice></div>}
      <div className="space-y-6">
        <Card><CardHeader><CardTitle>Format and framing</CardTitle></CardHeader><CardContent className="grid grid-cols-2 gap-3">
          <div><Label>Aspect ratio</Label><Select value={v.format} onChange={(e) => upd({ format: e.target.value })}><option value="9:16">9:16 – Reels / Shorts</option><option value="1:1">1:1 – Square</option><option value="16:9">16:9 – Landscape</option><option value="4:5">4:5 – Instagram feed</option></Select></div>
          <div><Label>Framing</Label><Select value={v.layout} onChange={(e) => upd({ layout: e.target.value })}><option value="smart">Smart (auto: facecam + content, or face crop)</option><option value="facecam">Facecam + content (always)</option><option value="face">Face-follow crop only</option><option value="center">Center crop</option><option value="blur">Blurred background</option><option value="fill">Colour fill</option><option value="split">Split screen</option></Select></div>
          <div><Label>Zoom</Label><Select value={en.zoom} onChange={(e) => upd({ enhance: { zoom: e.target.value } })}><option value="none">None</option><option value="punch">Punch-in</option><option value="push">Slow push-in</option></Select></div>
        </CardContent></Card>
        <Card><CardHeader><CardTitle>Export</CardTitle></CardHeader><CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Resolution</Label><Select value={ex.resolution} onChange={(e) => upd({ export: { resolution: +e.target.value } })}><option value={720}>720p</option><option value={1080}>1080p</option><option value={1440}>1440p</option><option value={2160}>4K</option></Select></div>
            <div><Label>Frame rate</Label><Select value={ex.fps} onChange={(e) => upd({ export: { fps: +e.target.value } })}><option value={24}>24</option><option value={30}>30</option><option value={60}>60</option></Select></div>
            <div><Label>Codec</Label><Select value={ex.codec} onChange={(e) => upd({ export: { codec: e.target.value } })}><option value="h264">MP4 (H.264)</option><option value="h265">MP4 (H.265)</option></Select></div>
            <div><Label>Quality</Label><Select value={ex.quality} onChange={(e) => upd({ export: { quality: e.target.value } })}><option value="high">High quality</option><option value="balanced">Balanced</option><option value="small">Smaller file</option></Select></div>
          </div>
          <p className="text-xs text-muted-foreground">ClipForge never invents detail: if the source has fewer pixels or frames than requested, the export says so (1440p / 4K / 60 fps need a source that really has them).</p>
        </CardContent></Card>
        <Card><CardHeader><CardTitle>Enhancements</CardTitle></CardHeader><CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Slider label="Brightness" value={en.brightness} min={-0.3} max={0.3} step={0.01} onChange={(x) => upd({ enhance: { brightness: x } })} />
            <Slider label="Contrast" value={en.contrast} min={0.7} max={1.5} step={0.01} onChange={(x) => upd({ enhance: { contrast: x } })} />
            <Slider label="Saturation" value={en.saturation} min={0} max={2} step={0.01} onChange={(x) => upd({ enhance: { saturation: x } })} />
            <Slider label="Sharpness" value={en.sharpness} min={0} max={1.5} step={0.05} onChange={(x) => upd({ enhance: { sharpness: x } })} />
            <Slider label="Fade in" value={en.fade_in} min={0} max={2} step={0.1} suffix=" s" onChange={(x) => upd({ enhance: { fade_in: x } })} />
            <Slider label="Fade out" value={en.fade_out} min={0} max={2} step={0.1} suffix=" s" onChange={(x) => upd({ enhance: { fade_out: x } })} />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Switch label="Stabilize" checked={en.stabilize} onChange={(x) => upd({ enhance: { stabilize: x } })} />
            <Switch label="Normalize loudness" checked={en.normalize_audio} onChange={(x) => upd({ enhance: { normalize_audio: x } })} />
            <Switch label="Reduce noise" checked={en.denoise_audio} onChange={(x) => upd({ enhance: { denoise_audio: x } })} />
          </div>
          <p className="text-xs text-muted-foreground">Music and sound effects are never added automatically; choose your own files per clip.</p>
        </CardContent></Card>
      </div>
    </div>
  );
}
