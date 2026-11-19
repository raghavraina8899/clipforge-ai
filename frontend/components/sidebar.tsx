"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Wand2, FolderKanban, Library, Captions, Sparkles, SlidersHorizontal, Info, Scissors } from "lucide-react";
import { cn } from "@/lib/utils";

const items = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/create", label: "Create New Clips", icon: Wand2 },
  { href: "/projects", label: "My Projects", icon: FolderKanban },
  { href: "/library", label: "Clip Library", icon: Library },
  { href: "/styles", label: "Subtitle Styles", icon: Captions },
  { href: "/settings/ai", label: "AI Settings", icon: Sparkles },
  { href: "/settings/video", label: "Video Settings", icon: SlidersHorizontal },
  { href: "/about", label: "About", icon: Info },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r bg-card/50 p-3 md:flex">
      <Link href="/" className="mb-5 flex items-center gap-2 px-2 py-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Scissors className="h-4 w-4" /></span>
        <span className="text-base font-semibold tracking-tight">ClipForge <span className="text-primary">AI</span></span>
      </Link>
      <nav className="flex flex-1 flex-col gap-0.5">
        {items.map((it) => {
          const active = it.href === "/" ? path === "/" : path.startsWith(it.href);
          return (
            <Link key={it.href} href={it.href} className={cn("flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors", active ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground")}>
              <it.icon className="h-4 w-4" />{it.label}
            </Link>
          );
        })}
      </nav>
      <p className="px-2 text-[11px] leading-snug text-muted-foreground">Runs locally. No watermark, no subscription.</p>
    </aside>
  );
}

export function MobileNav() {
  const path = usePathname();
  return (
    <nav className="sticky top-0 z-20 flex gap-1 overflow-x-auto border-b bg-background/95 p-2 backdrop-blur md:hidden">
      {items.map((it) => (
        <Link key={it.href} href={it.href} className={cn("flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs", (it.href === "/" ? path === "/" : path.startsWith(it.href)) ? "bg-primary/15 text-primary" : "text-muted-foreground")}>
          <it.icon className="h-3.5 w-3.5" />{it.label}
        </Link>
      ))}
    </nav>
  );
}
