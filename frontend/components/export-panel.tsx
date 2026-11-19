"use client";
import { useEffect, useState } from "react";
import { Download, Trash2, FileText, Loader2, Info } from "lucide-react";
import { api, Clip, ClipSettings, Job, url, useJob } from "@/lib/api";
import { Button, JobBar, Label, Notice, Select } from "@/components/ui";
import { fmtBytes, timeAgo } from "@/lib/utils";

export function ExportPanel({ clip, hasVideo, onUpdate, onSettings, onRefresh }: { clip: Clip; hasVideo: boolean; onUpdate: () => void; onSettings: (p: any) => void; onRefresh: () => void }) {
  const ex = clip.settings.export;
  const [plan, setPlan] = useState<any>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const job = useJob(jobId, () => { onRefresh(); });
  useEffect(() => {
    if (!hasVideo) return;
    const t = setTimeout(() => api(`/clips/${clip.id}/plan`, { body: { settings: {} } }).then(setPlan).catch(() => setPlan(null)), 300);
    return () => clearTimeout(t);
  }, [clip.id, clip.settings.export, clip.settings.format, clip.settings.layout, clip.settings.enhance.zoom, hasVideo]);
  const start = async () => {
    setErr("");
    try { const r = await api<{ job_id: string }>(`/clips/${clip.id}/render`, { body: {} }); setJobId(r.job_id); } catch (e: any) { setErr(e.message); }
  };
  const running = job && ["queued", "running"].includes(job.status);
  return (
    <div className="space-y-4">
      {!hasVideo && <Notice kind="warn">The original video file is not attached, so this clip cannot be rendered yet.</Notice>}
      <div className="grid grid-cols-2 gap-3">
        <div><Label>Resolution</Label><Select value={ex.resolution} onChange={(e) => onSettings({ export: { resolution: +e.target.value } })}>
          <option value={720}>720p</option><option value={1080}>1080p</option><option value={1440}>1440p (needs native source)</option><option value={2160}>4K (needs native source)</option></Select></div>
        <div><Label>Frame rate</Label><Select value={ex.fps} onChange={(e) => onSettings({ export: { fps: +e.target.value } })}><option value={24}>24 fps</option><option value={30}>30 fps</option><option value={60}>60 fps (needs 60 fps source)</option></Select></div>
        <div><Label>Format</Label><Select value={ex.codec} onChange={(e) => onSettings({ export: { codec: e.target.value } })}><option value="h264">MP4 (H.264) – most compatible</option><option value="h265">MP4 (H.265) – smaller, less compatible</option></Select></div>
        <div><Label>Quality</Label><Select value={ex.quality} onChange={(e) => onSettings({ export: { quality: e.target.value } })}><option value="high">High quality (slower)</option><option value="balanced">Balanced</option><option value="small">Smaller file</option></Select></div>
      </div>
      {plan && (
        <div className="rounded-md border p-3 text-sm">
          <div className="flex items-center gap-2 font-medium"><Info className="h-4 w-4 text-primary" />Will export {plan.W}×{plan.H} at {plan.fps} fps</div>
          {plan.notes.map((n: string, i: number) => <p key={i} className="mt-1 text-xs text-warning">{n}</p>)}
          {!plan.notes.length && <p className="mt-1 text-xs text-muted-foreground">Native quality: no upscaling needed.</p>}
        </div>
      )}
      {err && <Notice kind="error">{err}</Notice>}
      <Button size="lg" className="w-full" onClick={start} disabled={!hasVideo || !!running}>{running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}Render clip (no watermark)</Button>
      {job && job.status !== "done" && <JobBar job={job} onCancel={() => api(`/jobs/${job.id}/cancel`, { method: "POST" })} />}
      {job?.status === "error" && <Notice kind="error">{job.error}</Notice>}
      {job?.status === "done" && job.result?.notes?.length > 0 && <Notice kind="info">{job.result.notes.map((n: string, i: number) => <div key={i}>{n}</div>)}</Notice>}
      <div>
        <h4 className="mb-2 text-sm font-semibold">Exports for this clip</h4>
        {!clip.exports.length && <p className="text-sm text-muted-foreground">Nothing exported yet.</p>}
        <ul className="space-y-2">
          {[...clip.exports].reverse().map((e) => (
            <li key={e.file} className="flex items-center justify-between gap-2 rounded-md border p-2.5 text-sm">
              <div className="min-w-0"><div className="truncate">{e.width}×{e.height} · {e.fps} fps · {e.codec.toUpperCase()} · {fmtBytes(e.size)}</div><div className="text-xs text-muted-foreground">{timeAgo(e.at)} · {e.layout_used}</div></div>
              <div className="flex shrink-0 gap-1">
                <a href={url(e.url)}><Button size="sm" variant="secondary"><Download className="h-3.5 w-3.5" />MP4</Button></a>
                <a href={url(e.srt_url)}><Button size="sm" variant="ghost"><FileText className="h-3.5 w-3.5" />SRT</Button></a>
                <Button size="icon" variant="ghost" title="Delete export" onClick={async () => { await api(`/clips/${clip.id}/exports/${encodeURIComponent(e.file)}`, { method: "DELETE" }); onUpdate(); }}><Trash2 className="h-3.5 w-3.5" /></Button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
