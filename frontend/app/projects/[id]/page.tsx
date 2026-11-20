"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Download, FileVideo, Loader2, Plus, RefreshCw, Trash2, Wand2, Archive } from "lucide-react";
import { API, api, Clip, Job, Project, upload, useFonts, useJob } from "@/lib/api";
import { Badge, Button, Card, Input, JobBar, Notice, Progress, scoreColor } from "@/components/ui";
import { StatusBadge } from "@/components/status-badge";
import { ClipEditor } from "@/components/clip-editor";
import { DurationPicker, DurationValue } from "@/components/duration-picker";
import { cn, deepMerge, fmtTime } from "@/lib/utils";

interface Detail { project: Project; clips: Clip[]; job: Job | null }

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [renders, setRenders] = useState<Record<string, string>>({});
  const [showRegen, setShowRegen] = useState(false);
  const [dur, setDur] = useState<DurationValue>({ preset: "45-60", min: 45, max: 60 });
  const [maxClips, setMaxClips] = useState(8);
  const fonts = useFonts();

  const refresh = useCallback(async () => {
    try {
      const r = await api<Detail>(`/projects/${id}`);
      setD((old) => {
        // keep local (not yet flushed) edits of the active clip intact if only exports/social changed
        return r;
      });
      setErr("");
      if (r.job && !jobId) setJobId(r.job.id);
      setActiveId((a) => (a && r.clips.some((c) => c.id === a) ? a : r.clips[0]?.id ?? null));
    } catch (e: any) { setErr(e.message); }
  }, [id, jobId]);
  useEffect(() => { refresh(); }, [id]); // eslint-disable-line
  useEffect(() => {
    const p = d?.project;
    if (p) { setDur({ preset: "custom", min: p.prefs?.min_dur ?? 45, max: p.prefs?.max_dur ?? 60 }); setMaxClips(p.prefs?.max_clips ?? 8); }
  }, [d?.project.id]); // eslint-disable-line
  const job = useJob(jobId, () => { setJobId(null); refresh(); });

  // processing without a job handle (e.g. page reopened): keep polling
  useEffect(() => {
    if (d?.project.status !== "processing" || jobId) return;
    const t = setInterval(refresh, 2000); return () => clearInterval(t);
  }, [d?.project.status, jobId, refresh]);

  // debounced clip patches
  const pending = useRef<Record<string, { patch: any; timer: any }>>({});
  const patchClip = useCallback((cid: string, patch: any) => {
    setD((old) => old && { ...old, clips: old.clips.map((c) => (c.id === cid ? deepMerge(c, patch) : c)) });
    const cur = pending.current[cid];
    clearTimeout(cur?.timer);
    const merged = deepMerge(cur?.patch ?? {}, patch);
    pending.current[cid] = {
      patch: merged,
      timer: setTimeout(async () => {
        const p = pending.current[cid].patch; delete pending.current[cid];
        try { await api(`/clips/${cid}`, { method: "PATCH", body: p }); setErr(""); }
        catch (e: any) { setErr(e.message); refresh(); }
      }, 500),
    };
  }, [refresh]);

  if (!d) return <div>{err ? <Notice kind="error">{err}</Notice> : <p className="text-sm text-muted-foreground">Loading…</p>}</div>;
  const { project: p, clips } = d;
  const active = clips.find((c) => c.id === activeId) || null;
  const selected = clips.filter((c) => c.selected);

  const regen = async () => {
    setErr("");
    try { const r = await api<{ job_id: string }>(`/projects/${id}/reanalyze`, { body: { min_dur: dur.min, max_dur: dur.max, max_clips: maxClips } }); setJobId(r.job_id); setShowRegen(false); }
    catch (e: any) { setErr(e.message); }
  };
  const exportSelected = async () => {
    setErr("");
    try {
      const r = await api<{ jobs: { clip_id: string; job_id: string }[] }>(`/projects/${id}/render`, { body: { clip_ids: selected.map((c) => c.id) } });
      setRenders((x) => ({ ...x, ...Object.fromEntries(r.jobs.map((j) => [j.clip_id, j.job_id])) }));
    } catch (e: any) { setErr(e.message); }
  };
  const addClip = async () => {
    try { const c = await api<Clip>(`/projects/${id}/clips`, { body: { start: 0, end: Math.min(30, p.meta?.duration || 30), title: "Custom clip" } }); await refresh(); setActiveId(c.id); } catch (e: any) { setErr(e.message); }
  };
  const rename = async (name: string) => { if (name.trim() && name !== p.name) { await api(`/projects/${id}`, { method: "PATCH", body: { name } }); refresh(); } };
  const busy = p.status === "processing" || !!job;
  const totalExports = clips.reduce((n, c) => n + c.exports.length, 0);

  return (
    <div>
      <Link href="/projects" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Projects</Link>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <input defaultValue={p.name} key={p.name} onBlur={(e) => rename(e.target.value)} className="w-full bg-transparent text-2xl font-semibold tracking-tight outline-none focus:ring-2 focus:ring-primary/50 rounded px-1 -mx-1" />
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <StatusBadge status={p.status} />
            {p.meta?.duration ? <span>{fmtTime(p.meta.duration)}</span> : null}
            {p.meta?.width ? <span>{p.meta.width}×{p.meta.height} · {Math.round(p.meta.fps)} fps</span> : null}
            {p.language && <span>Language: {p.language.toUpperCase()}</span>}
            {p.analysis?.engine && <Badge>{p.analysis.engine === "builtin" ? "Built-in analyzer" : `AI: ${p.analysis.engine}`}</Badge>}
          </div>
        </div>
        {p.status !== "processing" && p.analysis && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowRegen((v) => !v)} disabled={busy}><RefreshCw className="h-4 w-4" />Regenerate suggestions</Button>
            {totalExports > 0 && <a href={`${API}/api/projects/${id}/zip`}><Button variant="secondary"><Archive className="h-4 w-4" />Download all (ZIP)</Button></a>}
          </div>
        )}
      </div>

      {err && <div className="mb-4"><Notice kind="error">{err}</Notice></div>}
      {busy && (
        <Card className="mb-5 p-4">
          {job ? <JobBar job={job} onCancel={() => api(`/jobs/${job.id}/cancel`, { method: "POST" })} /> : <div className="flex items-center gap-2 text-sm"><Loader2 className="h-4 w-4 animate-spin" />Processing…</div>}
          <p className="mt-2 text-xs text-muted-foreground">The first transcription downloads the speech model once (needs internet); later runs are offline. Large videos take a while: progress above is measured, not estimated.</p>
        </Card>
      )}
      {p.status === "error" && !busy && (
        <div className="mb-5 space-y-3"><Notice kind="error"><b>Processing failed.</b> {p.error}</Notice>
          {p.source_type === "youtube" && <Button variant="secondary" onClick={async () => { try { const r = await api<{ job_id: string }>(`/projects/${id}/retry`, { method: "POST", body: {} }); setJobId(r.job_id); refresh(); } catch (e: any) { setErr(e.message); } }}><RefreshCw className="h-4 w-4" />Try again</Button>}
        </div>
      )}
      {p.analysis?.note && !busy && <div className="mb-5"><Notice kind="warn">{p.analysis.note}</Notice></div>}
      {p.analysis?.summary && !busy && <p className="mb-5 text-sm text-muted-foreground"><span className="font-medium text-foreground">Summary: </span>{p.analysis.summary}</p>}

      {!p.can_render && (p.status === "needs_video" || (p.source_type !== "live" && p.status !== "processing")) && !busy && <AttachVideo project={p} onStarted={(j) => { setJobId(j); refresh(); }} />}

      {showRegen && (
        <Card className="mb-5 space-y-4 p-4">
          <DurationPicker value={dur} onChange={setDur} />
          <div className="flex items-end gap-3"><div><label className="mb-1 block text-xs text-muted-foreground">Maximum clips</label><Input className="w-24" type="number" min={1} max={30} value={maxClips} onChange={(e) => setMaxClips(+e.target.value)} /></div>
            <Button onClick={regen}><Wand2 className="h-4 w-4" />Regenerate</Button></div>
          <p className="text-xs text-muted-foreground">This replaces the current suggestions (your exported files are kept).</p>
        </Card>
      )}

      {!clips.length && !busy && p.status !== "error" && p.analysis && <Card className="p-8 text-center text-sm text-muted-foreground">No clip suggestions yet. Try a different clip length, or add a clip manually.<div className="mt-3"><Button variant="secondary" onClick={addClip}><Plus className="h-4 w-4" />Add custom clip</Button></div></Card>}

      {clips.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
          <div className="space-y-2 lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:self-start lg:overflow-y-auto lg:pr-1">
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selected.length === clips.length} onChange={(e) => clips.forEach((c) => c.selected !== e.target.checked && patchClip(c.id, { selected: e.target.checked }))} />Select all ({clips.length})</label>
              <Button size="sm" variant="ghost" onClick={addClip}><Plus className="h-3.5 w-3.5" />Add</Button>
            </div>
            {clips.map((c) => (
              <div key={c.id} onClick={() => setActiveId(c.id)} className={cn("cursor-pointer rounded-lg border p-3 transition-colors", c.id === activeId ? "border-primary bg-primary/10" : "bg-card hover:border-primary/40")}>
                <div className="flex items-start gap-2">
                  <input type="checkbox" className="mt-1" checked={c.selected} onClick={(e) => e.stopPropagation()} onChange={(e) => patchClip(c.id, { selected: e.target.checked })} />
                  <div className="min-w-0 flex-1">
                    <div className="line-clamp-2 text-sm font-medium">{c.title}</div>
                    <div className="mt-1 text-xs tabular-nums text-muted-foreground">{fmtTime(c.start)} – {fmtTime(c.end)} · {Math.round(c.end - c.start)}s</div>
                    <div className="mt-1 flex items-center gap-2"><Badge variant="primary">{c.kind}</Badge>{c.exports.length > 0 && <Badge variant="success">{c.exports.length} exported</Badge>}</div>
                  </div>
                  <div className={cn("text-xl font-bold tabular-nums", scoreColor(c.score))} title="Viral potential estimate (not a guarantee)">{Math.round(c.score)}</div>
                </div>
                {renders[c.id] && <RenderChip jobId={renders[c.id]} onDone={() => { setRenders((r) => { const n = { ...r }; delete n[c.id]; return n; }); refresh(); }} />}
              </div>
            ))}
            <Button className="w-full" disabled={!selected.length || !p.can_render} onClick={exportSelected}><Download className="h-4 w-4" />Render selected ({selected.length})</Button>
            {!p.can_render && <p className="text-xs text-warning">Attach the video file to render clips.</p>}
            {p.can_render && !p.has_video && <p className="text-xs text-muted-foreground">Each clip’s segment is downloaded when rendered, then deleted.</p>}
            {active && <Button variant="ghost" size="sm" className="w-full text-danger" onClick={async () => { if (confirm("Delete this clip suggestion?")) { await api(`/clips/${active.id}`, { method: "DELETE" }); refresh(); } }}><Trash2 className="h-3.5 w-3.5" />Delete this clip</Button>}
          </div>
          <div className="min-w-0">{active && <ClipEditor key={active.id} project={p} clip={active} fonts={fonts} patch={patchClip} refresh={refresh} />}</div>
        </div>
      )}
    </div>
  );
}

function RenderChip({ jobId, onDone }: { jobId: string; onDone: () => void }) {
  const job = useJob(jobId, onDone);
  if (!job) return null;
  return (
    <div className="mt-2">
      <Progress value={job.progress} />
      <div className="mt-1 flex justify-between text-[11px] text-muted-foreground"><span className="truncate">{job.status === "error" ? <span className="text-danger">{job.error}</span> : job.message || job.stage}</span><span>{Math.round(job.progress)}%</span></div>
    </div>
  );
}

function AttachVideo({ project, onStarted }: { project: Project; onStarted: (jobId: string) => void }) {
  const [pct, setPct] = useState<number | null>(null); const [err, setErr] = useState(""); const [ok, setOk] = useState(false);
  const acc = project.analysis?.access;
  const go = async (f?: File) => {
    if (!f) return; setErr(""); setPct(0);
    try { const r = await upload<{ job_id: string }>(`/projects/${project.id}/video?filename=${encodeURIComponent(f.name)}`, f, setPct).promise; setPct(null); onStarted(r.job_id); }
    catch (e: any) { setErr(e.message); setPct(null); }
  };
  return (
    <Card className="mb-5 space-y-3 p-4">
      <h3 className="text-sm font-semibold">{project.source_type === "youtube" ? "Attach the video file to render clips" : "No video file attached"}</h3>
      {project.source_type === "youtube" && (
        <p className="text-sm text-muted-foreground">
          {acc?.transcript ? "Suggestions above come from YouTube’s public captions (timing is estimated). " : acc?.reason ? `${acc.reason} ` : ""}
          Nothing has been downloaded: ClipForge only read public metadata and captions. To get video clips, either confirm below that you may use this video (clips are then fetched one segment at a time and deleted after rendering), or upload the file yourself.
        </p>
      )}
      {project.source_type === "youtube" && !project.yt_authorized && (
        <div className="space-y-2 rounded-md border p-3">
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={ok} onChange={(e) => setOk(e.target.checked)} />I own this video or have permission to use it, so ClipForge may download just each clip’s time range temporarily (deleted after rendering).</label>
          <Button disabled={!ok} onClick={async () => { try { await api(`/projects/${project.id}/authorize-download`, { body: { authorized: true } }); onStarted(""); } catch (e: any) { setErr(e.message); } }}>Enable automatic video clips</Button>
        </div>
      )}
      <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"><FileVideo className="h-4 w-4" />Choose video file<input type="file" accept="video/*,.mkv,.avi,.ts" className="hidden" onChange={(e) => go(e.target.files?.[0])} /></label>
      {pct !== null && <div><Progress value={pct} /><p className="mt-1 text-xs text-muted-foreground">{pct < 100 ? `Uploading ${Math.round(pct)}%` : "Reading the video…"}</p></div>}
      {err && <Notice kind="error">{err}</Notice>}
    </Card>
  );
}
