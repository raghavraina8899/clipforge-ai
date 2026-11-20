"""Subject / speaker tracking with OpenCV (Haar face detector, mouth-motion heuristic for the active speaker).
Deliberately conservative: when no face is found we report mode='center' and the renderer center-crops."""
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("vision")
STEP = 0.25  # seconds between samples


def _median(xs: list) -> float:
    s = sorted(xs)
    return s[len(s) // 2]


def track(video: Path, start: float, end: float, src_w: int, src_h: int, crop_w: float,
          on_progress=None, ctx=None) -> dict:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"mode": "center", "points": [], "tracks": [], "facecam": None, "note": "OpenCV not installed; used center crop."}
    if not hasattr(cv2, "CascadeClassifier"):
        return {"mode": "center", "points": [], "tracks": [], "facecam": None, "note": "This OpenCV build has no face detector (need OpenCV 4.x); used center crop."}
    cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cc.empty():
        return {"mode": "center", "points": [], "tracks": [], "facecam": None, "note": "Face detector model not found; used center crop."}
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return {"mode": "center", "points": [], "tracks": [], "facecam": None, "note": "Could not open video for face tracking; used center crop."}
    pw = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or src_w
    ph = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or src_h
    sx, sy = src_w / pw, src_h / ph
    scale = 640.0 / pw if pw > 640 else 1.0
    tracks: list = []  # each: {pts: [(t,cx,cy)], prev: patch, ema: float}
    samples: list = []  # per-time: {t, faces:[track idx]}
    keep_frames: list = []  # a few gray frames, used to find the facecam overlay's exact border
    n = max(1, int((end - start) / STEP))
    for i in range(n + 1):
        if ctx:
            ctx.check()
        t = min(end - start, i * STEP)
        cap.set(cv2.CAP_PROP_POS_MSEC, (start + t) * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(cv2.resize(frame, None, fx=scale, fy=scale) if scale != 1 else frame, cv2.COLOR_BGR2GRAY)
        if i % max(1, n // 8) == 0:
            keep_frames.append(gray.copy())
        faces = cc.detectMultiScale(gray, 1.15, 6, minSize=(max(24, int(gray.shape[1] * 0.04)),) * 2)
        seen = []
        for (x, y, w, h) in faces:
            cx, cy = (x + w / 2) / scale, (y + h / 2) / scale
            best, bd = None, 0.18 * pw
            for ti, tr in enumerate(tracks):
                lt, lx, ly = tr["pts"][-1]
                if t - lt <= 1.5 and abs(lx - cx) < bd:
                    best, bd = ti, abs(lx - cx)
            if best is None:
                tracks.append({"pts": [], "prev": None, "ema": 0.0, "sizes": []})
                best = len(tracks) - 1
            tr = tracks[best]
            # mouth-region motion between consecutive samples = speaking proxy
            my0, my1 = y + int(h * 0.55), y + h
            patch = cv2.resize(gray[my0:my1, x:x + w], (24, 12)).astype("float32") if my1 > my0 else None
            if patch is not None and tr["prev"] is not None:
                tr["ema"] = 0.6 * tr["ema"] + 0.4 * float(np.abs(patch - tr["prev"]).mean())
            tr["prev"] = patch
            tr["pts"].append((t, cx, cy))
            tr["sizes"].append((w / scale, h / scale))
            seen.append(best)
        samples.append({"t": t, "seen": seen})
        if on_progress and i % 8 == 0:
            on_progress(i / n * 100)
    cap.release()
    if not any(s["seen"] for s in samples):
        return {"mode": "center", "points": [], "tracks": [], "facecam": None, "note": "No faces detected; used center crop."}

    # choose active speaker with hysteresis, hold last position through gaps
    # ignore short-lived tracks: Haar false positives flicker, real people persist
    eligible = {i for i, tr in enumerate(tracks) if len(tr["pts"]) >= max(3, 0.3 * len(samples))}
    if not eligible:
        eligible = {max(range(len(tracks)), key=lambda i: len(tracks[i]["pts"]))}
    for s_ in samples:
        s_["seen"] = [ti for ti in s_["seen"] if ti in eligible]
    cur: Optional[int] = None
    raw = []
    last = (src_w / 2 / sx, src_h / 2 / sy)
    for s in samples:
        if s["seen"]:
            best = max(s["seen"], key=lambda ti: tracks[ti]["ema"])
            if cur is None or cur not in s["seen"]:
                cur = best
            elif best != cur and tracks[best]["ema"] > 1.3 * tracks[cur]["ema"] + 0.5:
                cur = best
            p = next(pt for pt in reversed(tracks[cur]["pts"]) if abs(pt[0] - s["t"]) < 1e-6)
            last = (p[1], p[2])
        raw.append((s["t"], last[0] * sx, last[1] * sy))

    # median filter then dead-zone follow (camera only moves when the subject leaves the comfort zone)
    xs = [r[1] for r in raw]
    ys = [r[2] for r in raw]
    med = lambda arr, i: _median(arr[max(0, i - 2): i + 3])  # noqa: E731
    xs = [med(xs, i) for i in range(len(xs))]
    ys = [med(ys, i) for i in range(len(ys))]
    dz = 0.08 * crop_w
    cam_x, cam_y = xs[0], ys[0]
    pts = []
    for (t, _, _), x, y in zip(raw, xs, ys):
        if abs(x - cam_x) > dz:
            cam_x += (x - cam_x) * 0.3
        if abs(y - cam_y) > dz:
            cam_y += (y - cam_y) * 0.3
        pts.append([round(t, 2), round(cam_x, 1), round(cam_y, 1)])
    # drop points that are linear interpolations of their neighbours
    simp = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = simp[-1], pts[i], pts[i + 1]
        f = (b[0] - a[0]) / max(1e-6, c[0] - a[0])
        if abs(a[1] + (c[1] - a[1]) * f - b[1]) > 4 or abs(a[2] + (c[2] - a[2]) * f - b[2]) > 4:
            simp.append(b)
    simp.append(pts[-1])

    persistent = []
    for ti, tr in enumerate(tracks):
        if ti in eligible:
            persistent.append({"cx": round(_median([p[1] for p in tr["pts"]]) * sx, 1), "cy": round(_median([p[2] for p in tr["pts"]]) * sy, 1)})
    persistent.sort(key=lambda p: p["cx"])
    facecam = _facecam(tracks, eligible, sx, sy, src_w, src_h)
    if facecam:
        facecam = _refine(keep_frames, facecam, scale / sx, src_w, src_h)
    return {"mode": "face", "points": simp, "tracks": persistent, "facecam": facecam, "note": f"Tracked {len(eligible)} face(s)" + (f"; active-speaker switching across {len(persistent)} people." if len(persistent) > 1 else ".")}


def _facecam(tracks: list, eligible: set, sx: float, sy: float, src_w: int, src_h: int) -> Optional[dict]:
    """A streamer-style facecam = a small face sitting near an edge/corner of a larger scene.
    Returns the overlay rectangle in source pixels, or None (e.g. vlogs where the face fills the frame)."""
    best = None
    for ti in eligible:
        tr = tracks[ti]
        if len(tr["pts"]) < 3:
            continue
        cx = _median([p[1] for p in tr["pts"]]) * sx
        cy = _median([p[2] for p in tr["pts"]]) * sy
        fw = _median([z[0] for z in tr["sizes"]]) * sx
        fh = _median([z[1] for z in tr["sizes"]]) * sy
        if best is None or len(tr["pts"]) > best[0]:
            best = (len(tr["pts"]), cx, cy, fw, fh)
    if not best:
        return None
    _, cx, cy, fw, fh = best
    small = fw / src_w < 0.22
    at_edge = cx / src_w < 0.3 or cx / src_w > 0.7 or cy / src_h < 0.3 or cy / src_h > 0.7
    if not (small and at_edge):
        return None
    w, h = min(fw * 2.6, src_w * 0.6), min(fh * 2.6, src_h * 0.6)
    x, y = min(max(cx - w / 2, 0), src_w - w), min(max(cy - h / 2, 0), src_h - h)
    return {"x": round(float(x), 1), "y": round(float(y), 1), "w": round(float(w), 1), "h": round(float(h), 1)}


def _refine(frames: list, rect: dict, k: float, src_w: int, src_h: int) -> dict:
    """Snap the estimated facecam rectangle to the overlay's real border: overlays are static rectangles,
    so their edges show up as strong, constant gradients across sampled frames. k = source px -> gray px."""
    import numpy as np
    if len(frames) < 3:
        return rect
    gh, gw = frames[0].shape
    x0, y0, x1, y1 = rect["x"] * k, rect["y"] * k, (rect["x"] + rect["w"]) * k, (rect["y"] + rect["h"]) * k
    bx, by = 0.14 * gw, 0.18 * gh
    st = np.stack([f.astype("float32") for f in frames])
    gx = np.abs(np.diff(st, axis=2)).mean(axis=0)  # vertical edges  (H, W-1)
    gy = np.abs(np.diff(st, axis=1)).mean(axis=0)  # horizontal edges (H-1, W)
    cols = gx[int(max(0, y0)):int(min(gh, y1)), :].mean(axis=0)
    rows = gy[:, int(max(0, x0)):int(min(gw, x1))].mean(axis=1)

    def best(profile, lo, hi, est):
        """Strongest edge near the estimate (the overlay border is a long, perfectly straight, high-contrast line)."""
        lo, hi = int(max(1, lo)), int(min(len(profile) - 1, hi))
        if hi <= lo:
            return est
        seg = profile[lo:hi]
        i = int(seg.argmax())
        return lo + i + 1 if seg[i] > 2.0 * float(np.median(profile)) + 1.0 else est

    # the estimate (face x 2.6) usually lies inside the overlay, so search further outward than inward
    nx0, nx1 = best(cols, x0 - 0.10 * gw, x0 + 0.04 * gw, x0), best(cols, x1 - 0.04 * gw, x1 + 0.10 * gw, x1)
    ny0, ny1 = best(rows, y0 - 0.12 * gh, y0 + 0.05 * gh, y0), best(rows, y1 - 0.05 * gh, y1 + 0.12 * gh, y1)
    # overlays in a corner touch the frame edge: snap when close
    snap_x, snap_y = 0.06 * gw, 0.06 * gh
    if nx0 < snap_x: nx0 = 0
    if ny0 < snap_y: ny0 = 0
    if nx1 > gw - snap_x: nx1 = gw
    if ny1 > gh - snap_y: ny1 = gh
    w, h = (nx1 - nx0) / k, (ny1 - ny0) / k
    if not (0.6 * rect["w"] <= w <= 2.2 * rect["w"] and 0.6 * rect["h"] <= h <= 2.2 * rect["h"]):
        return rect
    return {"x": round(nx0 / k, 1), "y": round(ny0 / k, 1), "w": round(w, 1), "h": round(h, 1), "refined": True}
