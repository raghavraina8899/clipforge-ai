"use client";
import { useEffect, useState } from "react";
import { Check, KeyRound, Loader2, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Label, Notice, PageHeader, Select } from "@/components/ui";
import { cn } from "@/lib/utils";

interface Model { id: string; name: string; description: string }

export default function AISettings() {
  const [s, setS] = useState<any>(null); const [sys, setSys] = useState<any>(null);
  const [key, setKey] = useState(""); const [models, setModels] = useState<Model[]>([]); const [lmodels, setLModels] = useState<Model[]>([]);
  const [msg, setMsg] = useState<{ k: "ok" | "error" | "info"; t: string } | null>(null); const [busy, setBusy] = useState("");
  const load = () => api<any>("/settings").then(setS);
  useEffect(() => { load().catch((e) => setMsg({ k: "error", t: e.message })); api("/system").then(setSys).catch(() => {}); }, []);
  const put = async (partial: any) => setS(await api("/settings", { method: "PUT", body: partial }));
  const run = async (name: string, fn: () => Promise<void>) => { setBusy(name); setMsg(null); try { await fn(); } catch (e: any) { setMsg({ k: "error", t: e.message }); } setBusy(""); };
  if (!s) return msg ? <Notice kind="error">{msg.t}</Notice> : null;
  const ai = s.ai;
  const provider = (id: string, title: string, desc: string, disabled = false) => (
    <button disabled={disabled} onClick={() => put({ ai: { provider: id } })} className={cn("rounded-lg border p-3 text-left transition-colors disabled:opacity-50", ai.provider === id ? "border-primary bg-primary/10" : "hover:border-primary/50")}>
      <div className="flex items-center justify-between text-sm font-medium">{title}{ai.provider === id && <Check className="h-4 w-4 text-primary" />}</div><div className="mt-1 text-xs text-muted-foreground">{desc}</div></button>
  );
  const testGemini = () => run("test", async () => { const r = await api<any>("/settings/ai/test", { body: { provider: "gemini" } }); setModels(r.models); setMsg({ k: "ok", t: r.message }); if (!ai.gemini.model && r.models.length) { const pick = r.models.find((m: Model) => /flash/.test(m.id) && !/(lite|image|tts|live|thinking|exp|preview)/.test(m.id)) || r.models[0]; await put({ ai: { gemini: { model: pick.id } } }); } });
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="AI Settings" subtitle="ClipForge works fully offline with its built-in analyzer. Add an AI provider for smarter clip ranking and better titles. Keys stay on this computer." />
      {msg && <div className="mb-4"><Notice kind={msg.k}>{msg.t}</Notice></div>}
      <Card className="mb-6"><CardHeader><CardTitle>Provider for clip analysis and social text</CardTitle></CardHeader><CardContent>
        <div className="grid gap-3 sm:grid-cols-2">
          {provider("builtin", "Built-in analyzer (free)", "Rule-based scoring on the transcript. No key, no internet.")}
          {provider("gemini", "Google Gemini (your key)", "Better ranking and copy. Uses your own API key.")}
          {provider("local", "Local model (Ollama)", "Runs on this computer. Needs Ollama installed.")}
          {provider("future", "More providers", "Planned: other OpenAI-compatible endpoints.", true)}
        </div>
        {ai.provider === "gemini" && !ai.gemini.model && <p className="mt-3 text-xs text-warning">Gemini is selected, but analysis falls back to the built-in analyzer until you add a working key and choose a model.</p>}
      </CardContent></Card>

      <Card className="mb-6"><CardHeader><CardTitle className="flex items-center gap-2"><KeyRound className="h-4 w-4" />Google Gemini</CardTitle></CardHeader><CardContent className="space-y-4">
        <div><Label>API key {ai.gemini.has_key && <Badge variant="success" className="ml-2">saved {ai.gemini.key_hint}</Badge>}</Label>
          <div className="flex gap-2"><Input type="password" autoComplete="off" placeholder={ai.gemini.has_key ? "Enter a new key to replace the saved one" : "Paste your Gemini API key"} value={key} onChange={(e) => setKey(e.target.value)} />
            <Button disabled={!key || !!busy} onClick={() => run("save", async () => { setS(await api("/settings/ai/gemini-key", { method: "PUT", body: { key } })); setKey(""); setMsg({ k: "ok", t: "Key saved on this computer." }); })}>Save</Button></div>
          <p className="mt-1 text-xs text-muted-foreground">Stored in <code>data/settings.json</code> (owner-only permissions), sent only to Google, never to the browser after saving. Get a key at aistudio.google.com.</p></div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={!ai.gemini.has_key || !!busy} onClick={testGemini}>{busy === "test" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}Test key and list models</Button>
          <Button variant="danger" disabled={!ai.gemini.has_key || !!busy} onClick={() => run("rm", async () => { setS(await api("/settings/ai/gemini-key", { method: "DELETE" })); setModels([]); setMsg({ k: "info", t: "Key removed." }); })}><Trash2 className="h-4 w-4" />Remove key</Button>
        </div>
        <div><Label>Model</Label>
          <Select value={ai.gemini.model} onChange={(e) => put({ ai: { gemini: { model: e.target.value } } })} disabled={!ai.gemini.has_key}>
            <option value="">{models.length ? "Choose a model…" : ai.gemini.model ? ai.gemini.model : "Run “Test key” to load models"}</option>
            {ai.gemini.model && !models.some((m) => m.id === ai.gemini.model) && <option value={ai.gemini.model}>{ai.gemini.model}</option>}
            {models.map((m) => <option key={m.id} value={m.id}>{m.id}</option>)}</Select>
          <p className="mt-1 text-xs text-muted-foreground">The list shows exactly the models your key can use.</p></div>
        <Notice kind="info"><b>About quotas:</b> Google offers a free tier for Gemini, but it is rate-limited and the limits differ per model and can change. Heavy use may hit them (ClipForge then tells you and falls back to the built-in analyzer). Check the current limits at ai.google.dev. Using the API is never required.</Notice>
      </CardContent></Card>

      <Card className="mb-6"><CardHeader><CardTitle>Local model (Ollama)</CardTitle></CardHeader><CardContent className="space-y-3">
        <div><Label>Server address</Label><Input value={ai.local.host} onChange={(e) => setS({ ...s, ai: { ...ai, local: { ...ai.local, host: e.target.value } } })} onBlur={() => put({ ai: { local: { host: ai.local.host } } })} /></div>
        <Button variant="secondary" disabled={!!busy} onClick={() => run("l", async () => { const r = await api<any>("/settings/ai/test", { body: { provider: "local" } }); setLModels(r.models); setMsg({ k: "ok", t: r.message }); })}>Find installed models</Button>
        <Select value={ai.local.model} onChange={(e) => put({ ai: { local: { model: e.target.value } } })}><option value="">{lmodels.length ? "Choose a model…" : ai.local.model || "Click “Find installed models”"}</option>{lmodels.map((m) => <option key={m.id} value={m.id}>{m.id} ({m.description})</option>)}</Select>
        <p className="text-xs text-muted-foreground">Small local models can give rougher JSON; ClipForge validates every answer and falls back if it is unusable.</p>
      </CardContent></Card>

      <Card><CardHeader><CardTitle>Speech recognition (faster-whisper, local)</CardTitle></CardHeader><CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div><Label>Model size</Label><Select value={s.transcription.model} onChange={(e) => put({ transcription: { model: e.target.value } })}>
            <option value="tiny">tiny – fastest, rough (≈75 MB)</option><option value="base">base – fast (≈145 MB)</option><option value="small">small – recommended (≈480 MB)</option><option value="medium">medium – accurate, slow (≈1.5 GB)</option><option value="large-v3">large-v3 – best, very slow (≈3 GB)</option></Select></div>
          <div className="text-sm"><Label>Status</Label>{sys ? <div className="space-y-0.5 text-xs"><div>faster-whisper: {sys.whisper ? "installed" : "missing"}</div><div>FFmpeg: {sys.ffmpeg ? "found" : "missing"}</div><div>Face detection (OpenCV): {sys.opencv ? "available" : "missing"}</div></div> : null}</div>
        </div>
        <p className="text-xs text-muted-foreground">The model is downloaded once from Hugging Face on first use, then everything runs offline. For Hindi, “small” or larger is strongly recommended.</p>
      </CardContent></Card>
    </div>
  );
}
