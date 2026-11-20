"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Wand2, FolderKanban, Library, Captions, Sparkles, SlidersHorizontal, Info, HardDrive, Stamp } from "lucide-react";
import { cn } from "@/lib/utils";
import { BRAND } from "@/lib/brand";
import { Logo } from "@/components/fx";

const items = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/create", label: "Create New Clips", icon: Wand2 },
  { href: "/projects", label: "My Projects", icon: FolderKanban },
  { href: "/library", label: "Clip Library", icon: Library },
  { href: "/styles", label: "Subtitle Styles", icon: Captions },
  { href: "/brand", label: "Brand kit", icon: Stamp },
  { href: "/storage", label: "Storage", icon: HardDrive },
  { href: "/settings/ai", label: "AI Settings", icon: Sparkles },
  { href: "/settings/video", label: "Video Settings", icon: SlidersHorizontal },
  { href: "/about", label: "About & Help", icon: Info },
];

const isActive = (path: string, href: string) => (href === "/" ? path === "/" : path.startsWith(href));

export function Sidebar() {
  const path = usePathname() ?? "";
  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-white/5 bg-card/40 p-4 backdrop-blur-xl md:flex">
      <Link href="/" className="group mb-7 flex items-center gap-3 px-2 py-2">
        <span className="transition-transform duration-300 group-hover:rotate-[-6deg] group-hover:scale-110"><Logo /></span>
        <span className="text-lg font-semibold tracking-tight">{BRAND.name}</span>
      </Link>
      <nav className="flex flex-1 flex-col gap-1">
        {items.map((it) => {
          const active = isActive(path, it.href);
          return (
            <Link key={it.href} href={it.href} className={cn("group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-200",
              active ? "bg-gradient-to-r from-primary/20 via-primary/5 to-transparent text-white shadow-[inset_0_1px_0_hsl(0_0%_100%/.06)]" : "text-muted-foreground hover:translate-x-0.5 hover:bg-white/[0.04] hover:text-foreground")}>
              {active && <span className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r bg-gradient-to-b from-primary to-cyan shadow-[0_0_12px_hsl(var(--primary))]" />}
              <it.icon className={cn("h-4 w-4 transition-transform duration-200 group-hover:scale-110", active && "text-cyan")} />{it.label}
            </Link>
          );
        })}
      </nav>
      <div className="rounded-lg border border-white/5 bg-white/[0.03] p-3 text-[11px] leading-snug text-muted-foreground">Runs on your computer.<br />No watermark. No subscription.</div>
    </aside>
  );
}

export function MobileNav() {
  const path = usePathname() ?? "";
  return (
    <nav className="sticky top-0 z-20 flex gap-1 overflow-x-auto border-b border-white/5 bg-background/80 p-2 backdrop-blur-xl md:hidden">
      {items.map((it) => (
        <Link key={it.href} href={it.href} className={cn("flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs", isActive(path, it.href) ? "bg-primary/20 text-white" : "text-muted-foreground")}>
          <it.icon className="h-3.5 w-3.5" />{it.label}
        </Link>
      ))}
    </nav>
  );
}
