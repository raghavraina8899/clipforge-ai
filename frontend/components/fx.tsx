"use client";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/** Card that tilts toward the cursor in 3D with a moving highlight. */
export function TiltCard({ children, className, strength = 7 }: { children: React.ReactNode; className?: string; strength?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [t, setT] = useState({ rx: 0, ry: 0, gx: 50, gy: 50, on: false });
  const move = (e: React.MouseEvent) => {
    const r = ref.current?.getBoundingClientRect(); if (!r) return;
    const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    setT({ rx: (0.5 - y) * strength * 2, ry: (x - 0.5) * strength * 2, gx: x * 100, gy: y * 100, on: true });
  };
  return (
    <div ref={ref} onMouseMove={move} onMouseLeave={() => setT({ rx: 0, ry: 0, gx: 50, gy: 50, on: false })} className={cn("relative", className)} style={{ perspective: 900 }}>
      <div className="surface relative h-full overflow-hidden rounded-xl transition-[transform,box-shadow,border-color] duration-200 ease-out"
        style={{ transform: `rotateX(${t.rx}deg) rotateY(${t.ry}deg) translateZ(0) ${t.on ? "scale(1.015)" : ""}`, transformStyle: "preserve-3d",
          borderColor: t.on ? "hsl(var(--primary) / .5)" : undefined, boxShadow: t.on ? "inset 0 1px 0 hsl(0 0% 100% / .1), 0 26px 44px -20px hsl(211 100% 50% / .45)" : undefined }}>
        <div className="pointer-events-none absolute inset-0 transition-opacity duration-200" style={{ opacity: t.on ? 1 : 0, background: `radial-gradient(260px circle at ${t.gx}% ${t.gy}%, hsl(211 100% 70% / .16), transparent 60%)` }} />
        <div className="relative">{children}</div>
      </div>
    </div>
  );
}

/** Number that counts up when it changes. */
export function Counter({ value }: { value: number | undefined }) {
  const [n, setN] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (value === undefined) return;
    const start = performance.now(), a = from.current, dur = 700;
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / dur), e = 1 - Math.pow(1 - p, 3);
      setN(Math.round(a + (value - a) * e));
      if (p < 1) raf = requestAnimationFrame(tick); else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <>{value === undefined ? "–" : n}</>;
}

export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className="drop-shadow-[0_6px_14px_hsl(211_100%_55%/.55)]">
      <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#3b9bff" /><stop offset="1" stopColor="#22d3ee" /></linearGradient></defs>
      <rect width="32" height="32" rx="9" fill="url(#lg)" />
      <path d="M12 9.5v13l11-6.5z" fill="#fff" /><path d="M8 11v10" stroke="#fff" strokeOpacity=".55" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
