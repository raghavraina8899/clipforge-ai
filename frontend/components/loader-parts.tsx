"use client";

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


export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className="drop-shadow-[0_6px_14px_hsl(211_100%_55%/.55)]">
      <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#3b9bff" /><stop offset="1" stopColor="#22d3ee" /></linearGradient></defs>
      <rect width="32" height="32" rx="9" fill="url(#lg)" />
      <path d="M12 9.5v13l11-6.5z" fill="#fff" /><path d="M8 11v10" stroke="#fff" strokeOpacity=".55" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
