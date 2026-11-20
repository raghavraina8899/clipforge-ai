"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Captions, Crop, Download, Image as ImageIcon, Megaphone, Scissors, Trash2, Type, Wand2, Upload, Loader2 } from "lucide-react";
import Link from "next/link";
import { api, BrandKit, Clip, ClipSettings, FontInfo, Project, upload, url, useJob, Word } from "@/lib/api";
import { Badge, Button, Card, Input, JobBar, Label, Notice, Select, Slider, Switch, Tabs, scoreColor } from "@/components/ui";
import { ClipPreview, Framing } from "@/components/clip-preview";
import { CaptionControls, PresetGallery, WordEditor } from "@/components/caption-editor";
import { SocialPanel } from "@/components/social-panel";
import { ThumbnailEditor } from "@/components/thumbnail-editor";
import { ExportPanel } from "@/components/export-panel";
import { fmtTime, parseTime } from "@/lib/utils";

interface TightenPlan { removed: number[][]; pauses: number; fillers: number; removed_seconds: number; new_duration: number; duration: number }

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

  // URL-only projects: a small temporary preview segment of just this clip is fetched on demand
  const urlOnly = !project.has_video && project.can_render;
  const [pv, setPv] = useState<{ ready: boolean; url?: string; seg_start: number; width: number; height: number } | null>(null);
  const [pvJob, setPvJob] = useState<string | null>(null);
  const [pvErr, setPvErr] = useState("");
  const loadPv = useCallback(async () => {
    if (!urlOnly) return;
    setPvErr("");
    try {
      const i = await api<any>(`/clips/${clip.id}/preview-info`);
      if (i.ready) { setPv(i); return; }
      setPv(null);
      const r = await api<any>(`/clips/${clip.id}/preview`, { method: "POST", body: {} });
      if (r.ready) { loadPvRef.current?.(); } else setPvJob(r.job_id);
    } catch (e: any) { setPvErr(e.message); }
  }, [clip.id, urlOnly]); // eslint-disable-line
  const loadPvRef = useRef<() => void>(undefined);
  loadPvRef.current = loadPv;
  const pvJobState = useJob(pvJob, (j) => { setPvJob(null); if (j.status === "done") { loadPv(); } else if (j.status === "error") setPvErr(j.error || "Preview failed"); else if (j.status === "cancelled") setPvErr("Preview cancelled."); });
  const pvJobRef = useRef<string | null>(null); pvJobRef.current = pvJob;
  // leaving this clip: stop a preview download that has not started yet, so clicking through clips does not pile up requests
  useEffect(() => () => { const id = pvJobRef.current; if (id) api(`/jobs/${id}/cancel?only_queued=1`, { method: "POST" }).catch(() => {}); }, [clip.id]);
  const rangeKey = `${clip.start.toFixed(1)}-${clip.end.toFixed(1)}`;
  useEffect(() => { if (!pvJob) { const t = setTimeout(loadPv, 700); return () => clearTimeout(t); } }, [clip.id, rangeKey, urlOnly]); // eslint-disable-line

  const loadWords = useCallback(() => { api<{ words: Word[] }>(`/clips/${clip.id}/words`).then((r) => setWords(r.words)).catch(() => setWords([])); }, [clip.id, clip.start, clip.end]);
  useEffect(() => { loadWords(); }, [loadWords]);
  useEffect(() => { if (pv?.ready) loadWords(); }, [pv?.url]); // eslint-disable-line
  const hasPreview = project.has_video || !!pv?.ready;
  useEffect(() => {
    setFraming(null);
    if (!hasPreview || !["smart", "split", "face", "facecam"].includes(st.layout)) return;
    let stop = false; setFramingBusy(true);
    api<Framing>(`/clips/${clip.id}/framing`).then((f) => !stop && setFraming(f)).catch(() => {}).finally(() => !stop && setFramingBusy(false));
    return () => { stop = true; };
  }, [clip.id, clip.start, clip.end, st.layout, hasPreview, pv?.url]);
  const onTime = useCallback((t: number) => setPlayhead(t), []);

  // tightening summary + the parts the preview should skip
  const [plan, setPlan] = useState<TightenPlan | null>(null);
  const tk = JSON.stringify(st.tighten || {});
  useEffect(() => {
    if (!st.tighten?.enabled) { setPlan(null); return; }
    let stop = false;
    const t = setTimeout(() => api<TightenPlan>(`/clips/${clip.id}/tighten-plan`, { body: { settings: st.tighten } }).then((p) => !stop && setPlan(p)).catch(() => {}), 350);
    return () => { stop = true; clearTimeout(t); };
  }, [clip.id, clip.start, clip.end, tk, words.length]); // eslint-disable-line

  return (
    <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
      <div className="xl:sticky xl:top-6 xl:self-start">
        {project.has_video && project.proxy_url ? (
          <ClipPreview src={url(project.proxy_url)} srcW={project.meta.width} srcH={project.meta.height} start={clip.start} end={clip.end} settings={st} words={words} framing={framing} onTime={onTime} seekTo={seek} skip={plan?.removed} />
        ) : urlOnly && pv?.ready && pv.url ? (
          <ClipPreview src={url(pv.url)} srcW={pv.width} srcH={pv.height} start={clip.start - pv.seg_start} end={clip.end - pv.seg_start} settings={st}
            words={words.map((w) => ({ ...w, s: w.s - pv.seg_start, e: w.e - pv.seg_start }))} framing={framing} onTime={onTime} seekTo={seek} skip={plan?.removed} />
        ) : urlOnly ? (
          <Card className="space-y-3 p-4">
            {pvErr ? <Notice kind="error">{pvErr}<div className="mt-2"><Button size="sm" variant="secondary" onClick={loadPv}>Try again</Button></div></Notice>
              : pvJobState ? <JobBar job={pvJobState} onCancel={async () => { await api(`/jobs/${pvJobState.id}/cancel`, { method: "POST" }).catch(() => {}); setPvJob(null); setPvErr("Preview cancelled."); }} />
              : <p className="text-sm text-muted-foreground">Preparing preview…</p>}
            <p className="text-xs text-muted-foreground">Only this clip’s short segment is downloaded (480p). It is deleted after you export the clip.</p>
          </Card>
        ) : <Notice kind="warn">No video file is attached to this project, so there is nothing to preview.</Notice>}
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
          {tab === "clip" && <ClipTab clip={clip} playhead={clip.start + playhead} patch={(p) => patch(clip.id, p)} seek={(t) => setSeek((s) => ({ t, n: s.n + 1 }))} plan={plan} set={set} />}
          {tab === "captions" && (
            <div className="space-y-5">
              <div className="rounded-md border p-3"><Switch label="Show captions in the video" checked={st.caption.show !== false} onChange={(v) => set({ caption: { show: v } })} />
                {st.caption.show === false && <p className="mt-2 text-xs text-muted-foreground">Captions are hidden in the preview and the exported video. The SRT subtitle file is still saved next to the MP4 if you want it separately. Hook and ending text are controlled in the Hook & ending tab.</p>}</div>
              <div className={st.caption.show === false ? "pointer-events-none space-y-5 opacity-40" : "space-y-5"}>
              <div><h4 className="mb-2 text-sm font-semibold">Style preset</h4><PresetGallery value={st.caption.preset} onPick={(p) => set({ caption: { ...p.style, preset: p.id, show: st.caption.show } })} /></div>
              <div><h4 className="mb-2 text-sm font-semibold">Customize</h4><CaptionControls style={st.caption} fonts={fonts} onChange={(c) => set({ caption: { ...c, preset: st.caption.preset === "custom" ? "custom" : st.caption.preset } })} /></div>
              </div>
              <HiddenRanges clip={clip} playhead={playhead} set={set} />
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

function ClipTab({ clip, playhead, patch, seek, plan, set }: { clip: Clip; playhead: number; patch: (p: any) => void; seek: (t: number) => void; plan: TightenPlan | null; set: (p: any) => void }) {
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
      <TightenBox clip={clip} plan={plan} set={set} />
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
      <BrandPicker st={st} set={set} />
      <div><h4 className="mb-2 text-sm font-semibold">Format</h4>
        <div className="flex flex-wrap gap-2">{[["9:16", "Reels / Shorts"], ["1:1", "Square"], ["16:9", "Landscape"], ["4:5", "Feed"]].map(([f, l]) => (
          <button key={f} onClick={() => set({ format: f })} className={`rounded-md border px-3 py-2 text-left text-sm ${st.format === f ? "border-primary bg-primary/10 text-primary" : "border-input"}`}><div className="font-medium">{f}</div><div className="text-[11px] text-muted-foreground">{l}</div></button>))}</div></div>
      <div><h4 className="mb-2 text-sm font-semibold">Framing</h4>
        <div className="grid gap-2 sm:grid-cols-2">{[["smart", "Smart (auto)", "Streamer facecam detected → face on top, gameplay/screen below. Otherwise follows the speaker's face (vlogs)."], ["facecam", "Facecam + content", "Always stack: face on top, full gameplay/screen below."], ["face", "Face-follow crop", "Only the speaker, full-screen vertical crop."], ["center", "Center crop", "Fixed center framing."], ["blur", "Blurred background", "Whole frame over a blurred copy. No cropping."], ["fill", "Colour fill", "Whole frame on a solid background."], ["split", "Split screen", "Two people stacked (needs two faces)."]].map(([id, l, d]) => (
          <button key={id} onClick={() => set({ layout: id })} className={`rounded-md border p-2.5 text-left ${st.layout === id ? "border-primary bg-primary/10" : "border-input"}`}><div className="text-sm font-medium">{l}</div><div className="text-xs text-muted-foreground">{d}</div></button>))}</div>
        {["smart", "facecam"].includes(st.layout) && (
          <div className="mt-3 space-y-3 rounded-md border p-3">
            <h5 className="text-xs font-semibold">Facecam + content layout</h5>
            <Slider label="Face area (share of screen)" value={st.facecam?.share ?? 0.4} min={0.25} max={0.6} step={0.01} onChange={(v) => set({ facecam: { share: v } })} />
            <div className="grid grid-cols-2 gap-2">{[["fit", "Show full content (blurred sides)"], ["fill", "Fill area (crop sides)"]].map(([id, l]) => (
              <button key={id} onClick={() => set({ facecam: { content: id } })} className={`rounded-md border px-2 py-1.5 text-xs ${(st.facecam?.content ?? "fit") === id ? "border-primary bg-primary/10 text-primary" : "border-input"}`}>{l}</button>))}</div>
            <Switch label="Cut the facecam out of the lower content (no second face)" checked={st.facecam?.hide ?? true} onChange={(v) => set({ facecam: { hide: v } })} />
            <div><Label>Caption placement</Label><Select value={st.facecam?.caption ?? "face"} onChange={(e) => set({ facecam: { caption: e.target.value } })}>
              <option value="face">On the face panel (keeps gameplay clear)</option><option value="seam">On the seam between face and content</option><option value="bottom">Bottom of the screen</option></Select></div>
            <p className="text-xs text-muted-foreground">Used only when a small face overlay is detected in the video; otherwise the normal face-follow crop is used and the export report says so.</p>
          </div>
        )}
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
      <Notice kind="info">Hook and ending text is an overlay only. HookHunt never reorders, cuts or alters what the speaker says, so edits cannot change their meaning. Keep hooks truthful to the clip.</Notice>
    </div>
  );
}


function HiddenRanges({ clip, playhead, set }: { clip: Clip; playhead: number; set: (p: any) => void }) {
  const dur = clip.end - clip.start;
  const ranges = clip.settings.caption.hidden ?? [];
  const save = (r: { start: number; end: number }[]) => set({ caption: { hidden: r.map((x) => ({ start: Math.max(0, Math.min(dur, +x.start.toFixed(2))), end: Math.max(0, Math.min(dur, +x.end.toFixed(2))) })) } });
  const upd = (i: number, p: Partial<{ start: number; end: number }>) => save(ranges.map((r, k) => (k === i ? { ...r, ...p } : r)));
  return (
    <div className="space-y-3 rounded-md border p-3">
      <div><h4 className="text-sm font-semibold">Hide captions for part of the clip</h4>
        <p className="mt-1 text-xs text-muted-foreground">Heard a wrong caption? Pause the preview there and hide captions for that stretch (0:00 = start of this clip). Hidden parts also drop out of the exported SRT.</p></div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" onClick={() => save([...ranges, { start: playhead, end: Math.min(dur, playhead + 3) }])}>Hide 3 s from playhead</Button>
        <Button size="sm" variant="secondary" onClick={() => save([...ranges, { start: playhead, end: dur }])}>Hide from playhead to the end</Button>
        <Button size="sm" variant="secondary" onClick={() => save([...ranges, { start: 0, end: playhead }])}>Hide from the start to playhead</Button>
        {ranges.length > 0 && <Button size="sm" variant="ghost" onClick={() => save([])}>Show all captions again</Button>}
      </div>
      {ranges.length > 0 && (
        <>
          <div className="relative h-3 overflow-hidden rounded-full bg-muted" title="Red = captions hidden">
            {ranges.map((r, i) => <div key={i} className="absolute top-0 h-full bg-danger/70" style={{ left: `${(r.start / dur) * 100}%`, width: `${Math.max(0.5, ((r.end - r.start) / dur) * 100)}%` }} />)}
            <div className="absolute top-0 h-full w-0.5 bg-foreground" style={{ left: `${Math.min(100, (playhead / dur) * 100)}%` }} />
          </div>
          <ul className="space-y-2">
            {ranges.map((r, i) => (
              <li key={i} className="flex flex-wrap items-end gap-2">
                <TimeField label="Hide from" value={r.start} onCommit={(v) => upd(i, { start: v })} />
                <TimeField label="to" value={r.end} onCommit={(v) => upd(i, { end: v })} />
                <Button size="sm" variant="outline" onClick={() => upd(i, { start: playhead })}>Start = playhead</Button>
                <Button size="sm" variant="outline" onClick={() => upd(i, { end: playhead })}>End = playhead</Button>
                <Button size="icon" variant="ghost" title="Remove" onClick={() => save(ranges.filter((_, k) => k !== i))}><Trash2 className="h-3.5 w-3.5" /></Button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}


function TightenBox({ clip, plan, set }: { clip: Clip; plan: TightenPlan | null; set: (p: any) => void }) {
  const t = clip.settings.tighten || { enabled: false, silence: true, silence_max: 0.7, keep: 0.2, fillers: true, filler_words: "um, uh, er, hmm" };
  const T = (p: Partial<typeof t>) => set({ tighten: p });
  return (
    <div className="space-y-3 rounded-lg border border-white/5 bg-white/[0.02] p-3">
      <Switch label="Tighten: cut long pauses and filler words" checked={t.enabled} onChange={(v) => T({ enabled: v })} />
      {t.enabled && (
        <>
          <div className="space-y-3">
            <Switch label="Cut long pauses" checked={t.silence} onChange={(v) => T({ silence: v })} />
            {t.silence && (
              <div className="grid gap-3 sm:grid-cols-2">
                <Slider label="Cut pauses longer than" value={t.silence_max} min={0.3} max={2.5} step={0.1} suffix=" s" onChange={(v) => T({ silence_max: v })} />
                <Slider label="Keep a breath of" value={t.keep} min={0.05} max={0.5} step={0.05} suffix=" s" onChange={(v) => T({ keep: v })} />
              </div>
            )}
            <Switch label="Cut filler words" checked={t.fillers} onChange={(v) => T({ fillers: v })} />
            {t.fillers && <div><Label>Filler words (comma separated)</Label><Input value={t.filler_words} onChange={(e) => T({ filler_words: e.target.value })} /></div>}
          </div>
          {plan && (
            <div className={`rounded-md px-3 py-2 text-sm ${plan.removed.length ? "bg-primary/10 text-foreground" : "bg-muted text-muted-foreground"}`}>
              {plan.removed.length
                ? <>Cuts <b>{plan.removed_seconds.toFixed(1)} s</b> ({plan.pauses} pause{plan.pauses === 1 ? "" : "s"}, {plan.fillers} filler word{plan.fillers === 1 ? "" : "s"}). The export is <b>{plan.new_duration.toFixed(1)} s</b> instead of {plan.duration.toFixed(1)} s. The preview skips the cut parts.</>
                : "Nothing to cut with these settings."}
            </div>
          )}
          <p className="text-xs text-muted-foreground">Cuts follow the transcript's word timing, so check the preview. Speech models often leave out "um" and "uh" entirely, so filler cutting only works for fillers that appear in the transcript; pause cutting always works. Captions and the SRT file follow the shorter timeline.</p>
        </>
      )}
    </div>
  );
}


function BrandPicker({ st, set }: { st: ClipSettings; set: (p: any) => void }) {
  const [kits, setKits] = useState<BrandKit[]>([]);
  useEffect(() => { api<{ brands: BrandKit[] }>("/brand").then((r) => setKits(r.brands)).catch(() => {}); }, []);
  const b = st.brand || { id: "", logo: true, intro: true, outro: true };
  const kit = kits.find((k) => k.id === b.id);
  return (
    <div className="space-y-3 rounded-lg border border-white/5 bg-white/[0.02] p-3">
      <div className="flex items-center justify-between"><h4 className="text-sm font-semibold">Brand kit</h4><Link href="/brand" className="text-xs text-primary underline">Manage kits</Link></div>
      <Select value={b.id} onChange={(e) => set({ brand: { id: e.target.value } })}>
        <option value="">None</option>{kits.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}</Select>
      {!kits.length && <p className="text-xs text-muted-foreground">You have no brand kits yet. Create one to add your logo and an intro/outro.</p>}
      {kit && (
        <div className="space-y-2">
          <div className="grid gap-2 sm:grid-cols-3">
            <Switch label="Logo" checked={b.logo && !!kit.logo.file} onChange={(v) => set({ brand: { logo: v } })} />
            <Switch label="Intro" checked={b.intro && !!kit.intro.file} onChange={(v) => set({ brand: { intro: v } })} />
            <Switch label="Outro" checked={b.outro && !!kit.outro.file} onChange={(v) => set({ brand: { outro: v } })} />
          </div>
          {!kit.logo.file && !kit.intro.file && !kit.outro.file && <p className="text-xs text-warning">This kit has no logo, intro or outro yet.</p>}
          {kit.caption && <Button size="sm" variant="secondary" onClick={() => set({ caption: { ...kit.caption } })}>Use this kit's caption style</Button>}
          <p className="text-xs text-muted-foreground">The logo is drawn on the video; the intro and outro are joined before and after the clip when you export, which takes a little longer. Captions and the SRT file shift to follow the intro.</p>
        </div>
      )}
    </div>
  );
}
