from __future__ import annotations

import re

# Cartridges that start with ".45" but are not the .45 pistol cartridges we want.
_OTHER_45 = re.compile(r"\.45(?:0|4|8)\b|\.45-70\b|\.460\b", re.I)

# "Glock 45" / "G45" is a 9mm model. "45 gen 6" is that same model in casual writing.
_FALSE_45 = re.compile(
    r"\b(?:glock\s*45|g45|45\s+gen(?:eration)?(?:\s*\d+)?)\b",
    re.I,
)

_PRICE = re.compile(r"\$\s*\d[\d,]*(?:\.\d+)?")

# Explicit chambering. Bare "45" is not enough; "Glock 45" and prices collide with it.
_EXPLICIT = re.compile(
    r"(?<!\w)(?:"
    r"\.45(?![\d-])"
    r"|45\s*a\.?\s*c\.?\s*p\.?"
    r"|45\s*auto(?:matic)?"
    r"|45\s*gap"
    r"|45\s*super"
    r"|45\s*(?:long\s*)?colt"
    r"|45\s*lc"
    r"|45\s*win(?:chester)?\s*mag(?:num)?"
    r"|45\s*cal(?:iber)?"
    r"|colt\s*\.?45"
    r"|usp\s*45"
    r")\b",
    re.I,
)

_STRONG = re.compile(r"acp|auto|gap|super|\blc\b|win|long\s*colt|45\s*colt", re.I)

# Models chambered in .45 ACP and not commonly sold in another caliber.
_MODELS = re.compile(
    r"\b(?:"
    r"glock\s*(?:21|30s?|36|41)\b"
    r"|g(?:21|30|36|41)\b"
    r"|hk\s*45\b|hk45\b"
    r"|fnx[-\s]?45|fnp[-\s]?45"
    r"|xd[-\s]?45|xdm[-\s]?45"
    r"|m\s*&\s*p\s*45\b|m&p\s*45\b"
    r")\b",
    re.I,
)

_BLACK_POWDER = re.compile(
    r"black\s*powder|muzzle\s*loader|muzzleloader|percussion|cap\s+and\s+ball",
    re.I,
)

# Title-only skip list so a Glock 19 listing does not need a page fetch.
# Anything that also mentions a .45 hint is still fetched.
_OBVIOUS_OTHER = re.compile(
    r"\b(?:"
    r"9\s*mm|9x19|\.380\b|380\s*acp|\.40\b|40\s*s\s*&\s*w|10\s*mm"
    r"|\.357\b|357\s*mag|\.38\b|38\s*special|\.22\b|22\s*lr|5\.7|\.44\b|44\s*mag"
    r"|glock\s*(?:17|19|26|34|42|43x?|44|45|47|48|49)\b"
    r"|p365|p320|p226|p229|hellcat|tx\s*22|p-?10\s*[cfsm]\b|shadow\s*2"
    r")\b",
    re.I,
)

_HINT = re.compile(
    r"(?<!\d)\.?45(?!\d)|1911|glock\s*(?:21|30s?|36|41)|hk\s*45|hk45|fnx[-\s]?45|m1911a1",
    re.I,
)

_SKIP_PREFIX = re.compile(r"sold|wtb|delete", re.I)


def normalize(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def evaluate(title: str, body: str = "") -> tuple[bool, str]:
    """Return whether this listing is a .45 pistol, and the phrase that matched."""
    title_n = normalize(title)
    body_n = normalize(body)
    combined = f"{title_n} {body_n}".strip()
    hits = _explicit_hits(combined)
    if _BLACK_POWDER.search(combined):
        hits = [hit for hit in hits if _STRONG.search(hit)]
    if hits:
        return True, _clean_reason(hits[0])
    model = _MODELS.search(title_n)
    if model and not _BLACK_POWDER.search(title_n):
        return True, _clean_reason(model.group(0))
    return False, ""


def should_fetch_body(title: str) -> bool:
    """True when the title is not enough to decide."""
    matched, _reason = evaluate(title, "")
    if matched:
        return False
    title_n = normalize(title)
    if _BLACK_POWDER.search(title_n):
        return False
    cleaned = _FALSE_45.sub(" ", title_n)
    if _HINT.search(cleaned):
        return True
    if _OBVIOUS_OTHER.search(title_n) or _OBVIOUS_OTHER.search(cleaned):
        return False
    return True


def skip_prefix(prefix: str, title: str) -> bool:
    if _SKIP_PREFIX.search(prefix or ""):
        return True
    return bool(re.match(r"\s*(sold|wtb)\b", title or "", re.I))


def snippet(body: str, title: str, limit: int = 320) -> str:
    text = body.strip() if body.strip() else title.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*read more\s*$", "", text, flags=re.I).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _explicit_hits(text: str) -> list[str]:
    cleaned = _PRICE.sub(" ", text)
    cleaned = _OTHER_45.sub(" ", cleaned)
    cleaned = _FALSE_45.sub(" ", cleaned)
    return [match.group(0) for match in _EXPLICIT.finditer(cleaned)]


def _clean_reason(phrase: str) -> str:
    return re.sub(r"\s+", " ", phrase).strip()
