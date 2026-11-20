"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Download, FileText } from "lucide-react";
import { api, Clip, url } from "@/lib/api";
import { Badge, Button, Card, Notice, PageHeader, scoreColor } from "@/components/ui";
import { fmtBytes, fmtTime, timeAgo } from "@/lib/utils";
import { PageLoader } from "@/components/loader";

export default function Library() {
  const [clips, setClips] = useState<Clip[] | null>(null); const [err, setErr] = useState(""); const [only, setOnly] = useState(true);
  useEffect(() => { api<{ clips: Clip[] }>("/clips").then((r) => setClips(r.clips)).catch((e) => setErr(e.message)); }, []);
  const list = (clips || []).filter((c) => !only || c.exports.length);
  return (
    <div>
      <PageHeader title="Clip Library" subtitle="Every clip across all projects. Open a clip to edit it or export it again with different settings."
        actions={<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={only} onChange={(e) => setOnly(e.target.checked)} />Only exported clips</label>} />
      {err && <Notice kind="error">{err}</Notice>}
      {!clips && !err && <PageLoader label="Loading your clips" />}
      {clips && !list.length && <Card className="p-10 text-center text-sm text-muted-foreground">{only ? "No exported clips yet. Render a clip from any project and it will appear here." : "No clips yet."}</Card>}
      <div className="space-y-3">
        {list.map((c) => (
          <Card key={c.id} className="p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <Link href={`/projects/${c.project_id}`} className="text-sm font-medium hover:text-primary">{c.title}</Link>
                <div className="mt-1 text-xs text-muted-foreground">{c.project_name} · {fmtTime(c.start)}–{fmtTime(c.end)} · <span className={scoreColor(c.score)}>score {Math.round(c.score)}</span></div>
              </div>
              <Badge variant="primary">{c.kind}</Badge>
            </div>
            {c.exports.length > 0 && <ul className="mt-3 space-y-1.5">{[...c.exports].reverse().map((e) => (
              <li key={e.file} className="flex items-center justify-between gap-2 text-sm"><span className="text-muted-foreground">{e.width}×{e.height} · {e.fps} fps · {fmtBytes(e.size)} · {timeAgo(e.at)}</span>
                <span className="flex gap-1"><a href={url(e.url)}><Button size="sm" variant="secondary"><Download className="h-3.5 w-3.5" />MP4</Button></a><a href={url(e.srt_url)}><Button size="sm" variant="ghost"><FileText className="h-3.5 w-3.5" />SRT</Button></a></span></li>))}</ul>}
          </Card>
        ))}
      </div>
    </div>
  );
}
