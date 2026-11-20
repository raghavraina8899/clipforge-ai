"use client";
import { useEffect, useRef, useState } from "react";
import { Check, Film, ImageIcon, Plus, Trash2, Upload, X } from "lucide-react";
import { api, BrandKit, upload, url } from "@/lib/api";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Label, Notice, PageHeader, Slider } from "@/components/ui";
import { PageLoader } from "@/components/loader";
import { PresetGallery, StyleSample } from "@/components/caption-editor";
import { cn } from "@/lib/utils";

const POS = [["tl", "tc", "tr"], ["bl", "bc", "br"]];
const newKit = (): BrandKit => ({ id: Math.random().toString(36).slice(2, 10), name: "My channel", logo: { file: "", pos: "tr", size: 0.18, opacity: 1, margin: 0.04 }, intro: { file: "" }, outro: { file: "" }, caption: null });

export default function Brand() {
  const [kits, setKits] = useState<BrandKit[] | null>(null);
  const [def, setDef] = useState("");
  const [sel, setSel] = useState<string>("");
  const [err, setErr] = useState(""); const [msg, setMsg] = useState(""); const [busy, setBusy] = useState("");
  const [dirty, setDirty] = useState(false);
  useEffect(() => { api<{ brands: BrandKit[]; default: string }>("/brand").then((r) => { setKits(r.brands); setDef(r.default); setSel(r.brands[0]?.id || ""); }).catch((e) => setErr(e.message)); }, []);
  if (!kits) return err ? <Notice kind="error">{err}</Notice> : <PageLoader label="Loading your brand kits" />;
  const kit = kits.find((k) => k.id === sel) || null;
  const edit = (p: Partial<BrandKit> | ((k: BrandKit) => BrandKit)) => { setKits(kits.map((k) => (k.id === sel ? (typeof p === "function" ? p(k) : { ...k, ...p }) : k))); setDirty(true); setMsg(""); };
  const save = async () => {
    setBusy("save"); setErr("");
    try { const r = await api<{ brands: BrandKit[]; default: string }>("/brand", { method: "PUT", body: { brands: kits, default: def } }); setKits(r.brands); setDef(r.default); setDirty(false); setMsg("Saved."); } catch (e: any) { setErr(e.message); }
    setBusy("");
  };
  const add = () => { const k = newKit(); setKits([...kits, k]); setSel(k.id); setDirty(true); };
  const remove = () => { if (!kit || !confirm(`Delete the brand kit “${kit.name}”? Its uploaded logo, intro and outro files are removed too.`)) return; const rest = kits.filter((k) => k.id !== kit.id); setKits(rest); setSel(rest[0]?.id || ""); if (def === kit.id) setDef(""); setDirty(true); };
  const up = async (kind: "logo" | "intro" | "outro", f?: File) => {
    if (!f || !kit) return;
    setBusy(kind); setErr("");
    try {
      const r = await upload<{ file: string }>(`/brand/upload?kind=${kind}&filename=${encodeURIComponent(f.name)}`, f, () => {}).promise;
      edit((k) => (kind === "logo" ? { ...k, logo: { ...k.logo, file: r.file } } : { ...k, [kind]: { file: r.file } }));
    } catch (e: any) { setErr(e.message); }
    setBusy("");
  };
  const fileLabel = (f: string) => f.replace(/^[0-9a-f]{8}_/, "");
  return (
    <div>
      <PageHeader title="Brand kit" subtitle="Your logo, an intro and outro, and a caption style, saved per channel. Pick a kit on any clip. Everything here is a file you upload; nothing is added automatically."
        actions={<div className="flex gap-2"><Button variant="secondary" onClick={add}><Plus className="h-4 w-4" />New kit</Button><Button onClick={save} disabled={!dirty || !!busy}>{msg ? <><Check className="h-4 w-4" />Saved</> : "Save changes"}</Button></div>} />
      {err && <div className="mb-4"><Notice kind="error">{err}</Notice></div>}
      {!kits.length && <Card className="p-10 text-center text-sm text-muted-foreground">No brand kits yet. Create one to add your logo and intro/outro to clips.<div className="mt-3"><Button onClick={add}><Plus className="h-4 w-4" />Create your first kit</Button></div></Card>}
      {kits.length > 0 && kit && (
        <div className="grid items-start gap-6 xl:grid-cols-[260px_minmax(0,1fr)_300px]">
          <div className="space-y-2">
            {kits.map((k) => (
              <button key={k.id} onClick={() => setSel(k.id)} className={cn("w-full rounded-lg border p-3 text-left transition", k.id === sel ? "border-primary bg-primary/10" : "border-white/5 hover:border-primary/40")}>
                <div className="flex items-center justify-between gap-2 text-sm font-medium"><span className="truncate">{k.name}</span>{def === k.id && <Badge variant="primary">default</Badge>}</div>
                <div className="mt-1 text-xs text-muted-foreground">{[k.logo.file && "logo", k.intro.file && "intro", k.outro.file && "outro", k.caption && "captions"].filter(Boolean).join(" · ") || "empty"}</div>
              </button>
            ))}
          </div>
          <div className="space-y-5">
            <Card><CardContent className="space-y-4 p-5">
              <div><Label>Kit name</Label><Input value={kit.name} onChange={(e) => edit({ name: e.target.value })} /></div>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={def === kit.id} onChange={(e) => { setDef(e.target.checked ? kit.id : ""); setDirty(true); }} />Use this kit for new clips</label>
            </CardContent></Card>
            <Card><CardHeader><CardTitle className="flex items-center gap-2"><ImageIcon className="h-4 w-4 text-cyan" />Logo</CardTitle></CardHeader><CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-gradient-to-b from-[hsl(225_21%_21%)] to-[hsl(225_22%_15%)] px-3 py-2 text-sm"><Upload className="h-4 w-4" />{busy === "logo" ? "Uploading…" : kit.logo.file ? "Replace logo" : "Upload logo"}
                  <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => up("logo", e.target.files?.[0])} /></label>
                {kit.logo.file && <><span className="text-xs text-muted-foreground">{fileLabel(kit.logo.file)}</span><button className="text-xs text-muted-foreground underline" onClick={() => edit((k) => ({ ...k, logo: { ...k.logo, file: "" } }))}>Remove</button></>}
              </div>
              <p className="text-xs text-muted-foreground">PNG with a transparent background looks best. Use a logo you own.</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <div><Label>Position</Label><div className="grid w-40 grid-cols-3 gap-1">{POS.flat().map((p) => <button key={p} onClick={() => edit((k) => ({ ...k, logo: { ...k.logo, pos: p } }))} className={cn("h-8 rounded border text-[10px]", kit.logo.pos === p ? "border-primary bg-primary/20" : "border-input")}>{p.toUpperCase()}</button>)}</div></div>
                <div className="space-y-3">
                  <Slider label="Size (of video width)" value={kit.logo.size * 100} min={4} max={60} step={1} suffix="%" onChange={(v) => edit((k) => ({ ...k, logo: { ...k.logo, size: v / 100 } }))} />
                  <Slider label="Opacity" value={kit.logo.opacity * 100} min={10} max={100} step={5} suffix="%" onChange={(v) => edit((k) => ({ ...k, logo: { ...k.logo, opacity: v / 100 } }))} />
                  <Slider label="Margin" value={kit.logo.margin * 100} min={0} max={20} step={1} suffix="%" onChange={(v) => edit((k) => ({ ...k, logo: { ...k.logo, margin: v / 100 } }))} />
                </div>
              </div>
            </CardContent></Card>
            {(["intro", "outro"] as const).map((kind) => (
              <Card key={kind}><CardHeader><CardTitle className="flex items-center gap-2"><Film className="h-4 w-4 text-cyan" />{kind === "intro" ? "Intro" : "Outro"}</CardTitle></CardHeader><CardContent className="space-y-2">
                <div className="flex flex-wrap items-center gap-3">
                  <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-gradient-to-b from-[hsl(225_21%_21%)] to-[hsl(225_22%_15%)] px-3 py-2 text-sm"><Upload className="h-4 w-4" />{busy === kind ? "Uploading…" : kit[kind].file ? `Replace ${kind}` : `Upload ${kind}`}
                    <input type="file" accept="video/*,image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => up(kind, e.target.files?.[0])} /></label>
                  {kit[kind].file && <><span className="text-xs text-muted-foreground">{fileLabel(kit[kind].file)}</span><button className="text-xs text-muted-foreground underline" onClick={() => edit((k) => ({ ...k, [kind]: { file: "" } }))}><X className="inline h-3 w-3" /> Remove</button></>}
                </div>
                <p className="text-xs text-muted-foreground">A short video (up to 30 s, any size: it is fitted to the clip) or a still image shown for 2.5 s. It plays {kind === "intro" ? "before" : "after"} every clip that uses this kit. Exporting takes a little longer.</p>
              </CardContent></Card>
            ))}
            <Card><CardHeader><CardTitle>Caption style for this channel</CardTitle></CardHeader><CardContent className="space-y-3">
              {kit.caption ? <div className="flex items-center gap-3"><div className="w-48"><StyleSample style={kit.caption} text="Make every word" className="h-16" /></div><Button variant="ghost" size="sm" onClick={() => edit({ caption: null })}>Clear</Button></div> : <p className="text-sm text-muted-foreground">No caption style saved. Pick one below, then use “Use this kit's caption style” on any clip.</p>}
              <PresetGallery value={kit.caption?.preset || ""} onPick={(p) => edit({ caption: { ...p.style, preset: p.id } })} />
              <p className="text-xs text-muted-foreground">Fine-tune colours and fonts in Subtitle Styles or on a clip; this saves the preset.</p>
            </CardContent></Card>
            <div><Button variant="danger" onClick={remove}><Trash2 className="h-4 w-4" />Delete this kit</Button></div>
          </div>
          <div className="xl:sticky xl:top-6">
            <Card><CardHeader><CardTitle>Preview</CardTitle></CardHeader><CardContent>
              <div className="relative mx-auto aspect-[9/16] w-44 overflow-hidden rounded-xl border border-white/10 bg-gradient-to-br from-slate-600 via-slate-700 to-slate-900 shadow-[0_20px_40px_-20px_hsl(0_0%_0%/.8)]">
                {kit.logo.file && <img src={url(`/api/brand/file/${kit.logo.file}`)} alt="" className="absolute object-contain" style={{
                  width: `${kit.logo.size * 100}%`, opacity: kit.logo.opacity,
                  ...(kit.logo.pos.startsWith("t") ? { top: `${kit.logo.margin * 100 * 0.56}%` } : { bottom: `${kit.logo.margin * 100 * 0.56}%` }),
                  ...(kit.logo.pos.endsWith("l") ? { left: `${kit.logo.margin * 100}%` } : kit.logo.pos.endsWith("r") ? { right: `${kit.logo.margin * 100}%` } : { left: "50%", transform: "translateX(-50%)" }) }} />}
                <div className="absolute inset-x-0 top-[62%] text-center text-[10px] font-extrabold uppercase text-white [text-shadow:0_1px_3px_#000]">Sample caption</div>
              </div>
              <p className="mt-3 text-center text-xs text-muted-foreground">Approximate layout of your logo on a vertical clip.</p>
            </CardContent></Card>
          </div>
        </div>
      )}
    </div>
  );
}
