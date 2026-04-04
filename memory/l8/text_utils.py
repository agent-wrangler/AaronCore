"""Text normalization helpers for L8 learning."""

from __future__ import annotations

import re


def normalize_query(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def clean_text(text: str, limit: int | None = None) -> str:
    cleaned = re.sub(r"<[^>]+>", "", str(text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if limit and len(cleaned) > limit:
        return cleaned[: max(limit - 1, 1)] + "…"
    return cleaned
