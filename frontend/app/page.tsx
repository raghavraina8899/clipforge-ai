"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Film, Scissors, Download, FolderKanban, Plus, Loader2 } from "lucide-react";
import { api, url, Job, Project } from "@/lib/api";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Notice, PageHeader, Progress } from "@/components/ui";
import { fmtTime, timeAgo } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";

interface Stats { videos: number; projects: number; clips: number; exports: number; recent_projects: Project[]; recent_exports: any[]; active_jobs: Job[] }

export default function Dashboard() {
  const [s, setS] = useState<Stats | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let stop = false;
    const load = async () => {
      try { const d = await api<Stats>("/stats"); if (!stop) { setS(d); setErr(""); } } catch (e: any) { if (!stop) setErr(e.message); }
      if (!stop) setTimeout(load, 3000);
    };
    load();
    return () => { stop = true; };
  }, []);
  const stat = (icon: React.ReactNode, label: string, v: number | undefined) => (
    <Card><CardContent className="flex items-center gap-4 p-5">
      <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/15 text-primary">{icon}</div>
      <div><div className="text-2xl font-semibold tabular-nums">{v ?? "–"}</div><div className="text-xs text-muted-foreground">{label}</div></div>
    </CardContent></Card>
  );
  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Turn long videos into ready-to-post Shorts and Reels. Everything runs on this computer."
        actions={<Link href="/create"><Button size="lg"><Plus className="h-4 w-4" />Quick Create</Button></Link>} />
      {err && <div className="mb-4"><Notice kind="error">{err}</Notice></div>}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stat(<Film className="h-5 w-5" />, "Videos processed", s?.videos)}
        {stat(<Scissors className="h-5 w-5" />, "Clips generated", s?.clips)}
        {stat(<Download className="h-5 w-5" />, "Clips exported", s?.exports)}
        {stat(<FolderKanban className="h-5 w-5" />, "Projects", s?.projects)}
      </div>

      <Card className="mt-6">
        <CardHeader><CardTitle>Processing status</CardTitle></CardHeader>
        <CardContent>
          {!s?.active_jobs.length ? <p className="text-sm text-muted-foreground">Nothing is processing right now.</p> : (
            <div className="space-y-4">
              {s.active_jobs.map((j) => (
                <Link key={j.id} href={`/projects/${j.project_id}`} className="block rounded-md border p-3 hover:bg-accent/50">
                  <div className="mb-2 flex items-center justify-between text-sm"><span className="flex items-center gap-2"><Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />{j.kind === "render" ? "Rendering clip" : j.stage}</span><span className="tabular-nums text-muted-foreground">{Math.round(j.progress)}%</span></div>
                  <Progress value={j.progress} /><p className="mt-1 text-xs text-muted-foreground">{j.message}</p>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Recent projects</CardTitle></CardHeader>
          <CardContent>
            {!s?.recent_projects.length ? <p className="text-sm text-muted-foreground">No projects yet. Start with “Quick Create”.</p> : (
              <ul className="divide-y">
                {s.recent_projects.map((p) => (
                  <li key={p.id}><Link href={`/projects/${p.id}`} className="flex items-center gap-3 py-2.5 hover:text-primary">
                    <div className="h-12 w-20 shrink-0 overflow-hidden rounded bg-muted">{p.thumb_url && <img src={url(p.thumb_url)} alt="" className="h-full w-full object-cover" />}</div>
                    <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{p.name}</div><div className="text-xs text-muted-foreground">{timeAgo(p.created_at)}{p.meta?.duration ? ` · ${fmtTime(p.meta.duration)}` : ""}</div></div>
                    <StatusBadge status={p.status} />
                  </Link></li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Recent exports</CardTitle></CardHeader>
          <CardContent>
            {!s?.recent_exports.length ? <p className="text-sm text-muted-foreground">Exported clips appear here.</p> : (
              <ul className="divide-y">
                {s.recent_exports.map((e, i) => (
                  <li key={i} className="flex items-center justify-between gap-3 py-2.5">
                    <div className="min-w-0"><div className="truncate text-sm font-medium">{e.title}</div><div className="text-xs text-muted-foreground">{e.resolution}p · {timeAgo(e.at)}</div></div>
                    <a href={url(e.url)}><Button size="sm" variant="secondary"><Download className="h-3.5 w-3.5" />Download</Button></a>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
