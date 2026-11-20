"use client";
import { useEffect } from "react";
import { Cube, Logo } from "@/components/loader-parts";
import { BRAND } from "@/lib/brand";

/** Server-rendered splash: it is part of the first HTML, so it shows instantly on every reload, before any script runs. */
export function Splash() {
  return (
    <div id="splash" className="fixed inset-0 z-[100] flex flex-col items-center justify-center gap-7 bg-background transition-opacity duration-500">
      <div className="flex items-center gap-3"><Logo size={40} /><span className="text-2xl font-semibold tracking-tight">{BRAND.name}</span></div>
      <Cube size={78} />
      <div className="text-center">
        <div className="text-sm text-muted-foreground">Starting up…</div>
        <div className="mx-auto mt-3 h-1.5 w-60 overflow-hidden rounded-full bg-muted shadow-[inset_0_1px_2px_hsl(0_0%_0%/.5)]">
          <div className="h-full w-1/3 animate-[loadbar_1.3s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-primary to-cyan shadow-[0_0_12px_hsl(var(--primary))]" />
        </div>
      </div>
      <noscript><style>{"#splash{display:none}"}</style></noscript>
    </div>
  );
}

/** Fades the splash out once the page is interactive (and it has been visible long enough to register). */
export function SplashController() {
  useEffect(() => {
    const el = document.getElementById("splash"); if (!el) return;
    const wait = Math.max(0, 1100 - performance.now());  // performance.now() = time since the reload started
    const t1 = setTimeout(() => { el.style.opacity = "0"; el.style.pointerEvents = "none"; }, wait);
    const t2 = setTimeout(() => el.remove(), wait + 600);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);
  return null;
}
