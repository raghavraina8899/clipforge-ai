"""Caption styling presets + ASS/SRT generation. ASS is rendered by FFmpeg's libass, so what the
user exports has real per-word timing (not an approximation)."""
import re
import textwrap
from typing import Optional

BASE = {
    "font": "Poppins ExtraBold", "size": 66, "bold": True, "color": "#FFFFFF", "highlight": "#FFE600", "keyword": "#00E676",
    "bg": "", "bgOpacity": 0.6, "outline": 6, "outlineColor": "#000000", "shadow": 0, "blur": 0, "position": 66,
    "lineSpacing": 1.05, "maxWordsPerLine": 3, "wordsAtTime": 3, "animation": "pop", "uppercase": True,
    "autoKeywords": False, "keywords": "", "emoji": False, "spacing": 0, "show": True,
}


def P(**kw):
    return {**BASE, **kw}


PRESETS = {
    "modern_podcast": ("Modern Podcast", P(font="Poppins Bold", size=58, uppercase=False, color="#FFFFFF", highlight="#7DD3FC", bg="#111827", bgOpacity=0.7, outline=14, shadow=0, position=74, maxWordsPerLine=3, wordsAtTime=5, animation="highlight")),
    "hormozi": ("Hormozi Style", P(font="Poppins Black", size=72, color="#FFFFFF", highlight="#22FF66", keyword="#FFE600", outline=8, position=64, wordsAtTime=3, maxWordsPerLine=3, animation="pop", autoKeywords=True)),
    "mrbeast": ("MrBeast Inspired", P(font="Bangers", size=96, color="#FFFFFF", highlight="#FFE600", keyword="#FF3B30", outline=10, shadow=4, position=60, wordsAtTime=2, maxWordsPerLine=2, animation="pop", spacing=1)),
    "minimal_white": ("Minimal White", P(font="Poppins", size=50, bold=False, uppercase=False, color="#FFFFFF", highlight="#FFFFFF", outline=0, shadow=3, blur=1, position=80, wordsAtTime=6, maxWordsPerLine=3, animation="fade")),
    "neon": ("Neon Highlight", P(font="Poppins ExtraBold", size=68, color="#F5F5FF", highlight="#39FF14", keyword="#FF2BD6", outline=5, outlineColor="#7C3AED", shadow=0, blur=4, position=64, wordsAtTime=3, maxWordsPerLine=3, animation="pop")),
    "karaoke": ("Karaoke Style", P(font="Poppins Bold", size=62, uppercase=False, color="#E5E7EB", highlight="#FACC15", outline=6, position=68, wordsAtTime=6, maxWordsPerLine=3, animation="karaoke")),
    "bold_yellow": ("Bold Yellow", P(font="Anton", size=84, color="#FFE600", highlight="#FFFFFF", outline=7, shadow=2, position=66, wordsAtTime=3, maxWordsPerLine=3, animation="highlight")),
    "clean_pro": ("Clean Professional", P(font="Poppins Bold", size=52, uppercase=False, color="#FFFFFF", highlight="#4ADE80", bg="#000000", bgOpacity=0.55, outline=12, position=78, wordsAtTime=6, maxWordsPerLine=3, animation="fade")),
    "cinematic": ("Cinematic", P(font="Bebas Neue", size=78, uppercase=True, bold=False, color="#F3E9D2", highlight="#F3E9D2", outline=0, shadow=3, blur=1, position=86, wordsAtTime=6, maxWordsPerLine=6, animation="fade", spacing=4)),
    "custom": ("Custom Style", P()),
}

FONT_CATALOG = [  # ASS family name, css family, weight, filename (None = system font)
    ("Poppins", "Poppins", 400, "Poppins-Regular.ttf"), ("Poppins Bold", "Poppins", 700, "Poppins-Bold.ttf"),
    ("Poppins ExtraBold", "Poppins", 800, "Poppins-ExtraBold.ttf"), ("Poppins Black", "Poppins", 900, "Poppins-Black.ttf"),
    ("Anton", "Anton", 400, "Anton-Regular.ttf"), ("Bebas Neue", "Bebas Neue", 400, "BebasNeue-Regular.ttf"),
    ("Bangers", "Bangers", 400, "Bangers-Regular.ttf"), ("Archivo Black", "Archivo Black", 400, "ArchivoBlack-Regular.ttf"),
    ("Arial", "Arial", 400, None), ("Helvetica Neue", "Helvetica Neue", 400, None), ("Impact", "Impact", 400, None),
    ("Georgia", "Georgia", 400, None), ("Verdana", "Verdana", 400, None), ("Trebuchet MS", "Trebuchet MS", 400, None),
]
BOLD_DEFAULT_FAMILIES = {"Poppins Bold", "Poppins ExtraBold", "Poppins Black", "Anton", "Bangers", "Archivo Black", "Impact"}


def merge_style(style: Optional[dict]) -> dict:
    style = style or {}
    base = PRESETS.get(style.get("preset", "hormozi"), PRESETS["hormozi"])[1]
    return {**base, **{k: v for k, v in style.items() if k != "preset"}}


def _ass_color(hex_: str, alpha: float = 0.0) -> str:
    h = (hex_ or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{int(round(alpha * 255)):02X}{b}{g}{r}".upper()


def _t(sec: float) -> str:
    sec = max(0.0, sec)
    cs = int(round(sec * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _esc(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


NUMBERISH = re.compile(r"^[\$€£₹]?\d[\d,.]*[%kKmMbB]?$")
STOP = set("the a an and or but if then so to of in on at for with from by is are was were be been it its this that these those i you he she we they me him her us them my your his our their as not no yes do does did have has had will would can could should just very really about into out up down over than too also there here what when where who how all any some like because".split())
EMOJI_MAP = {"money": "💰", "love": "❤️", "fire": "🔥", "win": "🏆", "success": "🚀", "idea": "💡", "time": "⏰", "secret": "🤫", "growth": "📈", "mind": "🧠", "wow": "😮", "happy": "😊"}


def _group(words: list, n: int) -> list:
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        brk = len(cur) >= n or nxt is None or re.search(r"[.!?।]$", w["w"]) or (nxt["s"] - w["e"] > 0.7)
        if brk:
            groups.append(cur)
            cur = []
    return groups


def _keywords(style: dict, words: list) -> set:
    kws = {k.strip().lower() for k in re.split(r"[,\n]", style.get("keywords") or "") if k.strip()}
    return kws


def _is_kw(style: dict, kws: set, word: str) -> bool:
    bare = re.sub(r"[^\w$€£₹%.,]", "", word).strip(".,").lower()
    if bare in kws:
        return True
    return bool(style.get("autoKeywords")) and bool(NUMBERISH.match(bare))


def _fit(text: str, width_px: float, fs: float) -> str:
    cpl = max(8, int(width_px / (fs * 0.52)))
    return "\\N".join(textwrap.wrap(text, cpl)) or text


def build_ass(words: list, style: Optional[dict], W: int, H: int, duration: float,
              hook: Optional[dict] = None, ending: Optional[dict] = None) -> tuple:
    """words: [{w,s,e}] with times relative to clip start."""
    st = merge_style(style)
    k = min(W, H) / 1080.0
    fs = max(10.0, st["size"] * k)
    bold = -1 if st.get("bold") else 0
    has_bg = bool(st.get("bg"))
    prim, sec = _ass_color(st["color"]), _ass_color(st["highlight"])
    if has_bg:
        border = f"3,{max(2, st['outline'] * k):.1f},0"
        outc = back = _ass_color(st["bg"], 1 - float(st.get("bgOpacity", 0.6)))
    else:
        border = f"1,{st['outline'] * k:.1f},{st['shadow'] * k:.1f}"
        outc = _ass_color(st["outlineColor"])
        back = _ass_color("#000000", 0.4)
    spacing = st.get("spacing", 0) * k
    hs = max(10.0, 76 * k)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Default,{st['font']},{fs:.1f},{prim},{sec},{outc},{back},{bold},0,0,0,100,100,{spacing:.1f},0,{border},5,10,10,10,1",
        f"Style: Hook,{st['font']},{hs:.1f},&H00FFFFFF,&H00FFFFFF,{_ass_color('#E11D48')},{_ass_color('#E11D48')},{-1},0,0,0,100,100,0,0,3,{max(6, 16 * k):.1f},0,5,10,10,10,1",
        f"Style: End,{st['font']},{hs * .8:.1f},&H00FFFFFF,&H00FFFFFF,{_ass_color('#000000', .25)},{_ass_color('#000000', .25)},{-1},0,0,0,100,100,0,0,3,{max(6, 14 * k):.1f},0,5,10,10,10,1",
        "", "[Events]", "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    ev = []
    words = [w for w in words if w["e"] > 0 and w["s"] < duration] if st.get("show", True) else []  # captions off: no subtitle text, no emoji
    kws = _keywords(st, words)
    mw = max(1, int(st["maxWordsPerLine"]))
    groups = _group(words, max(1, int(st["wordsAtTime"])))
    anim = st["animation"]
    cx = W / 2
    emoji_on = bool(st.get("emoji"))
    overlays: list = []
    li_first = lambda gi: True  # noqa: E731

    def word_text(w: dict, active: bool) -> str:
        t = _esc(w["w"])
        t = t.upper() if st.get("uppercase") else t
        kw = _is_kw(st, kws, w["w"])
        if active and anim in ("highlight", "pop", "karaoke"):
            pop = r"\fscx118\fscy118\t(0,90,\fscx100\fscy100)" if anim == "pop" else ""
            return "{\\c" + sec + pop + "}" + t + "{\\r}"
        if kw:
            return "{\\c" + _ass_color(st["keyword"]) + "}" + t + "{\\r}"
        return t

    for gi, g in enumerate(groups):
        g_start = g[0]["s"]
        nxt_start = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else duration
        g_end = min(max(g[-1]["e"] + 0.12, g[-1]["s"] + 0.25), nxt_start, duration)
        chunks = [g[i:i + mw] for i in range(0, len(g), mw)]
        n = len(chunks)
        block_y = st["position"] / 100.0 * H
        step = fs * float(st["lineSpacing"])
        emo = ""
        if emoji_on and li_first(gi):
            for w in g:
                m = EMOJI_MAP.get(re.sub(r"\W", "", w["w"]).lower())
                if m:
                    overlays.append({"emoji": m, "start": w["s"], "end": g_end, "y": block_y - (n / 2) * step - fs * 0.9})
                    break
        for li, ch in enumerate(chunks):
            y = block_y + (li - (n - 1) / 2) * step
            pos = f"\\an5\\pos({cx:.0f},{y:.0f})"
            glow = f"\\blur{st['blur']}" if st.get("blur") else ""
            if anim == "karaoke":
                parts = []
                for w in ch:
                    cs = max(1, int(round((max(w["e"], w["s"] + .05) - w["s"]) * 100)))
                    t = _esc(w["w"]).upper() if st.get("uppercase") else _esc(w["w"])
                    parts.append("{\\kf%d}%s" % (cs, t))
                # karaoke: Primary = highlight (filled), Secondary = base colour, so the sweep fills with the highlight.
                text = "{" + pos + glow + "\\1c" + sec + "\\2c" + prim + "}" + " ".join(parts) + (emo if li == n - 1 else "")
                ev.append(f"Dialogue: 1,{_t(ch[0]['s'])},{_t(g_end)},Default,,0,0,0,,{text}")
            elif anim in ("highlight", "pop"):
                for wi, w in enumerate(g):
                    if w not in ch:
                        continue
                    ws = w["s"] if wi else g_start
                    we = g[wi + 1]["s"] if wi + 1 < len(g) else g_end
                    if we <= ws:
                        continue
                    text = "".join(["{" + pos + glow + "}"]) + " ".join(word_text(x, x is w) for x in ch) + (emo if li == n - 1 else "")
                    ev.append(f"Dialogue: 1,{_t(ws)},{_t(we)},Default,,0,0,0,,{text}")
            elif anim == "reveal":
                for wi, w in enumerate(g):
                    if w not in ch:
                        continue
                    shown = ch[:ch.index(w) + 1]
                    we = g[wi + 1]["s"] if wi + 1 < len(g) else g_end
                    text = "{" + pos + glow + "}" + " ".join(word_text(x, x is w) for x in shown)
                    ev.append(f"Dialogue: 1,{_t(w['s'] if wi else g_start)},{_t(we)},Default,,0,0,0,,{text}")
            else:  # fade / none: static group
                fade = "\\fad(140,0)" if anim == "fade" else ""
                text = "{" + pos + glow + fade + "}" + " ".join(word_text(x, False) for x in ch) + (emo if li == n - 1 else "")
                ev.append(f"Dialogue: 1,{_t(g_start)},{_t(g_end)},Default,,0,0,0,,{text}")

    if hook and hook.get("enabled") and (hook.get("text") or "").strip():
        d = min(float(hook.get("duration", 2.5)), max(0.5, duration))
        txt = _fit(_esc(hook["text"].strip()).upper(), W * 0.8, hs)
        eff = "\\fscx70\\fscy70\\t(0,180,\\fscx100\\fscy100)" if hook.get("style", "pop") == "pop" else ""
        ev.append(f"Dialogue: 2,{_t(0)},{_t(d)},Hook,,0,0,0,,{{\\an5\\pos({cx:.0f},{H * .2:.0f})\\fad(120,250){eff}}}{txt}")
    if ending and ending.get("enabled") and (ending.get("text") or "").strip():
        d = min(float(ending.get("duration", 2.5)), max(0.5, duration))
        txt = _fit(_esc(ending["text"].strip()), W * 0.8, hs * .8)
        ev.append(f"Dialogue: 2,{_t(duration - d)},{_t(duration)},End,,0,0,0,,{{\\an5\\pos({cx:.0f},{H * .3:.0f})\\fad(200,150)}}{txt}")
    return "\n".join(lines + ev) + "\n", overlays


def build_srt(words: list, per: int = 7) -> str:
    out = []
    for i, g in enumerate(_group(words, per), 1):
        def ts(x):
            ms = int(round(max(0, x) * 1000))
            return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
        text = " ".join(w["w"] for w in g)
        if len(text) > 42:
            half = len(g) // 2
            text = " ".join(w["w"] for w in g[:half]) + "\n" + " ".join(w["w"] for w in g[half:])
        out.append(f"{i}\n{ts(g[0]['s'])} --> {ts(max(g[-1]['e'], g[0]['s'] + .2))}\n{text}\n")
    return "\n".join(out)
