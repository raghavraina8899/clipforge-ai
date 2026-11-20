"use client";
import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { api, CaptionStyle, useFonts } from "@/lib/api";
import { CaptionControls, PresetGallery, StyleSample } from "@/components/caption-editor";
import { Button, Card, CardContent, CardHeader, CardTitle, Notice, PageHeader } from "@/components/ui";

import { PageLoader } from "@/components/loader";

export default function Styles() {
  const fonts = useFonts();
  const [style, setStyle] = useState<CaptionStyle | null>(null);
  const [saved, setSaved] = useState(false); const [err, setErr] = useState("");
  useEffect(() => { api<any>("/settings").then((s) => api<any>("/presets").then((p) => {
    const base = p.presets.find((x: any) => x.id === (s.caption.preset || "hormozi"))?.style || {};
    setStyle({ ...base, ...s.caption });
  })).catch((e) => setErr(e.message)); }, []);
  const save = async () => { try { await api("/settings", { method: "PUT", body: { caption: style } }); setSaved(true); setTimeout(() => setSaved(false), 2000); } catch (e: any) { setErr(e.message); } };
  if (!style) return err ? <Notice kind="error">{err}</Notice> : <PageLoader label="Loading subtitle styles" />;
  return (
    <div>
      <PageHeader title="Subtitle Styles" subtitle="Choose the look new clips start with. You can still change the style of any individual clip in its editor." actions={<Button onClick={save}>{saved ? <><Check className="h-4 w-4" />Saved</> : "Save as default"}</Button>} />
      {err && <div className="mb-4"><Notice kind="error">{err}</Notice></div>}
      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <Card><CardHeader><CardTitle>Presets</CardTitle></CardHeader><CardContent>
          <PresetGallery value={style.preset} onPick={(p) => setStyle({ ...p.style, preset: p.id })} /></CardContent></Card>
        <div className="space-y-6">
          <Card><CardHeader><CardTitle>Live preview</CardTitle></CardHeader><CardContent><StyleSample style={style} text="Make every single word count" className="h-32" />
            <p className="mt-2 text-xs text-muted-foreground">Fonts are free (open-source) or already on your computer. Exports render with the same font and timing.</p></CardContent></Card>
          <Card><CardHeader><CardTitle>Customize</CardTitle></CardHeader><CardContent><CaptionControls style={style} fonts={fonts} onChange={(p) => setStyle({ ...style, ...p, preset: "custom" in p ? "custom" : style.preset })} /></CardContent></Card>
        </div>
      </div>
    </div>
  );
}
