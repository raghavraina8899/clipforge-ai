"use client";
import { Input, Label } from "@/components/ui";
import { cn } from "@/lib/utils";

export const DURATIONS = [
  { id: "15-30", label: "15–30 s", min: 15, max: 30 }, { id: "30-45", label: "30–45 s", min: 30, max: 45 },
  { id: "45-60", label: "45–60 s", min: 45, max: 60 }, { id: "60-90", label: "60–90 s", min: 60, max: 90 },
  { id: "custom", label: "Custom", min: 0, max: 0 },
];
export type DurationValue = { preset: string; min: number; max: number };
export const defaultDuration: DurationValue = { preset: "45-60", min: 45, max: 60 };

export function DurationPicker({ value, onChange }: { value: DurationValue; onChange: (v: DurationValue) => void }) {
  return (
    <div>
      <Label>Clip length</Label>
      <div className="flex flex-wrap gap-2">
        {DURATIONS.map((d) => (
          <button key={d.id} type="button" onClick={() => onChange(d.id === "custom" ? { preset: "custom", min: value.min, max: value.max } : { preset: d.id, min: d.min, max: d.max })}
            className={cn("rounded-md border px-3 py-1.5 text-sm transition-colors", value.preset === d.id ? "border-primary bg-primary/15 text-primary" : "border-input text-muted-foreground hover:text-foreground")}>
            {d.label}
          </button>
        ))}
      </div>
      {value.preset === "custom" && (
        <div className="mt-2 flex items-center gap-2">
          <Input type="number" min={5} max={170} className="w-24" value={value.min} onChange={(e) => onChange({ ...value, min: Number(e.target.value) })} />
          <span className="text-sm text-muted-foreground">to</span>
          <Input type="number" min={6} max={180} className="w-24" value={value.max} onChange={(e) => onChange({ ...value, max: Number(e.target.value) })} />
          <span className="text-sm text-muted-foreground">seconds</span>
        </div>
      )}
    </div>
  );
}
