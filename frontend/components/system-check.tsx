"use client";
import { useState } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Loader2, Copy, Check, Stethoscope } from "lucide-react";
import { API, api } from "@/lib/api";
import { Button, Card, CardContent, CardHeader, CardTitle } from "@/components/ui";

interface C { id: string; name: string; level: "ok" | "warn" | "error"; detail: string; fix: string }

export function SystemCheck() {
  const [checks, setChecks] = useState<C[] | null>(null);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [copied, setCopied] = useState(false);
  const run = async () => { setBusy(true); setErr(""); try { setChecks((await api<{ checks: C[] }>("/doctor")).checks); } catch (e: any) { setErr(e.message); } setBusy(false); };
  const copy = async () => {
    try { const t = await (await fetch(`${API}/api/doctor/report`)).text(); await navigator.clipboard.writeText(t); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { setErr("Could not copy the report."); }
  };
  const icon = (l: string) => l === "ok" ? <CheckCircle2 className="h-4 w-4 shrink-0 text-success" /> : l === "warn" ? <AlertTriangle className="h-4 w-4 shrink-0 text-warning" /> : <XCircle className="h-4 w-4 shrink-0 text-danger" />;
  const bad = checks?.filter((c) => c.level === "error").length ?? 0;
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><Stethoscope className="h-4 w-4" />System check</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">Something not working? Run this. It checks FFmpeg, captions, speech recognition, YouTube support, disk space and internet, and says how to fix anything it finds.</p>
        <div className="flex flex-wrap gap-2">
          <Button onClick={run} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Stethoscope className="h-4 w-4" />}Run system check</Button>
          <Button variant="secondary" onClick={copy}>{copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}Copy diagnostic report</Button>
        </div>
        <p className="text-xs text-muted-foreground">The report (system info, check results, last log lines; no API keys) is what to send whoever is helping you.</p>
        {err && <p className="text-sm text-danger">{err}</p>}
        {checks && (
          <>
            <p className={`text-sm font-medium ${bad ? "text-danger" : "text-success"}`}>{bad ? `${bad} problem(s) need fixing before Frameflow works.` : "Everything essential looks fine."}</p>
            <ul className="space-y-2">
              {checks.map((c) => (
                <li key={c.id} className="flex items-start gap-2 text-sm">{icon(c.level)}<div className="min-w-0"><div>{c.name} <span className="text-muted-foreground">· {c.detail}</span></div>{c.fix && <div className="text-xs text-warning">→ {c.fix}</div>}</div></li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}
