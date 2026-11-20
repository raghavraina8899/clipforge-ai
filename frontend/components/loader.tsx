"use client";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export function Cube({ size = 56, shadow = true }: { size?: number; shadow?: boolean }) {
  return (
    <div className="inline-block" style={{ ["--s" as any]: `${size}px` }}>
      <div className="cube-scene"><div className="cube">
        {["f1", "f2", "f3", "f4", "f5", "f6"].map((f) => <div key={f} className={`face ${f}`} />)}
        <div className="core">{[1, 2, 3, 4, 5, 6].map((i) => <i key={i} />)}</div>
      </div></div>
      {shadow && <div className="cube-shadow" />}
    </div>
  );
}

export function Bar3D({ value, className }: { value: number; className?: string }) {
  const v = Math.max(2, Math.min(100, value));
  return (
    <div className={cn("bar3d", className)} role="progressbar" aria-valuenow={Math.round(v)}>
      <div className="fill" style={{ width: `${v}%` }} />
      <div className="knob" style={{ left: `${v}%` }} />
    </div>
  );
}

/** Film frames stream along a belt into an MP4 that fills as the real progress rises. */
export function FilmExport({ pct }: { pct: number }) {
  return (
    <div className="film-scene">
      <div className="film-belt">{Array.from({ length: 7 }, (_, i) => <span key={i} className="film-frame" style={{ animationDelay: `${-i * 0.34}s` }} />)}</div>
      <div className="film-file">
        <div className="fill" style={{ height: `${Math.max(4, Math.min(100, pct))}%` }} />
        <div className="absolute inset-0 flex flex-col items-center justify-center text-white"><span className="text-sm font-bold tracking-wider drop-shadow">MP4</span><span className="text-[11px] tabular-nums opacity-90">{Math.round(pct)}%</span></div>
      </div>
    </div>
  );
}

function fmtDur(s: number) {
  s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : m ? `${m}m ${String(r).padStart(2, "0")}s` : `${r}s`;
}

/** Elapsed time and a rough remaining-time estimate based on the real progress rate so far. */
function useTiming(progress: number, active: boolean) {
  const start = useRef<number>(Date.now());
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (!active) return; const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, [active]);
  const elapsed = (now - start.current) / 1000;
  const eta = progress >= 4 && elapsed >= 8 && progress < 100 ? (elapsed * (100 - progress)) / progress : null;
  return { elapsed, eta };
}

export interface LoaderJob { stage: string; progress: number; message: string | null; status: string }

export function JobLoader({ job, variant = "process", onCancel, compact = false, title }: { job: LoaderJob | null; variant?: "process" | "export" | "upload"; onCancel?: () => void; compact?: boolean; title?: string }) {
  const active = !!job && ["queued", "running"].includes(job.status);
  const { elapsed, eta } = useTiming(job?.progress ?? 0, active);
  if (!job) return null;
  const p = job.progress;
  const heading = title || (variant === "export" ? "Exporting your clip" : variant === "upload" ? "Uploading" : job.stage);

  if (compact) {
    return (
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <Cube size={16} shadow={false} />
          <span className="min-w-0 flex-1 truncate text-xs">{variant === "export" ? "Exporting" : job.stage}</span>
          <span className="text-xs tabular-nums text-muted-foreground">{Math.round(p)}%</span>
        </div>
        <div className="bar3d !h-1.5"><div className="fill" style={{ width: `${Math.max(2, Math.min(100, p))}%` }} /></div>
        {job.message && <div className="truncate text-[11px] text-muted-foreground">{job.message}</div>}
      </div>
    );
  }
  return (
    <div className="space-y-4 rounded-xl border border-white/5 bg-gradient-to-b from-white/[0.04] to-transparent p-4 shadow-[inset_0_1px_0_hsl(0_0%_100%/.06)]">
      {variant === "export" ? <FilmExport pct={p} /> : (
        <div className="flex items-center gap-5"><Cube size={52} />
          <div className="min-w-0 flex-1"><div className="truncate text-base font-semibold">{heading}</div><div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{job.message || "Working…"}</div></div>
          <div className="text-3xl font-semibold tabular-nums text-gradient">{Math.round(p)}%</div></div>
      )}
      {variant === "export" && <div className="flex items-end justify-between gap-3"><div className="min-w-0"><div className="text-base font-semibold">{heading}</div><div className="line-clamp-2 text-xs text-muted-foreground">{job.message || job.stage}</div></div><div className="text-3xl font-semibold tabular-nums text-gradient">{Math.round(p)}%</div></div>}
      <Bar3D value={p} />
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted-foreground">
        <span>Stage: <b className="text-foreground">{job.stage}</b></span>
        <span>Elapsed: <b className="tabular-nums text-foreground">{fmtDur(elapsed)}</b></span>
        {eta !== null && <span>About <b className="tabular-nums text-foreground">{fmtDur(eta)}</b> left <span className="opacity-70">(estimate)</span></span>}
        {onCancel && active && <button onClick={onCancel} className="ml-auto underline hover:text-foreground">Cancel</button>}
      </div>
    </div>
  );
}

/** Full-area loader shown while a page fetches its data (also after a refresh). Fades in after 150 ms so fast loads do not flash. */
export function PageLoader({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-[55vh] flex-col items-center justify-center gap-6 opacity-0 animate-fade-up" style={{ animationDelay: "150ms" }}>
      <Cube size={72} />
      <div className="text-center">
        <div className="flex items-center justify-center gap-1 text-base font-medium">{label}
          <span className="ml-0.5 inline-flex gap-1">{[0, 1, 2].map((i) => <i key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan" style={{ animationDelay: `${i * 0.15}s` }} />)}</span></div>
        <div className="mx-auto mt-3 h-1.5 w-56 overflow-hidden rounded-full bg-muted shadow-[inset_0_1px_2px_hsl(0_0%_0%/.5)]">
          <div className="h-full w-1/3 animate-[loadbar_1.3s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-primary to-cyan shadow-[0_0_12px_hsl(var(--primary))]" />
        </div>
      </div>
    </div>
  );
}
