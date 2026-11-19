import { Badge } from "@/components/ui";

export function StatusBadge({ status }: { status: string }) {
  const m: Record<string, [string, any]> = { ready: ["Ready", "success"], processing: ["Processing", "primary"], error: ["Failed", "danger"], needs_video: ["Needs video file", "warning"], new: ["New", "default"] };
  const [l, v] = m[status] || [status, "default"];
  return <Badge variant={v}>{l}</Badge>;
}
