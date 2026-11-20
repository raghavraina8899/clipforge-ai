"use client";
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 disabled:pointer-events-none disabled:opacity-50 active:translate-y-px",
  {
    variants: {
      variant: {
        default: "text-white bg-gradient-to-b from-[hsl(211_100%_64%)] to-[hsl(215_100%_50%)] shadow-[inset_0_1px_0_hsl(0_0%_100%/.28),0_8px_18px_-8px_hsl(211_100%_55%/.8)] hover:-translate-y-px hover:brightness-110 hover:shadow-[inset_0_1px_0_hsl(0_0%_100%/.3),0_12px_24px_-8px_hsl(211_100%_55%)]",
        secondary: "text-foreground bg-gradient-to-b from-[hsl(225_21%_21%)] to-[hsl(225_22%_15%)] border border-white/[0.06] shadow-[inset_0_1px_0_hsl(0_0%_100%/.07),0_6px_14px_-8px_hsl(0_0%_0%/.8)] hover:-translate-y-px hover:border-primary/40",
        outline: "border border-input bg-card/40 backdrop-blur hover:border-primary/50 hover:bg-accent",
        ghost: "hover:bg-accent",
        danger: "bg-danger/15 text-danger border border-danger/20 hover:bg-danger/25",
      },
      size: { default: "h-9 px-4", sm: "h-8 px-3 text-xs", lg: "h-11 px-6 text-base", icon: "h-8 w-8" },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, ...p }, ref) => (
  <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...p} />
));
Button.displayName = "Button";

export const Card = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("surface rounded-xl", className)} {...p} />
);
export const CardHeader = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => <div className={cn("flex flex-col gap-1 p-4 pb-2", className)} {...p} />;
export const CardTitle = ({ className, ...p }: React.HTMLAttributes<HTMLHeadingElement>) => <h3 className={cn("text-sm font-semibold", className)} {...p} />;
export const CardContent = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => <div className={cn("p-4 pt-2", className)} {...p} />;

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input ref={ref} className={cn("h-9 w-full rounded-md border border-input bg-background/70 px-3 text-sm shadow-[inset_0_1px_2px_hsl(0_0%_0%/.4)] placeholder:text-muted-foreground transition focus-visible:border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-50", className)} {...p} />
));
Input.displayName = "Input";
export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => (
  <textarea ref={ref} className={cn("w-full rounded-md border border-input bg-background/70 px-3 py-2 text-sm shadow-[inset_0_1px_2px_hsl(0_0%_0%/.4)] placeholder:text-muted-foreground focus-visible:border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40", className)} {...p} />
));
Textarea.displayName = "Textarea";

export const Select = ({ className, ...p }: React.SelectHTMLAttributes<HTMLSelectElement>) => (
  <select className={cn("h-9 w-full rounded-md border border-input bg-background/70 px-2 text-sm shadow-[inset_0_1px_2px_hsl(0_0%_0%/.4)] focus-visible:border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40", className)} {...p} />
);

export const Label = ({ className, ...p }: React.LabelHTMLAttributes<HTMLLabelElement>) => <label className={cn("mb-1 block text-xs font-medium text-muted-foreground", className)} {...p} />;

const badgeV = cva("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", {
  variants: { variant: { default: "bg-muted text-foreground", primary: "bg-primary/20 text-primary", success: "bg-success/20 text-success", warning: "bg-warning/20 text-warning", danger: "bg-danger/20 text-danger" } },
  defaultVariants: { variant: "default" },
});
export const Badge = ({ className, variant, ...p }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeV>) => <span className={cn(badgeV({ variant }), className)} {...p} />;

export const Progress = ({ value, className }: { value: number; className?: string }) => (
  <div className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)} role="progressbar" aria-valuenow={Math.round(value)}>
    <div className="relative h-full overflow-hidden rounded-full bg-gradient-to-r from-primary to-cyan shadow-[0_0_14px_hsl(var(--primary)/.6)] transition-all duration-500" style={{ width: `${Math.max(2, Math.min(100, value))}%` }}>
      <span className="absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-white/40 to-transparent" />
    </div>
  </div>
);

export const Switch = ({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) => (
  <label className="flex cursor-pointer items-center justify-between gap-3 text-sm">
    {label && <span>{label}</span>}
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
      className={cn("relative h-5 w-9 shrink-0 rounded-full transition-all", checked ? "bg-gradient-to-r from-primary to-cyan shadow-[0_0_12px_hsl(var(--primary)/.55)]" : "bg-input")}>
      <span className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all", checked ? "left-[18px]" : "left-0.5")} />
    </button>
  </label>
);

export const Slider = ({ label, value, min, max, step, onChange, suffix = "" }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; suffix?: string }) => (
  <div>
    <div className="mb-1 flex justify-between text-xs text-muted-foreground"><span>{label}</span><span className="tabular-nums text-foreground">{Number(value).toFixed(step < 1 ? (step < 0.1 ? 2 : 1) : 0)}{suffix}</span></div>
    <input type="range" className="w-full" min={min} max={max} step={step} value={value} onChange={(e) => onChange(parseFloat(e.target.value))} />
  </div>
);

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; icon?: React.ReactNode }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="flex flex-wrap gap-1 rounded-lg border border-white/5 bg-muted/70 p-1 shadow-[inset_0_1px_2px_hsl(0_0%_0%/.4)]">
      {tabs.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)}
          className={cn("flex items-center gap-1.5 whitespace-nowrap rounded px-3 py-1.5 text-xs font-medium transition-colors", value === t.id ? "bg-gradient-to-b from-[hsl(225_22%_22%)] to-[hsl(225_24%_17%)] text-foreground shadow-[inset_0_1px_0_hsl(0_0%_100%/.08),0_4px_10px_-4px_hsl(0_0%_0%/.7)]" : "text-muted-foreground hover:text-foreground")}>
          {t.icon}{t.label}
        </button>
      ))}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="text-[1.65rem] font-semibold tracking-tight"><span className="text-gradient">{title}</span></h1>{subtitle && <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{subtitle}</p>}</div>
      {actions}
    </div>
  );
}

export function Notice({ kind = "info", children }: { kind?: "info" | "warn" | "error" | "ok"; children: React.ReactNode }) {
  const c = { info: "border-primary/30 bg-primary/10", warn: "border-warning/30 bg-warning/10", error: "border-danger/30 bg-danger/10", ok: "border-success/30 bg-success/10" }[kind];
  return <div className={cn("rounded-lg border px-3 py-2.5 text-sm shadow-[inset_0_1px_0_hsl(0_0%_100%/.05)]", c)}>{children}</div>;
}

export function JobBar({ job, onCancel }: { job: { stage: string; progress: number; message: string | null; status: string; error: string | null } | null; onCancel?: () => void }) {
  if (!job) return null;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm"><span className="font-medium">{job.stage}</span><span className="tabular-nums text-muted-foreground">{Math.round(job.progress)}%</span></div>
      <Progress value={job.progress} />
      <div className="flex items-center justify-between text-xs text-muted-foreground"><span>{job.message}</span>{onCancel && ["queued", "running"].includes(job.status) && <button onClick={onCancel} className="underline hover:text-foreground">Cancel</button>}</div>
    </div>
  );
}

export const scoreColor = (s: number) => (s >= 70 ? "text-success" : s >= 50 ? "text-warning" : "text-muted-foreground");
