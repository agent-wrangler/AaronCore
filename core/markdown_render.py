from __future__ import annotations

import re

try:
    from markdown_it import MarkdownIt
except Exception:  # pragma: no cover
    MarkdownIt = None


_MARKDOWN_RENDERER = (
    MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": False})
    if MarkdownIt
    else None
)
_ANCHOR_TAG_RE = re.compile(r"<a\b", re.I)


def _decorate_links(html: str) -> str:
    if not html:
        return ""
    return _ANCHOR_TAG_RE.sub('<a target="_blank" rel="noopener noreferrer"', html)


def render_markdown_html(markdown_text: str) -> str:
    text = str(markdown_text or "").strip()
    if not text:
        return ""
    if _MARKDOWN_RENDERER is not None:
        try:
            return _decorate_links(_MARKDOWN_RENDERER.render(text))
        except Exception:
            pass
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<p>{escaped}</p>"
