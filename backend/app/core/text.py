"""Small text helpers."""

import re
import unicodedata


def slugify(value: str, *, fallback: str = "item") -> str:
    normalized = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or fallback
