"use client";
import { useEffect, useState } from "react";
import { Gauge, Zap } from "lucide-react";
import { api, useJob } from "@/lib/api";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Label, Notice, Select } from "@/components/ui";
import { JobLoader } from "@/components/loader";

interface EngineInfo { available: { id: string; label: string }[]; best: string; machine: string; apple_silicon: boolean; mlx_installed: boolean; setting: string; chosen: { engine: string; label: string; note: string } }
interface Row { engine: string; label: string; seconds: number; x_realtime: number; minutes_for_20h: number }

export function SpeechCard({ s, put, sys }: { s: any; put: (p: any) => Promise<void>; sys: any }) {
  const [info, setInfo] = useState<EngineInfo | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [err, setErr] = useState("");
  const load = () => api<EngineInfo>("/speech-engine").then(setInfo).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  const job = useJob(jobId, (j) => { setJobId(null); if (j.status === "done") setRows(j.result?.results || []); else if (j.status === "error") setErr(j.error || "Speed test failed"); });
  const start = async () => { setErr(""); setRows(null); try { const r = await api<{ job_id: string }>("/speed-test", { body: {} }); setJobId(r.job_id); } catch (e: any) { setErr(e.message); } };
  const best = rows && rows.length ? Math.max(...rows.map((r) => r.x_realtime)) : 0;
  const fmtMin = (m: number) => (m >= 90 ? `${(m / 60).toFixed(1)} hours` : `${Math.round(m)} minutes`);
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><Zap className="h-4 w-4 text-cyan" />Speech recognition (runs on this computer)</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {info && <div className="rounded-lg border border-white/5 bg-white/[0.03] p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">Using: <b>{info.chosen.label}</b>{info.chosen.engine === info.best && <Badge variant="success">fastest available</Badge>}</div>
          <div className="mt-1 text-xs text-muted-foreground">{info.machine}. HookHunt picks the fastest engine on its own: Apple GPU on Apple-chip Macs, NVIDIA GPU where present, otherwise the CPU.</div>
          {info.chosen.note && <div className="mt-1 text-xs text-warning">{info.chosen.note}</div>}
          {info.apple_silicon && !info.mlx_installed && <div className="mt-1 text-xs text-warning">The faster Apple GPU engine is not installed. Run <code>./start.sh</code> again or <code>backend/.venv/bin/pip install mlx-whisper</code>.</div>}
        </div>}
        <div className="grid gap-3 sm:grid-cols-2">
          <div><Label>Engine</Label><Select value={s.transcription.engine || "auto"} onChange={async (e) => { await put({ transcription: { engine: e.target.value } }); load(); }}>
            <option value="auto">Automatic (recommended)</option>{info?.available.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}</Select></div>
          <div><Label>Model</Label><Select value={s.transcription.model} onChange={(e) => put({ transcription: { model: e.target.value } })}>
            <option value="tiny">tiny – fastest, rough (≈75 MB)</option><option value="base">base – fast (≈145 MB)</option><option value="small">small – recommended (≈480 MB)</option>
            <option value="turbo">turbo – near-best accuracy (≈1.6 GB)</option><option value="medium">medium – accurate, slow (≈1.5 GB)</option><option value="large-v3">large-v3 – best, slowest (≈3 GB)</option></Select></div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" onClick={start} disabled={!!jobId}><Gauge className="h-4 w-4" />Run speed test</Button>
          <span className="text-xs text-muted-foreground">Times each engine on 2.5 minutes of speech with the model selected above (the first run downloads the model).</span>
        </div>
        {job && <JobLoader job={job} variant="process" title="Measuring speed" onCancel={() => api(`/jobs/${job.id}/cancel`, { method: "POST" })} />}
        {err && <Notice kind="error">{err}</Notice>}
        {rows && (
          <div className="overflow-hidden rounded-lg border border-white/5">
            <table className="w-full text-sm"><thead className="bg-white/[0.03] text-xs text-muted-foreground"><tr><th className="px-3 py-2 text-left">Engine</th><th className="px-3 py-2 text-right">Speed</th><th className="px-3 py-2 text-right">A 20-hour video takes about</th></tr></thead>
              <tbody>{rows.map((r) => (
                <tr key={r.engine} className="border-t border-white/5"><td className="px-3 py-2">{r.label} {r.x_realtime === best && rows.length > 1 && <Badge variant="success" className="ml-1">fastest</Badge>}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{r.x_realtime}× real time</td><td className="px-3 py-2 text-right tabular-nums">{fmtMin(r.minutes_for_20h)}</td></tr>))}</tbody></table>
          </div>
        )}
        <p className="text-xs text-muted-foreground">Models download once from Hugging Face on first use, then everything runs offline. Short samples vary a little; real videos with silences are usually faster. For Hindi, “small” or larger is strongly recommended.{sys ? ` FFmpeg: ${sys.ffmpeg ? "found" : "missing"}. Face detection: ${sys.opencv ? "available" : "missing"}.` : ""}</p>
      </CardContent>
    </Card>
  );
}
