"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Trash2, Pencil, Plus } from "lucide-react";
import { api, url, Project } from "@/lib/api";
import { Button, Card, Input, Notice, PageHeader } from "@/components/ui";
import { StatusBadge } from "@/components/status-badge";
import { fmtTime, timeAgo } from "@/lib/utils";
import { TiltCard } from "@/components/fx";
import { PageLoader } from "@/components/loader";

export default function Projects() {
  const [list, setList] = useState<Project[] | null>(null);
  const [err, setErr] = useState("");
  const [renaming, setRenaming] = useState<string | null>(null);
  const [name, setName] = useState("");
  const load = () => api<{ projects: Project[] }>("/projects").then((r) => setList(r.projects)).catch((e) => setErr(e.message));
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, []);
  const del = async (p: Project) => {
    if (!confirm(`Delete “${p.name}” and all of its clips and exports? This cannot be undone.`)) return;
    try { await api(`/projects/${p.id}`, { method: "DELETE" }); load(); } catch (e: any) { setErr(e.message); }
  };
  const rename = async (p: Project) => { try { await api(`/projects/${p.id}`, { method: "PATCH", body: { name } }); setRenaming(null); load(); } catch (e: any) { setErr(e.message); } };
  return (
    <div>
      <PageHeader title="My Projects" subtitle="Every video you process becomes a project you can reopen, edit and export again."
        actions={<Link href="/create"><Button><Plus className="h-4 w-4" />New project</Button></Link>} />
      {err && <div className="mb-4"><Notice kind="error">{err}</Notice></div>}
      {!list && !err && <PageLoader label="Loading your projects" />}
      {list && !list.length && <Card className="p-10 text-center text-sm text-muted-foreground">No projects yet.</Card>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {list?.map((p) => (
          <TiltCard key={p.id} strength={5}><div className="overflow-hidden">
            <Link href={`/projects/${p.id}`}>
              <div className="aspect-video bg-muted">{p.thumb_url && <img src={url(p.thumb_url)} alt="" className="h-full w-full object-cover" />}</div>
            </Link>
            <div className="space-y-2 p-3">
              {renaming === p.id ? (
                <div className="flex gap-2"><Input value={name} onChange={(e) => setName(e.target.value)} autoFocus onKeyDown={(e) => e.key === "Enter" && rename(p)} /><Button size="sm" onClick={() => rename(p)}>Save</Button></div>
              ) : (
                <div className="flex items-start justify-between gap-2">
                  <Link href={`/projects/${p.id}`} className="line-clamp-2 text-sm font-medium hover:text-primary">{p.name}</Link>
                  <div className="flex shrink-0 gap-1">
                    <Button size="icon" variant="ghost" title="Rename" onClick={() => { setRenaming(p.id); setName(p.name); }}><Pencil className="h-3.5 w-3.5" /></Button>
                    <Button size="icon" variant="ghost" title="Delete" onClick={() => del(p)}><Trash2 className="h-3.5 w-3.5" /></Button>
                  </div>
                </div>
              )}
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{p.clip_count ?? 0} clips · {p.export_count ?? 0} exports{p.meta?.duration ? ` · ${fmtTime(p.meta.duration)}` : ""}</span><StatusBadge status={p.status} />
              </div>
              <div className="text-xs text-muted-foreground">{p.source_type === "youtube" ? "YouTube" : p.source_type === "live" ? "Live recording" : "Upload"} · {timeAgo(p.created_at)}</div>
            </div>
          </div></TiltCard>
        ))}
      </div>
    </div>
  );
}
