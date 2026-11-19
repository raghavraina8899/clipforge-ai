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
        return {"mode": "center", "points": [], "tracks": [], "note": "OpenCV not installed; used center crop."}
    if not hasattr(cv2, "CascadeClassifier"):
        return {"mode": "center", "points": [], "tracks": [], "note": "This OpenCV build has no face detector (need OpenCV 4.x); used center crop."}
    cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cc.empty():
        return {"mode": "center", "points": [], "tracks": [], "note": "Face detector model not found; used center crop."}
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return {"mode": "center", "points": [], "tracks": [], "note": "Could not open video for face tracking; used center crop."}
    pw = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or src_w
    ph = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or src_h
    sx, sy = src_w / pw, src_h / ph
    scale = 640.0 / pw if pw > 640 else 1.0
    tracks: list = []  # each: {pts: [(t,cx,cy)], prev: patch, ema: float}
    samples: list = []  # per-time: {t, faces:[track idx]}
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
                tracks.append({"pts": [], "prev": None, "ema": 0.0})
                best = len(tracks) - 1
            tr = tracks[best]
            # mouth-region motion between consecutive samples = speaking proxy
            my0, my1 = y + int(h * 0.55), y + h
            patch = cv2.resize(gray[my0:my1, x:x + w], (24, 12)).astype("float32") if my1 > my0 else None
            if patch is not None and tr["prev"] is not None:
                tr["ema"] = 0.6 * tr["ema"] + 0.4 * float(np.abs(patch - tr["prev"]).mean())
            tr["prev"] = patch
            tr["pts"].append((t, cx, cy))
            seen.append(best)
        samples.append({"t": t, "seen": seen})
        if on_progress and i % 8 == 0:
            on_progress(i / n * 100)
    cap.release()
    if not any(s["seen"] for s in samples):
        return {"mode": "center", "points": [], "tracks": [], "note": "No faces detected; used center crop."}

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
    return {"mode": "face", "points": simp, "tracks": persistent, "note": f"Tracked {len(eligible)} face(s)" + (f"; active-speaker switching across {len(persistent)} people." if len(persistent) > 1 else ".")}
