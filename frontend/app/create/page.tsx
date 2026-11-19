"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Youtube, Upload, Radio, FileVideo, Pause, Play, Square, Circle, X } from "lucide-react";
import { api, upload, ApiError } from "@/lib/api";
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Label, Notice, PageHeader, Progress, Select, Tabs } from "@/components/ui";
import { DurationPicker, defaultDuration, DurationValue } from "@/components/duration-picker";
import { fmtBytes, fmtTime } from "@/lib/utils";

type Mode = "youtube" | "upload" | "live";
const YT = /(?:youtu\.be\/|youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|live\/|embed\/|v\/))([A-Za-z0-9_-]{11})/;

export default function Create() {
  const [mode, setMode] = useState<Mode>("upload");
  const [dur, setDur] = useState<DurationValue>(defaultDuration);
  const [lang, setLang] = useState("auto");
  const [maxClips, setMaxClips] = useState(8);
  const common = { dur, lang, maxClips };
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Create New Clips" subtitle="Provide a video you own or have permission to use. ClipForge analyzes the speech, finds the best moments and prepares clips with captions." />
      <Tabs<Mode> value={mode} onChange={setMode} tabs={[
        { id: "upload", label: "Upload video", icon: <Upload className="h-3.5 w-3.5" /> },
        { id: "youtube", label: "YouTube URL", icon: <Youtube className="h-3.5 w-3.5" /> },
        { id: "live", label: "Authorized live stream", icon: <Radio className="h-3.5 w-3.5" /> }]} />
      <Card className="mt-4"><CardContent className="space-y-5 p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2"><DurationPicker value={dur} onChange={setDur} /></div>
          <div><Label>Spoken language</Label>
            <Select value={lang} onChange={(e) => setLang(e.target.value)}><option value="auto">Auto-detect</option><option value="en">English</option><option value="hi">Hindi</option></Select></div>
          <div><Label>Maximum clips</Label><Input type="number" min={1} max={30} value={maxClips} onChange={(e) => setMaxClips(Number(e.target.value))} /></div>
        </div>
        {mode === "upload" && <UploadPane {...common} />}
        {mode === "youtube" && <YouTubePane {...common} />}
        {mode === "live" && <LivePane {...common} />}
      </CardContent></Card>
      <p className="mt-4 text-xs text-muted-foreground">Only process videos you own or have permission to use. ClipForge never bypasses logins, DRM or platform restrictions.</p>
    </div>
  );
}

type Common = { dur: DurationValue; lang: string; maxClips: number };
const qs = (c: Common) => `min_dur=${c.dur.min}&max_dur=${c.dur.max}&max_clips=${c.maxClips}&language=${c.lang}`;
const durOk = (c: Common) => c.dur.min >= 5 && c.dur.max > c.dur.min && c.dur.max <= 180;

function UploadPane(c: Common) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [info, setInfo] = useState<{ duration: number; w: number; h: number } | null>(null);
  const [pct, setPct] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const [over, setOver] = useState(false);
  const abort = useRef<(() => void) | undefined>(undefined);
  const pick = useCallback((f: File | undefined) => {
    if (!f) return;
    setErr(""); setInfo(null); setFile(f);
    const u = URL.createObjectURL(f); setPreview(u);
  }, []);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const go = async () => {
    if (!file) return;
    if (!durOk(c)) { setErr("Clip length must be at least 5 s, with max above min and at most 180 s."); return; }
    setErr(""); setPct(0);
    const u = upload<{ project_id: string }>(`/projects/upload?filename=${encodeURIComponent(file.name)}&${qs(c)}`, file, setPct);
    abort.current = u.abort;
    try { const r = await u.promise; router.push(`/projects/${r.project_id}`); } catch (e: any) { setErr(e.message); setPct(null); }
  };
  return (
    <div className="space-y-4">
      {!file ? (
        <label onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-10 text-center transition-colors ${over ? "border-primary bg-primary/10" : "border-input hover:border-primary/60"}`}>
          <FileVideo className="h-8 w-8 text-muted-foreground" />
          <div className="text-sm font-medium">Drag and drop a video here, or click to browse</div>
          <div className="text-xs text-muted-foreground">MP4, MOV, WEBM, MKV, AVI, M4V and more</div>
          <input type="file" accept="video/*,.mkv,.avi,.ts,.m4v" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
        </label>
      ) : (
        <div className="space-y-3">
          <video src={preview} controls className="max-h-72 w-full rounded-md bg-black" onLoadedMetadata={(e) => { const v = e.currentTarget; setInfo({ duration: v.duration, w: v.videoWidth, h: v.videoHeight }); }}
            onError={() => setErr("Your browser cannot preview this format, but ClipForge can usually still process it.")} />
          <div className="flex items-center justify-between text-sm">
            <span className="truncate">{file.name} · {fmtBytes(file.size)}{info ? ` · ${fmtTime(info.duration)} · ${info.w}×${info.h}` : ""}</span>
            {pct === null && <Button variant="ghost" size="sm" onClick={() => { setFile(null); setPreview(""); }}><X className="h-3.5 w-3.5" />Change</Button>}
          </div>
        </div>
      )}
      {pct !== null && (
        <div><div className="mb-1 flex justify-between text-sm"><span>{pct < 100 ? "Uploading" : "Reading the video…"}</span><span className="tabular-nums">{Math.round(pct)}%</span></div><Progress value={pct} />
          <button className="mt-1 text-xs text-muted-foreground underline" onClick={() => abort.current?.()}>Cancel upload</button></div>
      )}
      {err && <Notice kind="error">{err}</Notice>}
      <Button size="lg" className="w-full" disabled={!file || pct !== null} onClick={go}>Analyze and create clips</Button>
    </div>
  );
}

function YouTubePane(c: Common) {
  const router = useRouter();
  const [u, setU] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const valid = YT.test(u);
  const go = async () => {
    if (!durOk(c)) { setErr("Clip length must be at least 5 s, with max above min and at most 180 s."); return; }
    setBusy(true); setErr("");
    try { const r = await api<{ project_id: string }>("/projects/youtube", { body: { url: u, language: c.lang, min_dur: c.dur.min, max_dur: c.dur.max } }); router.push(`/projects/${r.project_id}`); }
    catch (e: any) { setErr(e.message); setBusy(false); }
  };
  return (
    <div className="space-y-4">
      <div><Label>YouTube video URL</Label><Input placeholder="https://www.youtube.com/watch?v=…" value={u} onChange={(e) => setU(e.target.value)} />
        {u && !valid && <p className="mt-1 text-xs text-warning">This does not look like a YouTube video link.</p>}</div>
      <Notice kind="info"><b>What this does:</b> reads the title, thumbnail and public captions, then suggests clip moments from the transcript. ClipForge does <b>not</b> download YouTube videos. To render clips, you attach the video file you own (e.g. exported from YouTube Studio) afterwards.</Notice>
      {err && <Notice kind="error">{err}</Notice>}
      <Button size="lg" className="w-full" disabled={!valid || busy} onClick={go}>{busy ? "Checking…" : "Check video and analyze captions"}</Button>
    </div>
  );
}

function LivePane(c: Common) {
  const router = useRouter();
  const [u, setU] = useState(""); const [name, setName] = useState(""); const [ok, setOk] = useState(false);
  const [pid, setPid] = useState<string | null>(null);
  const [st, setSt] = useState<{ state: string; elapsed: number; bytes: number; error: string }>({ state: "idle", elapsed: 0, bytes: 0, error: "" });
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!pid) return;
    const t = setInterval(() => api<any>(`/projects/${pid}/live`).then(setSt).catch(() => {}), 1000);
    return () => clearInterval(t);
  }, [pid]);
  const create = async () => {
    setBusy(true); setErr("");
    try { const r = await api<{ project_id: string }>("/projects/live", { body: { url: u, name, authorized: ok, language: c.lang } }); await api(`/projects/${r.project_id}`, { method: "PATCH", body: { prefs: { min_dur: c.dur.min, max_dur: c.dur.max, max_clips: c.maxClips } } }); setPid(r.project_id); }
    catch (e: any) { setErr(e.message); } setBusy(false);
  };
  const ctl = async (a: string) => {
    setBusy(true); setErr("");
    try { const r = await api<any>(`/projects/${pid}/live/${a}`, { method: "POST" }); if (a === "stop") { router.push(`/projects/${pid}`); return; } setSt(r); }
    catch (e: any) { setErr(e.message); } setBusy(false);
  };
  if (!pid) return (
    <div className="space-y-4">
      <div><Label>Stream URL (direct stream, e.g. HLS .m3u8, RTMP, RTSP, SRT)</Label><Input placeholder="https://example.com/live/stream.m3u8" value={u} onChange={(e) => setU(e.target.value)} /></div>
      <div><Label>Project name (optional)</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={ok} onChange={(e) => setOk(e.target.checked)} />I own this stream or have permission to record and clip it.</label>
      <Notice kind="info">ClipForge records only direct stream addresses. It does not extract streams from website pages, and it cannot (and will not) bypass logins or DRM. Pausing stops recording: content during a pause is not captured.</Notice>
      {err && <Notice kind="error">{err}</Notice>}
      <Button size="lg" className="w-full" disabled={!u || !ok || busy} onClick={create}>Prepare recorder</Button>
    </div>
  );
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between rounded-md border p-4">
        <div className="flex items-center gap-2 text-sm"><Circle className={`h-3 w-3 ${st.state === "recording" ? "animate-pulse fill-danger text-danger" : "text-muted-foreground"}`} />
          {{ idle: "Ready", recording: "Recording", paused: "Paused", stopped: "Stopped", none: "Idle" }[st.state] || st.state}</div>
        <div className="text-right tabular-nums"><div className="text-xl font-semibold">{fmtTime(st.elapsed)}</div><div className="text-xs text-muted-foreground">{fmtBytes(st.bytes)} captured</div></div>
      </div>
      <div className="flex gap-2">
        {st.state === "idle" && <Button disabled={busy} onClick={() => ctl("start")}><Play className="h-4 w-4" />Start recording</Button>}
        {st.state === "recording" && <Button variant="secondary" disabled={busy} onClick={() => ctl("pause")}><Pause className="h-4 w-4" />Pause</Button>}
        {st.state === "paused" && <Button disabled={busy} onClick={() => ctl("resume")}><Play className="h-4 w-4" />Resume</Button>}
        {["recording", "paused"].includes(st.state) && <Button variant="danger" disabled={busy} onClick={() => ctl("stop")}><Square className="h-4 w-4" />Stop and create clips</Button>}
      </div>
      {(err || st.error) && <Notice kind="error">{err || st.error}</Notice>}
    </div>
  );
}
