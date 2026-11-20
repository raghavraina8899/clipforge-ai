"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Play, Pause, RotateCcw } from "lucide-react";
import { captionAt } from "@/lib/captions";
import { FACECAM_DEFAULT, facecamCaptionPos, facecamGeometry } from "@/lib/facecam";
import type { ClipSettings, Word } from "@/lib/api";
import { fmtTime } from "@/lib/utils";

export interface Framing { mode: string; points: number[][]; tracks: { cx: number; cy: number }[]; facecam?: { x: number; y: number; w: number; h: number } | null; src_w: number; src_h: number; note: string }
const ASPECT: Record<string, [number, number]> = { "9:16": [9, 16], "1:1": [1, 1], "16:9": [16, 9], "4:5": [4, 5] };

function lerp(points: number[][], t: number, idx: number): number {
  if (!points.length) return NaN;
  if (t <= points[0][0]) return points[0][idx];
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i], b = points[i + 1];
    if (t <= b[0]) return a[idx] + ((b[idx] - a[idx]) * (t - a[0])) / Math.max(1e-3, b[0] - a[0]);
  }
  return points[points.length - 1][idx];
}

export function ClipPreview({ src, srcW, srcH, start, end, settings, words, framing, onTime, seekTo }: {
  src: string; srcW: number; srcH: number; start: number; end: number; settings: ClipSettings; words: Word[]; framing: Framing | null; onTime?: (t: number) => void; seekTo?: { t: number; n: number };
}) {
  const vref = useRef<HTMLVideoElement>(null);
  const cref = useRef<HTMLCanvasElement>(null);
  const [playing, setPlaying] = useState(false);
  const [t, setT] = useState(0);
  const [boxW, setBoxW] = useState(320);
  const wrap = useRef<HTMLDivElement>(null);
  const [a, b] = ASPECT[settings.format] || [9, 16];
  const ar = a / b;
  const dur = Math.max(0.1, end - start);
  const S = useRef({ settings, framing, start, end, dur, srcW, srcH });
  S.current = { settings, framing, start, end, dur, srcW, srcH };

  const draw = useCallback(() => {
    const v = vref.current, c = cref.current; if (!v || !c) return;
    const { settings: st, framing: fr, start, dur, srcW, srcH } = S.current;
    const ctx = c.getContext("2d"); if (!ctx) return;
    const W = c.width, H = c.height;
    const rel = Math.max(0, v.currentTime - start);
    const vw = v.videoWidth || srcW, vh = v.videoHeight || srcH;
    const sx = vw / srcW; // proxy may be smaller than the original: scale coordinates
    const en = st.enhance;
    ctx.save();
    ctx.filter = `brightness(${1 + en.brightness}) contrast(${en.contrast}) saturate(${en.saturation})`;
    ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H);
    const zf = en.zoom === "punch" ? 1.15 : 1;
    const crop = (cxPx: number, cyPx: number, aspect: number, zoomExtra = 1) => {
      let cw: number, ch: number;
      if (srcW / srcH >= aspect) { ch = srcH / zf / zoomExtra; cw = ch * aspect; } else { cw = srcW / zf / zoomExtra; ch = cw / aspect; }
      const x = Math.min(Math.max(cxPx - cw / 2, 0), srcW - cw), y = Math.min(Math.max(cyPx - ch / 2, 0), srcH - ch);
      return [x * sx, y * sx, cw * sx, ch * sx];
    };
    const layout = st.layout;
    const fc = fr?.facecam;
    if (fc && (layout === "smart" || layout === "facecam")) {
      // stacked: facecam on top, main content (gameplay / screen) below, facecam cropped out of the content
      const g = facecamGeometry(fc, srcW, srcH, W, H, { ...FACECAM_DEFAULT, ...(st.facecam || {}) });
      const { Ht, Hb } = g;
      ctx.drawImage(v, g.face.x * sx, g.face.y * sx, g.face.w * sx, g.face.h * sx, 0, 0, W, Ht);
      ctx.save(); ctx.beginPath(); ctx.rect(0, Ht, W, Hb); ctx.clip();
      const base = ctx.filter;
      const cx = g.content.x * sx, cy = g.content.y * sx, cw = g.content.w * sx, ch = g.content.h * sx;
      const fill = (st.facecam?.content ?? "fit") === "fill";
      let f: number;
      if (fill) f = Math.max(W / cw, Hb / ch);
      else {
        const cover = Math.max(W / cw, Hb / ch);
        ctx.filter = `blur(${W / 18}px) brightness(.9)`;
        ctx.drawImage(v, cx, cy, cw, ch, (W - cw * cover) / 2, Ht + (Hb - ch * cover) / 2, cw * cover, ch * cover);
        ctx.filter = base;
        f = Math.min(W / cw, Hb / ch);
      }
      const ox = (W - cw * f) / 2, oy = Ht + (Hb - ch * f) / 2;
      ctx.drawImage(v, cx, cy, cw, ch, ox, oy, cw * f, ch * f);
      if (g.mode === "blur") {
        ctx.save(); ctx.beginPath(); ctx.rect(ox + (fc.x * sx - cx) * f, oy + (fc.y * sx - cy) * f, fc.w * sx * f, fc.h * sx * f); ctx.clip();
        ctx.filter = `blur(${W / 40}px)`; ctx.drawImage(v, cx, cy, cw, ch, ox, oy, cw * f, ch * f); ctx.restore();
      }
      ctx.restore();
    } else if (layout === "smart" || layout === "center" || layout === "face" || layout === "facecam") {
      let cx = srcW / 2, cy = srcH / 2;
      if ((layout === "smart" || layout === "face" || layout === "facecam") && fr?.mode === "face" && fr.points.length) { cx = lerp(fr.points, rel, 1); cy = lerp(fr.points, rel, 2); }
      const zoomExtra = en.zoom === "push" ? 1 + 0.12 * (rel / dur) : 1;
      const [x, y, cw, ch] = crop(cx, cy, W / H, zoomExtra);
      ctx.drawImage(v, x, y, cw, ch, 0, 0, W, H);
    } else if (layout === "split" && fr && fr.tracks.length >= 2) {
      const aspect = W / (H / 2);
      [fr.tracks[0], fr.tracks[fr.tracks.length - 1]].forEach((tr, i) => {
        const [x, y, cw, ch] = crop(tr.cx, srcH / 2, aspect);
        ctx.drawImage(v, x, y, cw, ch, 0, (i * H) / 2, W, H / 2);
      });
    } else if (layout === "blur") {
      const cover = Math.max(W / vw, H / vh);
      ctx.filter = `blur(${W / 18}px) brightness(${0.9 * (1 + en.brightness)}) contrast(${en.contrast}) saturate(${en.saturation})`;
      ctx.drawImage(v, (W - vw * cover) / 2, (H - vh * cover) / 2, vw * cover, vh * cover);
      ctx.filter = `brightness(${1 + en.brightness}) contrast(${en.contrast}) saturate(${en.saturation})`;
      const fit = Math.min(W / vw, H / vh);
      ctx.drawImage(v, (W - vw * fit) / 2, (H - vh * fit) / 2, vw * fit, vh * fit);
    } else { // fill (and split fallback)
      ctx.fillStyle = st.fill_color || "#101010"; ctx.fillRect(0, 0, W, H);
      const fit = Math.min(W / vw, H / vh);
      ctx.drawImage(v, (W - vw * fit) / 2, (H - vh * fit) / 2, vw * fit, vh * fit);
    }
    ctx.restore();
  }, []);

  // size to container
  useEffect(() => {
    const el = wrap.current; if (!el) return;
    const ro = new ResizeObserver(() => setBoxW(el.clientWidth)); ro.observe(el); setBoxW(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  const canvasW = 540, canvasH = Math.round(540 / ar);

  useEffect(() => {
    const v = vref.current; if (!v) return;
    let raf = 0;
    const loop = () => {
      draw();
      const rel = v.currentTime - S.current.start;
      setT(rel); onTime?.(rel);
      if (v.currentTime >= S.current.end - 0.03) { v.pause(); v.currentTime = S.current.start; setPlaying(false); }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [draw, onTime]);

  useEffect(() => { const v = vref.current; if (v && (v.currentTime < start || v.currentTime > end)) v.currentTime = start; }, [start, end, src]);
  useEffect(() => { const v = vref.current; if (v && seekTo) v.currentTime = Math.min(end, Math.max(start, start + seekTo.t)); }, [seekTo?.n]); // eslint-disable-line

  const toggle = () => {
    const v = vref.current; if (!v) return;
    if (v.paused) { if (v.currentTime >= end - 0.1 || v.currentTime < start) v.currentTime = start; v.play(); setPlaying(true); } else { v.pause(); setPlaying(false); }
  };
  const stacked = !!framing?.facecam && (settings.layout === "smart" || settings.layout === "facecam");
  const st = (stacked ? { ...settings.caption, position: facecamCaptionPos(Math.round(540 / ar * Math.min(0.6, Math.max(0.25, settings.facecam?.share ?? 0.4))), canvasH, settings.facecam?.caption ?? "face") } : settings.caption) as any;
  const k = (Math.min(boxW, boxW / ar)) / 1080 * (ar >= 1 ? ar : 1);
  const shown = captionAt(words.map((w) => ({ ...w, s: w.s - start, e: w.e - start })), t, st);
  const fs = (st.size || 66) * Math.min(boxW, boxW / ar) / 1080;
  const kk = fs / (st.size || 66);
  const hookOn = settings.hook.enabled && settings.hook.text && t < settings.hook.duration;
  const endOn = settings.ending.enabled && settings.ending.text && t > dur - settings.ending.duration;
  void k;

  return (
    <div className="space-y-2">
      <div ref={wrap} className="relative mx-auto w-full overflow-hidden rounded-lg bg-black" style={{ aspectRatio: `${a} / ${b}`, maxWidth: ar >= 1 ? "100%" : 340 }}>
        <video ref={vref} src={src} className="hidden" playsInline preload="auto" crossOrigin="anonymous" onLoadedData={() => { const v = vref.current; if (v) { v.currentTime = start; setTimeout(draw, 80); } }} onSeeked={draw} />
        <canvas ref={cref} width={canvasW} height={canvasH} className="absolute inset-0 h-full w-full" />
        {shown && (
          <div className="pointer-events-none absolute left-0 right-0 flex flex-col items-center" style={{ top: `${st.position}%`, transform: "translateY(-50%)", animation: shown.fade ? "none" : undefined }}>
            {shown.emoji && <div style={{ fontSize: fs * 1.2, lineHeight: 1, marginBottom: 4 * kk }}>{shown.emoji}</div>}
            {shown.lines.map((line, li) => (
              <div key={li} className="caption-text flex justify-center text-center" style={{
                fontFamily: `"${st.font}", sans-serif`, fontSize: fs, fontWeight: st.bold ? 700 : 400, lineHeight: `${(st.lineSpacing || 1.05)}`, letterSpacing: (st.spacing || 0) * kk,
                color: st.color, WebkitTextStroke: !st.bg && st.outline ? `${st.outline * 2 * kk}px ${st.outlineColor}` : undefined,
                background: st.bg ? hexA(st.bg, st.bgOpacity ?? 0.6) : undefined, padding: st.bg ? `${(st.outline || 6) * kk * 0.4}px ${(st.outline || 6) * kk}px` : undefined,
                textShadow: [st.shadow ? `${st.shadow * kk}px ${st.shadow * kk}px 0 rgba(0,0,0,.6)` : "", st.blur ? `0 0 ${st.blur * kk * 3}px ${st.outlineColor}` : ""].filter(Boolean).join(",") || undefined,
              }}>
                {line.map((w, i) => (
                  <span key={i} style={{ marginRight: i < line.length - 1 ? "0.28em" : 0, visibility: w.visible ? "visible" : "hidden", color: w.active ? st.highlight : w.kw ? st.keyword : undefined, display: "inline-block", transform: w.active && st.animation === "pop" ? "scale(1.12)" : undefined, transition: "transform .08s" }}>{w.w}</span>
                ))}
              </div>
            ))}
          </div>
        )}
        {hookOn && <div className="absolute left-1/2 top-[20%] w-4/5 -translate-x-1/2 -translate-y-1/2 text-center"><span className="inline-block bg-[#E11D48] px-3 py-1 font-extrabold uppercase text-white" style={{ fontFamily: `"${st.font}", sans-serif`, fontSize: 76 * Math.min(boxW, boxW / ar) / 1080, lineHeight: 1.25 }}>{settings.hook.text}</span></div>}
        {endOn && <div className="absolute left-1/2 top-[30%] w-4/5 -translate-x-1/2 -translate-y-1/2 text-center"><span className="inline-block bg-black/75 px-3 py-1 font-bold text-white" style={{ fontSize: 61 * Math.min(boxW, boxW / ar) / 1080 }}>{settings.ending.text}</span></div>}
        <button onClick={toggle} className="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition hover:bg-black/20 hover:opacity-100" aria-label={playing ? "Pause" : "Play"}>
          {playing ? <Pause className="h-10 w-10 text-white drop-shadow" /> : <Play className="h-10 w-10 text-white drop-shadow" />}
        </button>
      </div>
      <div className="mx-auto flex items-center gap-2" style={{ maxWidth: ar >= 1 ? "100%" : 340 }}>
        <button onClick={toggle} className="rounded p-1 hover:bg-accent">{playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}</button>
        <input type="range" min={0} max={dur} step={0.05} value={Math.min(dur, Math.max(0, t))} className="flex-1" onChange={(e) => { const v = vref.current; if (v) v.currentTime = start + parseFloat(e.target.value); }} />
        <span className="w-20 text-right text-xs tabular-nums text-muted-foreground">{fmtTime(t, true)} / {fmtTime(dur)}</span>
        <button onClick={() => { const v = vref.current; if (v) v.currentTime = start; }} className="rounded p-1 hover:bg-accent" title="Restart"><RotateCcw className="h-3.5 w-3.5" /></button>
      </div>
      <p className="mx-auto text-center text-[11px] text-muted-foreground" style={{ maxWidth: 340 }}>Preview uses a 720p proxy and approximates colour effects; the export is rendered from your original file.</p>
    </div>
  );
}

export function hexA(hex: string, a: number) {
  const h = hex.replace("#", ""); if (h.length !== 6) return hex;
  return `rgba(${parseInt(h.slice(0, 2), 16)},${parseInt(h.slice(2, 4), 16)},${parseInt(h.slice(4, 6), 16)},${a})`;
}
