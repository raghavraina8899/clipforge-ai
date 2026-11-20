"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Captions, Crop, Download, Image as ImageIcon, Megaphone, Scissors, Type, Wand2, Upload, Loader2 } from "lucide-react";
import { api, Clip, ClipSettings, FontInfo, Project, upload, url, Word } from "@/lib/api";
import { Badge, Button, Card, Input, Label, Notice, Select, Slider, Switch, Tabs, scoreColor } from "@/components/ui";
import { ClipPreview, Framing } from "@/components/clip-preview";
import { CaptionControls, PresetGallery, WordEditor } from "@/components/caption-editor";
import { SocialPanel } from "@/components/social-panel";
import { ThumbnailEditor } from "@/components/thumbnail-editor";
import { ExportPanel } from "@/components/export-panel";
import { fmtTime, parseTime } from "@/lib/utils";

type Tab = "clip" | "captions" | "look" | "hook" | "social" | "thumb" | "export";
const LABELS: Record<string, string> = { hook: "Opening hook", emotion: "Emotional impact", info: "Information value", engagement: "Engagement", standalone: "Standalone context", ending: "Ending quality" };

export function ClipEditor({ project, clip, fonts, patch, refresh }: { project: Project; clip: Clip; fonts: FontInfo[]; patch: (id: string, p: any) => void; refresh: () => void }) {
  const [tab, setTab] = useState<Tab>("clip");
  const [words, setWords] = useState<Word[]>([]);
  const [framing, setFraming] = useState<Framing | null>(null);
  const [framingBusy, setFramingBusy] = useState(false);
  const [playhead, setPlayhead] = useState(0);
  const [seek, setSeek] = useState({ t: 0, n: 0 });
  const st = clip.settings;
  const set = (p: Partial<ClipSettings> | any) => patch(clip.id, { settings: p });

  const loadWords = useCallback(() => { api<{ words: Word[] }>(`/clips/${clip.id}/words`).then((r) => setWords(r.words)).catch(() => setWords([])); }, [clip.id, clip.start, clip.end]);
  useEffect(() => { loadWords(); }, [loadWords]);
  useEffect(() => {
    setFraming(null);
    if (!project.has_video || !["smart", "split"].includes(st.layout)) return;
    let stop = false; setFramingBusy(true);
    api<Framing>(`/clips/${clip.id}/framing`).then((f) => !stop && setFraming(f)).catch(() => {}).finally(() => !stop && setFramingBusy(false));
    return () => { stop = true; };
  }, [clip.id, clip.start, clip.end, st.layout, project.has_video]);
  const onTime = useCallback((t: number) => setPlayhead(t), []);

  return (
    <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
      <div className="xl:sticky xl:top-6 xl:self-start">
        {project.has_video && project.proxy_url ? (
          <ClipPreview src={url(project.proxy_url)} srcW={project.meta.width} srcH={project.meta.height} start={clip.start} end={clip.end} settings={st} words={words} framing={framing} onTime={onTime} seekTo={seek} />
        ) : project.can_render ? <Notice kind="info">The video for this clip is downloaded only when you render it, so there is no live preview. Caption styling is shown in Subtitle Styles; the exported clip is the real result.</Notice>
          : <Notice kind="warn">No video file is attached to this project, so there is nothing to preview.</Notice>}
        {framingBusy && <p className="mt-2 flex items-center justify-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin" />Detecting faces for smart framing…</p>}
        {framing && !framingBusy && <p className="mt-2 text-center text-xs text-muted-foreground">{framing.note}</p>}
      </div>
      <div className="min-w-0 space-y-4">
        <Tabs<Tab> value={tab} onChange={setTab} tabs={[
          { id: "clip", label: "Clip", icon: <Scissors className="h-3.5 w-3.5" /> }, { id: "captions", label: "Captions", icon: <Captions className="h-3.5 w-3.5" /> },
          { id: "look", label: "Layout & look", icon: <Crop className="h-3.5 w-3.5" /> }, { id: "hook", label: "Hook & ending", icon: <Type className="h-3.5 w-3.5" /> },
          { id: "social", label: "Social text", icon: <Megaphone className="h-3.5 w-3.5" /> }, { id: "thumb", label: "Thumbnail", icon: <ImageIcon className="h-3.5 w-3.5" /> },
          { id: "export", label: "Export", icon: <Download className="h-3.5 w-3.5" /> }]} />
        <Card className="p-4">
          {tab === "clip" && <ClipTab clip={clip} playhead={clip.start + playhead} patch={(p) => patch(clip.id, p)} seek={(t) => setSeek((s) => ({ t, n: s.n + 1 }))} />}
          {tab === "captions" && (
            <div className="space-y-5">
              <div><h4 className="mb-2 text-sm font-semibold">Style preset</h4><PresetGallery value={st.caption.preset} onPick={(p) => set({ caption: { ...p.style, preset: p.id } })} /></div>
              <div><h4 className="mb-2 text-sm font-semibold">Customize</h4><CaptionControls style={st.caption} fonts={fonts} onChange={(c) => set({ caption: { ...c, preset: st.caption.preset === "custom" ? "custom" : st.caption.preset } })} /></div>
              <div><h4 className="mb-2 text-sm font-semibold">Fix words and timing</h4><WordEditor projectId={project.id} words={words} onSaved={loadWords} onSeek={(t) => setSeek((s) => ({ t: t - clip.start, n: s.n + 1 }))} /></div>
              {project.analysis?.word_timing === "estimated" && <Notice kind="warn">Word timing came from YouTube captions and is estimated. Attach your video to transcribe it precisely.</Notice>}
            </div>
          )}
          {tab === "look" && <LookTab st={st} set={set} />}
          {tab === "hook" && <HookTab clip={clip} set={set} />}
          {tab === "social" && <SocialPanel clip={clip} onChange={() => refresh()} />}
          {tab === "thumb" && <ThumbnailEditor clip={clip} fonts={fonts} hasVideo={project.has_video} />}
          {tab === "export" && <ExportPanel clip={clip} hasVideo={project.can_render} onUpdate={refresh} onRefresh={refresh} onSettings={set} />}
        </Card>
      </div>
    </div>
  );
}

function TimeField({ label, value, onCommit }: { label: string; value: number; onCommit: (v: number) => void }) {
  const [txt, setTxt] = useState(fmtTime(value, true));
  useEffect(() => setTxt(fmtTime(value, true)), [value]);
  const commit = () => { const v = parseTime(txt); if (v !== null && Math.abs(v - value) > 0.01) onCommit(v); else setTxt(fmtTime(value, true)); };
  return <div><Label>{label}</Label><Input className="w-28 tabular-nums" value={txt} onChange={(e) => setTxt(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && commit()} /></div>;
}

function ClipTab({ clip, playhead, patch, seek }: { clip: Clip; playhead: number; patch: (p: any) => void; seek: (t: number) => void }) {
  const [err, setErr] = useState("");
  const safe = async (p: any) => { setErr(""); try { patch(p); } catch (e: any) { setErr(e.message); } };
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1"><Label>Title</Label><Input value={clip.title} onChange={(e) => patch({ title: e.target.value })} /></div>
        <div className="text-center"><div className={`text-3xl font-bold tabular-nums ${scoreColor(clip.score)}`}>{Math.round(clip.score)}</div><div className="text-[11px] text-muted-foreground">Viral potential</div></div>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <TimeField label="Start" value={clip.start} onCommit={(v) => safe({ start: v })} />
        <TimeField label="End" value={clip.end} onCommit={(v) => safe({ end: v })} />
        <div className="text-sm text-muted-foreground">Duration <span className="font-medium text-foreground">{(clip.end - clip.start).toFixed(1)} s</span></div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" onClick={() => safe({ start: Math.max(0, +(clip.start - 0.5).toFixed(2)) })}>Start −0.5s</Button>
        <Button size="sm" variant="secondary" onClick={() => safe({ start: +(clip.start + 0.5).toFixed(2) })}>Start +0.5s</Button>
        <Button size="sm" variant="secondary" onClick={() => safe({ end: +(clip.end - 0.5).toFixed(2) })}>End −0.5s</Button>
        <Button size="sm" variant="secondary" onClick={() => safe({ end: +(clip.end + 0.5).toFixed(2) })}>End +0.5s</Button>
        <Button size="sm" variant="outline" onClick={() => safe({ start: +playhead.toFixed(2) })}>Start = playhead</Button>
        <Button size="sm" variant="outline" onClick={() => safe({ end: +playhead.toFixed(2) })}>End = playhead</Button>
      </div>
      {err && <Notice kind="error">{err}</Notice>}
      <div className="rounded-md bg-muted/50 p-3 text-sm"><span className="font-medium">Why this clip: </span>{clip.reason}<div className="mt-2"><Badge variant="primary">{clip.kind}</Badge></div></div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        {Object.entries(LABELS).map(([k, l]) => (
          <div key={k}><div className="flex justify-between text-xs"><span className="text-muted-foreground">{l}</span><span className="tabular-nums">{Math.round(clip.scores?.[k] ?? 0)}</span></div>
            <div className="mt-1 h-1.5 rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${clip.scores?.[k] ?? 0}%` }} /></div></div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">The score is an estimate of how well the clip is built (hook, clarity, ending). It is not a prediction or guarantee of views.</p>
      <div><Label>Suggested hook</Label><Input value={clip.hook} onChange={(e) => patch({ hook: e.target.value })} /></div>
      <div><Label>Suggested caption</Label><Input value={clip.caption} onChange={(e) => patch({ caption: e.target.value })} /></div>
    </div>
  );
}

function LookTab({ st, set }: { st: ClipSettings; set: (p: any) => void }) {
  const en = st.enhance;
  const [assets, setAssets] = useState<string[]>([]);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const loadAssets = () => api<{ assets: string[] }>("/assets").then((r) => setAssets(r.assets)).catch(() => {});
  useEffect(() => { loadAssets(); }, []);
  const up = async (f?: File) => { if (!f) return; setBusy(true); setErr(""); try { await upload(`/assets?filename=${encodeURIComponent(f.name)}`, f, () => {}).promise; await loadAssets(); } catch (e: any) { setErr(e.message); } setBusy(false); };
  const E = (p: Partial<ClipSettings["enhance"]>) => set({ enhance: p });
  const audio = (key: "music" | "sfx") => (
    <div className="space-y-2 rounded-md border p-3">
      <Label>{key === "music" ? "Background music (your own / licensed file)" : "Sound effect at the start (your own / licensed file)"}</Label>
      <Select value={st.audio?.[key]?.file || ""} onChange={(e) => set({ audio: { [key]: e.target.value ? { file: e.target.value, volume: st.audio?.[key]?.volume ?? (key === "music" ? 0.15 : 0.8) } : null } })}>
        <option value="">None</option>{assets.map((a) => <option key={a}>{a}</option>)}</Select>
      {st.audio?.[key]?.file && <Slider label="Volume" value={st.audio[key]!.volume} min={0.02} max={1} step={0.01} onChange={(v) => set({ audio: { [key]: { file: st.audio[key]!.file, volume: v } } })} />}
    </div>
  );
  return (
    <div className="space-y-6">
      <div><h4 className="mb-2 text-sm font-semibold">Format</h4>
        <div className="flex flex-wrap gap-2">{[["9:16", "Reels / Shorts"], ["1:1", "Square"], ["16:9", "Landscape"], ["4:5", "Feed"]].map(([f, l]) => (
          <button key={f} onClick={() => set({ format: f })} className={`rounded-md border px-3 py-2 text-left text-sm ${st.format === f ? "border-primary bg-primary/10 text-primary" : "border-input"}`}><div className="font-medium">{f}</div><div className="text-[11px] text-muted-foreground">{l}</div></button>))}</div></div>
      <div><h4 className="mb-2 text-sm font-semibold">Framing</h4>
        <div className="grid gap-2 sm:grid-cols-2">{[["smart", "Smart crop", "Follows the active speaker's face; falls back to center."], ["center", "Center crop", "Fixed center framing."], ["blur", "Blurred background", "Whole frame over a blurred copy. No cropping."], ["fill", "Colour fill", "Whole frame on a solid background."], ["split", "Split screen", "Two people stacked (needs two faces)."]].map(([id, l, d]) => (
          <button key={id} onClick={() => set({ layout: id })} className={`rounded-md border p-2.5 text-left ${st.layout === id ? "border-primary bg-primary/10" : "border-input"}`}><div className="text-sm font-medium">{l}</div><div className="text-xs text-muted-foreground">{d}</div></button>))}</div>
        {st.layout === "fill" && <div className="mt-2 flex items-center gap-2"><Label className="mb-0">Fill colour</Label><input type="color" value={st.fill_color || "#101010"} onChange={(e) => set({ fill_color: e.target.value })} /></div>}
        <div className="mt-3 grid grid-cols-3 gap-2">{[["none", "No zoom"], ["punch", "Punch-in (static 1.15×)"], ["push", "Slow push-in"]].map(([id, l]) => (
          <button key={id} onClick={() => E({ zoom: id })} className={`rounded-md border px-2 py-1.5 text-xs ${en.zoom === id ? "border-primary bg-primary/10 text-primary" : "border-input"}`}>{l}</button>))}</div>
      </div>
      <div><h4 className="mb-2 text-sm font-semibold">Video enhancement</h4>
        <div className="grid gap-4 sm:grid-cols-2">
          <Slider label="Brightness" value={en.brightness} min={-0.3} max={0.3} step={0.01} onChange={(v) => E({ brightness: v })} />
          <Slider label="Contrast" value={en.contrast} min={0.7} max={1.5} step={0.01} onChange={(v) => E({ contrast: v })} />
          <Slider label="Saturation" value={en.saturation} min={0} max={2} step={0.01} onChange={(v) => E({ saturation: v })} />
          <Slider label="Sharpness" value={en.sharpness} min={0} max={1.5} step={0.05} onChange={(v) => E({ sharpness: v })} />
          <Slider label="Fade in" value={en.fade_in} min={0} max={2} step={0.1} suffix=" s" onChange={(v) => E({ fade_in: v })} />
          <Slider label="Fade out" value={en.fade_out} min={0} max={2} step={0.1} suffix=" s" onChange={(v) => E({ fade_out: v })} />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <Switch label="Stabilize video" checked={en.stabilize} onChange={(v) => E({ stabilize: v })} />
          <Switch label="Normalize loudness" checked={en.normalize_audio} onChange={(v) => E({ normalize_audio: v })} />
          <Switch label="Reduce audio noise" checked={en.denoise_audio} onChange={(v) => E({ denoise_audio: v })} />
        </div>
      </div>
      <div><h4 className="mb-2 text-sm font-semibold">Music and sound effects</h4>
        <p className="mb-2 text-xs text-muted-foreground">Nothing is added automatically. Upload audio you own or that is royalty-free for your use.</p>
        <div className="space-y-3">{audio("music")}{audio("sfx")}
          <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-primary"><Upload className="h-4 w-4" />{busy ? "Uploading…" : "Upload an audio file"}<input type="file" accept="audio/*" className="hidden" onChange={(e) => up(e.target.files?.[0])} /></label>
          {err && <Notice kind="error">{err}</Notice>}</div>
      </div>
    </div>
  );
}

function HookTab({ clip, set }: { clip: Clip; set: (p: any) => void }) {
  const h = clip.settings.hook, e = clip.settings.ending;
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <Switch label="Show an opening hook text (first seconds)" checked={h.enabled} onChange={(v) => set({ hook: { enabled: v, text: h.text || clip.hook } })} />
        <div><Label>Hook text</Label><div className="flex gap-2"><Input value={h.text} onChange={(e) => set({ hook: { text: e.target.value } })} placeholder={clip.hook} /><Button variant="secondary" onClick={() => set({ hook: { text: clip.hook, enabled: true } })}>Use suggestion</Button></div></div>
        <Slider label="Visible for" value={h.duration} min={1} max={3} step={0.1} suffix=" s" onChange={(v) => set({ hook: { duration: v } })} />
        <div className="grid grid-cols-2 gap-2">{[["pop", "Pop-in"], ["none", "Fade only"]].map(([id, l]) => <button key={id} onClick={() => set({ hook: { style: id } })} className={`rounded-md border px-2 py-1.5 text-sm ${h.style === id ? "border-primary bg-primary/10 text-primary" : "border-input"}`}>{l}</button>)}</div>
      </div>
      <div className="space-y-3">
        <Switch label="Show an ending caption (last seconds)" checked={e.enabled} onChange={(v) => set({ ending: { enabled: v } })} />
        <div><Label>Ending text</Label><Input value={e.text} placeholder="Follow for more" onChange={(ev) => set({ ending: { text: ev.target.value } })} /></div>
        <Slider label="Visible for" value={e.duration} min={1} max={4} step={0.1} suffix=" s" onChange={(v) => set({ ending: { duration: v } })} />
      </div>
      <Notice kind="info">Hook and ending text is an overlay only. ClipForge never reorders, cuts or alters what the speaker says, so edits cannot change their meaning. Keep hooks truthful to the clip.</Notice>
    </div>
  );
}
