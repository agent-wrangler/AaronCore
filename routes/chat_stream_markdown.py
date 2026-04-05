from __future__ import annotations

from dataclasses import dataclass
import re

from core.markdown_render import render_markdown_html


_BLOCK_START_RE = re.compile(r"^(?:#{1,6}\s|[-*+]\s+|\d+[.)]\s+|>\s?)")
_COMPLEX_BLOCK_RE = re.compile(r"^\s*(?:[-*+]\s+|#{1,6}\s|>\s|\d+[.)]\s+)", re.MULTILINE)


def _sanitize_stream_render_text(text: str) -> str:
    source = str(text or "")
    if "**" not in source and "__" not in source:
        return source
    if "```" in source:
        return source
    if _COMPLEX_BLOCK_RE.search(source):
        return source
    if len([line for line in source.splitlines() if line.strip()]) > 8:
        return source
    return source.replace("**", "").replace("__", "")


def find_markdown_commit_boundary(text: str) -> int:
    source = str(text or "").replace("\r", "")
    if not source:
        return 0
    lines = source.split("\n")
    offset = 0
    in_fence = False
    last_boundary = 0
    for index, line in enumerate(lines):
        trimmed = str(line or "").strip()
        line_end = offset + len(line)
        block_end = line_end + 1 if index < len(lines) - 1 else line_end
        line_has_break = index < len(lines) - 1
        if trimmed.startswith("```"):
            in_fence = not in_fence
            if not in_fence and line_has_break:
                last_boundary = block_end
            offset = block_end
            continue
        if in_fence:
            offset = block_end
            continue
        if not line_has_break:
            offset = block_end
            continue
        if trimmed == "":
            if block_end > 0:
                last_boundary = block_end
        elif _BLOCK_START_RE.match(trimmed):
            last_boundary = block_end
        offset = block_end
    return last_boundary


@dataclass
class MarkdownIncrementalStream:
    _text: str = ""
    _committed: str = ""

    def reset(self) -> None:
        self._text = ""
        self._committed = ""

    def feed(self, chunk: str) -> dict | None:
        piece = str(chunk or "")
        if not piece:
            return None
        self._text += piece
        return self._build_payload(final=False)

    def flush(self) -> dict | None:
        if not self._text:
            return None
        return self._build_payload(final=True)

    def _build_payload(self, *, final: bool) -> dict | None:
        source = self._text.replace("\r", "")
        boundary = len(source) if final else find_markdown_commit_boundary(source)
        committed = source[:boundary] if boundary > 0 else ""
        tail = "" if final else source[boundary:]

        append: list[dict] = []
        delta = ""
        if committed:
            if committed.startswith(self._committed):
                delta = committed[len(self._committed) :]
            elif not self._committed:
                delta = committed
        if delta:
            rendered_delta = _sanitize_stream_render_text(delta)
            append.append(
                {
                    "kind": "markdown_block",
                    "markdown": delta,
                    "html": render_markdown_html(rendered_delta),
                }
            )
            self._committed = committed

        if not append and not tail:
            return None
        rendered_tail = _sanitize_stream_render_text(tail)
        return {
            "format": "markdown_incremental",
            "append": append,
            "tail": tail,
            "tail_html": render_markdown_html(rendered_tail) if rendered_tail else "",
            "full_text": source,
            "final": bool(final),
        }
