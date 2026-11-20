"use client";
import { useRef, useState } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Loader2, Copy, Check, Stethoscope, RotateCw } from "lucide-react";
import { API, api } from "@/lib/api";
import { Button, Card, CardContent, CardHeader, CardTitle } from "@/components/ui";
import { cn } from "@/lib/utils";

interface Step { id: string; name: string }
interface Result extends Step { ok: boolean; level: "ok" | "warn" | "error"; detail: string; fix: string }
const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));

function Ring({ pct, label, sub, tone }: { pct: number; label: string; sub: string; tone: "run" | "ok" | "warn" | "error" | "idle" }) {
  const R = 52, C = 2 * Math.PI * R;
  const stroke = { run: "url(#rg)", ok: "hsl(var(--success))", warn: "hsl(var(--warning))", error: "hsl(var(--danger))", idle: "hsl(var(--muted))" }[tone];
  return (
    <div className="relative h-36 w-36 shrink-0">
      <svg viewBox="0 0 120 120" className={cn("h-full w-full -rotate-90", tone === "run" && "drop-shadow-[0_0_10px_hsl(var(--primary)/.7)]")}>
        <defs><linearGradient id="rg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#3b9bff" /><stop offset="1" stopColor="#22d3ee" /></linearGradient></defs>
        <circle cx="60" cy="60" r={R} fill="none" stroke="hsl(var(--muted))" strokeWidth="9" />
        <circle cx="60" cy="60" r={R} fill="none" stroke={stroke} strokeWidth="9" strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * (1 - pct / 100)} style={{ transition: "stroke-dashoffset .5s ease, stroke .4s" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center"><div className="text-2xl font-semibold tabular-nums">{label}</div><div className="text-[11px] text-muted-foreground">{sub}</div></div>
    </div>
  );
}

export function SystemCheck() {
  const [steps, setSteps] = useState<Step[]>([]);
  const [res, setRes] = useState<Record<string, Result>>({});
  const [cur, setCur] = useState<string | null>(null);
  const [phase, setPhase] = useState<"idle" | "running" | "done">("idle");
  const [err, setErr] = useState(""); const [copied, setCopied] = useState(false);
  const token = useRef(0);

  const run = async () => {
    const my = ++token.current;
    setErr(""); setRes({}); setPhase("running");
    try {
      const { steps: st } = await api<{ steps: Step[] }>("/doctor/steps");
      setSteps(st);
      for (const s of st) {
        if (token.current !== my) return;
        setCur(s.id);
        // the check really runs now; the minimum pause just keeps each step readable
        const [r] = await Promise.all([api<Result>(`/doctor/run/${s.id}`), pause(420)]);
        setRes((x) => ({ ...x, [s.id]: r }));
      }
      setCur(null); setPhase("done");
    } catch (e: any) { setErr(e.message); setCur(null); setPhase("done"); }
  };
  const copy = async () => {
    try { const t = await (await fetch(`${API}/api/doctor/report`)).text(); await navigator.clipboard.writeText(t); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { setErr("Could not copy the report."); }
  };

  const done = Object.keys(res).length, total = steps.length || 1;
  const list = Object.values(res);
  const bad = list.filter((r) => r.level === "error").length, warn = list.filter((r) => r.level === "warn").length;
  const passed = list.filter((r) => r.ok).length;
  const tone = phase === "idle" ? "idle" : phase === "running" ? "run" : bad ? "error" : warn ? "warn" : "ok";
  const label = phase === "idle" ? "—" : phase === "running" ? `${Math.round((done / total) * 100)}%` : `${passed}/${total}`;
  const sub = phase === "idle" ? "not run yet" : phase === "running" ? `step ${Math.min(done + 1, total)} of ${total}` : bad ? "need fixing" : warn ? "with notes" : "all passed";
  const verdict = phase === "done" ? (bad ? `${bad} problem${bad > 1 ? "s" : ""} must be fixed before HookHunt works.` : warn ? "Everything essential works. A few optional items are worth a look." : "All checks passed. Your system is ready.") : "";

  const icon = (id: string) => {
    const r = res[id];
    if (r) return r.level === "ok" ? <CheckCircle2 className="h-5 w-5 animate-pop text-success" /> : r.level === "warn" ? <AlertTriangle className="h-5 w-5 animate-pop text-warning" /> : <XCircle className="h-5 w-5 animate-pop text-danger" />;
    if (cur === id) return <Loader2 className="h-5 w-5 animate-spin text-cyan" />;
    return <span className="m-1.5 h-2 w-2 rounded-full bg-muted-foreground/30" />;
  };

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><Stethoscope className="h-4 w-4 text-cyan" />System check</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-5">
          <Ring pct={phase === "done" ? (passed / total) * 100 : (done / total) * 100} label={label} sub={sub} tone={tone} />
          <div className="min-w-[220px] flex-1 space-y-3">
            <p className="text-sm text-muted-foreground">Something not working? This tests, one step at a time, everything HookHunt depends on: video tools, captions, speech recognition, YouTube support, disk space and internet. Anything wrong comes with the fix.</p>
            {phase === "running" && cur && <p className="flex items-center gap-2 text-sm font-medium text-cyan"><Loader2 className="h-4 w-4 animate-spin" />Checking: {steps.find((s) => s.id === cur)?.name}…</p>}
            {verdict && <p className={cn("text-sm font-medium", bad ? "text-danger" : warn ? "text-warning" : "text-success")}>{verdict}</p>}
            <div className="flex flex-wrap gap-2">
              <Button onClick={run} disabled={phase === "running"}>{phase === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : phase === "done" ? <RotateCw className="h-4 w-4" /> : <Stethoscope className="h-4 w-4" />}{phase === "done" ? "Run again" : phase === "running" ? "Running…" : "Run system check"}</Button>
              <Button variant="secondary" onClick={copy}>{copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}Copy diagnostic report</Button>
            </div>
          </div>
        </div>
        {err && <p className="text-sm text-danger">{err}</p>}
        {steps.length > 0 && (
          <ul className="space-y-1.5">
            {steps.map((s, i) => {
              const r = res[s.id]; const active = cur === s.id; const shown = r || active;
              return (
                <li key={s.id} className={cn("relative flex items-start gap-3 overflow-hidden rounded-lg border px-3 py-2 text-sm transition-all duration-300",
                  active ? "border-primary/50 bg-primary/10 shadow-[0_0_20px_-6px_hsl(var(--primary)/.6)]" : r ? "border-white/5 bg-white/[0.02] animate-slide-in" : "border-transparent opacity-45")}>
                  {active && <span className="pointer-events-none absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-primary/15 to-transparent" />}
                  <div className="relative mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">{icon(s.id)}</div>
                  <div className="relative min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-3"><span className={cn(shown ? "text-foreground" : "text-muted-foreground")}>{s.name}</span><span className="text-[11px] tabular-nums text-muted-foreground">{String(i + 1).padStart(2, "0")}/{String(steps.length).padStart(2, "0")}</span></div>
                    {r && <div className="text-xs text-muted-foreground">{r.detail}</div>}
                    {r?.fix && <div className="mt-0.5 text-xs text-warning">→ {r.fix}</div>}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <p className="text-xs text-muted-foreground">The copied report (system info, results, last log lines; no API keys) is what to send whoever is helping you.</p>
      </CardContent>
    </Card>
  );
}
