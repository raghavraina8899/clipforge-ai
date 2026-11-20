"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { HardDrive, Loader2, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, Card, CardContent, Notice, PageHeader } from "@/components/ui";
import { cn, fmtBytes } from "@/lib/utils";

interface Item { id: string; group: string; project_id: string | null; kind: string; label: string; detail: string; bytes: number; note: string; danger: boolean; busy: boolean }
interface Data { items: Item[]; total: number; disk_free: number; disk_total: number }

export default function Storage() {
  const [d, setD] = useState<Data | null>(null);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [err, setErr] = useState(""); const [msg, setMsg] = useState(""); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { setD(await api<Data>("/storage")); setErr(""); } catch (e: any) { setErr(e.message); } }, []);
  useEffect(() => { load(); }, [load]);

  const groups = useMemo(() => {
    const m = new Map<string, Item[]>();
    d?.items.forEach((i) => m.set(i.group, [...(m.get(i.group) || []), i]));
    return [...m.entries()];
  }, [d]);
  const wholeSel = (pid: string | null) => !!pid && sel.has(`proj:${pid}:project`);
  const effective = (i: Item) => sel.has(i.id) || (i.kind !== "project" && wholeSel(i.project_id));
  const toggle = (i: Item) => setSel((s) => { const n = new Set(s); n.has(i.id) ? n.delete(i.id) : n.add(i.id); return n; });
  const selectable = (d?.items || []).filter((i) => !i.busy);
  const freed = useMemo(() => {
    let total = 0; const whole = new Set([...sel].filter((x) => x.endsWith(":project")).map((x) => x.split(":")[1]));
    d?.items.forEach((i) => { if (!sel.has(i.id)) return; if (i.kind !== "project" && i.project_id && whole.has(i.project_id)) return; total += i.bytes; });
    return total;
  }, [sel, d]);

  const run = async () => {
    const dangerous = (d?.items || []).filter((i) => sel.has(i.id) && i.danger);
    const text = `Delete ${sel.size} selected item(s) and free about ${fmtBytes(freed)}?` + (dangerous.length ? `\n\nThis includes:\n${dangerous.map((i) => `• ${i.label} (${i.group})`).join("\n")}\n\nThese cannot be recovered.` : "") + "\n\nThis cannot be undone.";
    if (!confirm(text)) return;
    setBusy(true); setMsg(""); setErr("");
    try {
      const r = await api<{ freed: number; deleted: number; skipped: { id: string; reason: string }[] }>("/storage/delete", { body: { ids: [...sel] } });
      setMsg(`Freed ${fmtBytes(r.freed)} (${r.deleted} item${r.deleted === 1 ? "" : "s"} deleted).` + (r.skipped.length ? ` Skipped ${r.skipped.length}: ${r.skipped.map((s) => s.reason).join("; ")}` : ""));
      setSel(new Set()); await load();
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  const usedPct = d ? Math.min(100, (d.total / Math.max(1, d.disk_total)) * 100 * 20) : 0;

  return (
    <div>
      <PageHeader title="Storage" subtitle="Everything Frameflow keeps on this computer. Tick what you no longer need and free the space. Nothing is deleted until you confirm."
        actions={<Button variant="outline" onClick={load}><RefreshCw className="h-4 w-4" />Refresh</Button>} />
      {err && <div className="mb-4"><Notice kind="error">{err}</Notice></div>}
      {msg && <div className="mb-4"><Notice kind="ok">{msg}</Notice></div>}
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Card><CardContent className="p-5"><div className="text-xs text-muted-foreground">Used by Frameflow</div><div className="mt-1 text-3xl font-semibold tracking-tight">{d ? fmtBytes(d.total) : "…"}</div></CardContent></Card>
        <Card><CardContent className="p-5"><div className="text-xs text-muted-foreground">Free on this disk</div><div className="mt-1 text-3xl font-semibold tracking-tight">{d ? fmtBytes(d.disk_free) : "…"}</div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-gradient-to-r from-primary to-cyan" style={{ width: `${Math.max(2, usedPct)}%` }} /></div></CardContent></Card>
        <Card className="glow-ring"><CardContent className="p-5"><div className="text-xs text-muted-foreground">Selected to delete</div><div className="mt-1 text-3xl font-semibold tracking-tight text-gradient">{fmtBytes(freed)}</div></CardContent></Card>
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button variant="secondary" size="sm" onClick={() => setSel(new Set(selectable.filter((i) => i.kind !== "project").map((i) => i.id)))}>Select all</Button>
        <Button variant="secondary" size="sm" onClick={() => setSel(new Set(selectable.filter((i) => !i.danger && i.kind !== "model" && i.kind !== "proxy").map((i) => i.id)))}><ShieldCheck className="h-4 w-4" />Select safe items only</Button>
        <Button variant="ghost" size="sm" onClick={() => setSel(new Set())}>Clear</Button>
        <div className="flex-1" />
        <Button variant="danger" disabled={!sel.size || busy} onClick={run}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}Free up {fmtBytes(freed)}</Button>
      </div>
      {d && !d.items.length && <Card className="p-10 text-center text-sm text-muted-foreground">Nothing stored yet.</Card>}
      <div className="space-y-4">
        {groups.map(([g, list]) => (
          <Card key={g}>
            <div className="flex items-center gap-2 border-b border-white/5 px-4 py-3 text-sm font-semibold"><HardDrive className="h-4 w-4 text-cyan" />{g}</div>
            <ul className="divide-y divide-white/5">
              {list.map((i) => {
                const forced = i.kind !== "project" && wholeSel(i.project_id);
                return (
                  <li key={i.id} className={cn("flex items-start gap-3 px-4 py-3 transition-colors hover:bg-white/[0.025]", i.kind === "project" && "bg-white/[0.02]", i.busy && "opacity-50")}>
                    <input type="checkbox" className="mt-1" disabled={i.busy || forced} checked={effective(i)} onChange={() => toggle(i)} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 text-sm font-medium">{i.label}{i.danger && <Badge variant="warning">Not recoverable</Badge>}{i.busy && <Badge variant="primary">in use</Badge>}</div>
                      <div className="text-xs text-muted-foreground">{i.detail}</div>
                      {i.note && <div className="mt-0.5 text-xs text-muted-foreground/80">{i.note}</div>}
                    </div>
                    <div className="shrink-0 text-sm tabular-nums">{fmtBytes(i.bytes)}</div>
                  </li>
                );
              })}
            </ul>
          </Card>
        ))}
      </div>
    </div>
  );
}
