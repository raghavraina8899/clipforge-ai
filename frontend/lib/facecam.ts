export interface Rect { x: number; y: number; w: number; h: number }
export interface FacecamOpts { share: number; content: string; hide: boolean; caption: string }
export const FACECAM_DEFAULT: FacecamOpts = { share: 0.4, content: "fit", hide: true, caption: "face" };
const even = (v: number) => Math.round(v / 2) * 2;

/** Mirrors backend render.facecam_geometry so preview == export. */
export function facecamGeometry(fc: Rect, sw: number, sh: number, W: number, H: number, o: FacecamOpts) {
  const Ht = even(H * Math.min(0.6, Math.max(0.25, o.share)));
  const asp = W / Ht;
  const fcw = Math.min(fc.w, fc.h * asp), fch = fcw / asp;
  const face = { x: fc.x + (fc.w - fcw) / 2, y: fc.y + (fc.h - fch) / 2, w: fcw, h: fch };
  let content: Rect = { x: 0, y: 0, w: sw, h: sh };
  let mode: "keep" | "crop" | "blur" = "keep";
  if (o.hide) {
    const m = 8; const opts: Rect[] = [];
    if (fc.x + fc.w >= sw - 4) opts.push({ x: 0, y: 0, w: fc.x - m, h: sh });
    if (fc.x <= 4) opts.push({ x: fc.x + fc.w + m, y: 0, w: sw - (fc.x + fc.w + m), h: sh });
    if (fc.y <= 4) opts.push({ x: 0, y: fc.y + fc.h + m, w: sw, h: sh - (fc.y + fc.h + m) });
    if (fc.y + fc.h >= sh - 4) opts.push({ x: 0, y: 0, w: sw, h: fc.y - m });
    const best = opts.sort((a, b) => b.w * b.h - a.w * a.h)[0];
    if (best && best.w * best.h >= 0.35 * sw * sh) { content = best; mode = "crop"; } else mode = "blur";
  }
  return { Ht, Hb: H - Ht, face, content, mode };
}

/** Caption y (percent of height) so captions do not cover the gameplay. */
export function facecamCaptionPos(Ht: number, H: number, where: string): number {
  return where === "seam" ? (Ht / H) * 100 : where === "bottom" ? 93 : ((Ht * 0.84) / H) * 100;
}
