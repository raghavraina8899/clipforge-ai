"""Titles, captions, hashtags etc. AI when configured, otherwise transparent template-based text."""
import re
from collections import Counter

from . import llm
from .analyze import STOP, _toks

KEYS = ("titles", "captions", "hashtags", "description", "thumbnail_text", "pinned_comment", "youtube_shorts", "instagram_reels")


def heuristic(text: str, hook: str, title: str) -> dict:
    toks = [t for t in _toks(text) if t not in STOP and len(t) > 3 and not t.isdigit()]
    top = [w for w, _ in Counter(toks).most_common(8)]
    topic = top[0] if top else "this"
    tags = ["#" + re.sub(r"\W", "", w) for w in top[:6]] + ["#shorts", "#reels"]
    hook = hook.strip().rstrip(".") or title
    titles = [hook[:70], f"The truth about {topic}", f"What nobody tells you about {topic}", f"{topic.title()} in under a minute",
              f"Watch this before you try {topic}"]
    caps = [f"{hook}. Watch till the end.", f"{title}\n\nWhat do you think? Tell me below.", f"Save this for later: {hook[:90]}"]
    return {
        "titles": titles, "captions": caps, "hashtags": list(dict.fromkeys(tags)),
        "description": f"{hook}. A short clip about {', '.join(top[:3]) or 'this topic'}.",
        "thumbnail_text": " ".join(hook.split()[:5]).upper(),
        "pinned_comment": f"Which part of this surprised you most? 👇",
        "youtube_shorts": {"title": titles[0][:100], "description": f"{hook}\n\n#shorts " + " ".join(tags[:3]), "hashtags": tags[:3] + ["#shorts"]},
        "instagram_reels": {"caption": f"{hook}\n\n" + " ".join(tags[:8]), "hashtags": tags[:8]},
        "engine": "template",
    }


def generate(text: str, hook: str, title: str) -> dict:
    base = heuristic(text, hook, title)
    if not llm.active_provider():
        return base
    prompt = f"""Write social copy for this short video clip. Stay faithful to what is said; no clickbait that misleads, no invented claims.
Clip transcript:\n{text[:4000]}\n
Return JSON with keys: titles (5 strings), captions (3 strings), hashtags (8-12 strings starting with #), description (1-2 sentences),
thumbnail_text (max 5 words), pinned_comment (1 sentence), youtube_shorts {{title, description, hashtags (3-5)}},
instagram_reels {{caption (with line breaks), hashtags (5-10)}}."""
    try:
        r = llm.generate_json(prompt, "You write honest, engaging short-form video copy. JSON only.")
        out = {**base, "engine": llm.active_provider()}
        for k in KEYS:
            if k in r and r[k]:
                out[k] = r[k]
        if not isinstance(out["titles"], list) or not isinstance(out["captions"], list):
            return base
        return out
    except llm.LLMError as e:
        base["note"] = f"AI unavailable ({e}); showing template text."
        return base
