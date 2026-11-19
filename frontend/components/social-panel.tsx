"use client";
import { useState } from "react";
import { Copy, Check, Sparkles, Loader2 } from "lucide-react";
import { api, Clip } from "@/lib/api";
import { Button, Notice, Tabs } from "@/components/ui";

function CopyBtn({ text, label = "Copy" }: { text: string; label?: string }) {
  const [ok, setOk] = useState(false);
  return <Button size="sm" variant="ghost" onClick={async () => { try { await navigator.clipboard.writeText(text); setOk(true); setTimeout(() => setOk(false), 1500); } catch {} }}>{ok ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}{label}</Button>;
}
const Row = ({ title, text }: { title?: string; text: string }) => (
  <div className="flex items-start justify-between gap-2 rounded-md border p-2.5 text-sm"><div className="min-w-0 whitespace-pre-wrap">{title && <div className="mb-0.5 text-[11px] uppercase tracking-wide text-muted-foreground">{title}</div>}{text}</div><CopyBtn text={text} label="" /></div>
);

export function SocialPanel({ clip, onChange }: { clip: Clip; onChange: (s: any) => void }) {
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [tab, setTab] = useState<"general" | "yt" | "ig">("general");
  const s = clip.social;
  const gen = async () => { setBusy(true); setErr(""); try { onChange(await api(`/clips/${clip.id}/social`, { method: "POST" })); } catch (e: any) { setErr(e.message); } setBusy(false); };
  const all = s ? [`TITLES\n${s.titles.join("\n")}`, `CAPTIONS\n${s.captions.join("\n\n")}`, `HASHTAGS\n${s.hashtags.join(" ")}`, `DESCRIPTION\n${s.description}`, `THUMBNAIL TEXT\n${s.thumbnail_text}`, `PINNED COMMENT\n${s.pinned_comment}`].join("\n\n") : "";
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Button onClick={gen} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}{s ? "Regenerate" : "Generate social content"}</Button>
        {s && <CopyBtn text={all} label="Copy everything" />}
      </div>
      {s && <p className="text-xs text-muted-foreground">Written by: {s.engine === "template" ? "built-in templates (connect an AI provider in AI Settings for tailored copy)" : s.engine}.</p>}
      {s?.note && <Notice kind="warn">{s.note}</Notice>}
      {err && <Notice kind="error">{err}</Notice>}
      {s && (<>
        <Tabs value={tab} onChange={setTab} tabs={[{ id: "general", label: "All" }, { id: "yt", label: "YouTube Shorts" }, { id: "ig", label: "Instagram Reels" }]} />
        {tab === "general" && <div className="space-y-2">
          <h4 className="text-xs font-semibold">5 title ideas</h4>{s.titles.map((t: string, i: number) => <Row key={i} text={t} />)}
          <h4 className="pt-2 text-xs font-semibold">3 caption variations</h4>{s.captions.map((t: string, i: number) => <Row key={i} text={t} />)}
          <Row title="Hashtags" text={s.hashtags.join(" ")} /><Row title="Description" text={s.description} /><Row title="Thumbnail text" text={s.thumbnail_text} /><Row title="Pinned comment" text={s.pinned_comment} />
        </div>}
        {tab === "yt" && <div className="space-y-2"><Row title="Title (max 100 chars)" text={s.youtube_shorts.title} /><Row title="Description" text={s.youtube_shorts.description} /><Row title="Hashtags (3–5 work best)" text={(s.youtube_shorts.hashtags || []).join(" ")} /></div>}
        {tab === "ig" && <div className="space-y-2"><Row title="Caption" text={s.instagram_reels.caption} /><Row title="Hashtags" text={(s.instagram_reels.hashtags || []).join(" ")} /></div>}
      </>)}
    </div>
  );
}
