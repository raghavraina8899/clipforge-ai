"""Hinglish = Hindi written in English letters. Whisper outputs Devanagari for Hindi speech; this converts it
to a natural romanization (no scholarly diacritics) so captions read the way people type Hindi online."""
import re

DEV = re.compile(r"[ऀ-ॿ]+")


def has_devanagari(text: str) -> bool:
    return bool(DEV.search(text))


def _word(dev: str) -> str:
    from indic_transliteration import sanscript
    r = sanscript.transliterate(dev, sanscript.DEVANAGARI, sanscript.ITRANS)
    # inherent final 'a' is silent in Hindi (kamal, gem, bahut); long 'A' is capital in ITRANS so it is kept
    r = re.sub(r"(?<=[^aeiouAEIOU\s])a$", "", r)
    # inner schwa deletion (aapko, samjhana): drop a short 'a' in  V C [a] C V  position
    V, C = "aeiouAEIOU", "bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ"
    dig = "[bcdgjkpt]h|ch|sh"
    r = re.sub(rf"(?:(?<=[{V}][{C}])|(?<=[{V}][bcdgjkpt]h))a(?=(?:{dig}|[{C}])[{V}])", "", r)
    r = re.sub(r"^A", "aa", r)
    for a, b in (("j~n", "gy"), ("kSh", "ksh"), ("GY", "gy"), ("Ch", "chh"), ("Sh", "sh"), (".Dh", "rh"), (".D", "r"), ("RRi", "ri"), ("R^i", "ri"),
                 ("~N", "n"), (".N", "n"), (".n", "n"), ("M", "n"), ("H", "h"), ("A", "a"), ("I", "i"), ("U", "u"), ("^", ""), ("L", "l")):
        r = r.replace(a, b)
    r = r.lower()
    r = re.sub(r"(?<=[^aeiou])ie$", "iye", r)   # चाहिए chahiye, लिए liye, दीजिए dijiye
    r = re.sub(r"ae$", "aye", r)                # गए gaye
    return r


def romanize(text: str) -> str:
    """Convert any Devanagari in `text` to Hinglish; Latin text (e.g. English words) is left unchanged."""
    if not has_devanagari(text):
        return text
    return DEV.sub(lambda m: _word(m.group(0)), text)


def romanize_words(words: list) -> int:
    n = 0
    for w in words:
        if has_devanagari(w["w"]):
            w["w"] = romanize(w["w"]); n += 1
    return n
