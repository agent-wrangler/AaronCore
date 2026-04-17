from __future__ import annotations

import base64
import binascii
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from uuid import uuid4

from storage.paths import CHAT_UPLOADS_DIR


CHAT_UPLOADS_ROUTE_PREFIX = "/chat-uploads"


def _normalize_relative_upload_path(path: str | None) -> str | None:
    raw = str(path or "").strip().replace("\\", "/")
    if not raw:
        return None
    pure = PurePosixPath(raw)
    if pure.is_absolute():
        return None
    if not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        return None
    return pure.as_posix()


def _resolve_upload_path(path: str | None) -> Path | None:
    normalized = _normalize_relative_upload_path(path)
    if not normalized:
        return None
    target = (CHAT_UPLOADS_DIR / Path(normalized)).resolve()
    try:
        target.relative_to(CHAT_UPLOADS_DIR.resolve())
    except Exception:
        return None
    return target


def _decode_base64_payload(raw_payload: str | None) -> bytes:
    raw = str(raw_payload or "").strip()
    if not raw:
        return b""
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error):
        return b""


def _detect_image_kind(data: bytes) -> tuple[str, str] | None:
    if not data:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif", "image/gif"
    if data.startswith(b"BM"):
        return ".bmp", "image/bmp"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp", "image/webp"
    return None


def build_chat_attachment_url(path: str | None) -> str | None:
    normalized = _normalize_relative_upload_path(path)
    if not normalized:
        return None
    return CHAT_UPLOADS_ROUTE_PREFIX + "/" + quote(normalized, safe="/")


def persist_inline_chat_images(images: list[str] | None) -> list[dict]:
    saved: list[dict] = []
    for payload in list(images or []):
        data = _decode_base64_payload(payload)
        image_kind = _detect_image_kind(data)
        if not image_kind:
            continue
        ext, mime = image_kind
        day_dir = datetime.now().strftime("%Y%m%d")
        target_dir = CHAT_UPLOADS_DIR / day_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{datetime.now().strftime('%H%M%S_%f')}_{uuid4().hex[:8]}{ext}"
        target_file = target_dir / filename
        target_file.write_bytes(data)
        saved.append(
            {
                "type": "image",
                "path": PurePosixPath(day_dir, filename).as_posix(),
                "mime": mime,
                "size": len(data),
            }
        )
    return saved


def build_public_chat_attachments(raw_attachments) -> list[dict]:
    if not isinstance(raw_attachments, list):
        return []
    public_items: list[dict] = []
    for item in raw_attachments:
        if not isinstance(item, dict):
            continue
        rel_path = _normalize_relative_upload_path(item.get("path"))
        target = _resolve_upload_path(rel_path)
        if not rel_path or target is None or not target.is_file():
            continue
        row = dict(item)
        row["path"] = rel_path
        row["url"] = build_chat_attachment_url(rel_path)
        row["type"] = str(row.get("type") or "image").strip().lower() or "image"
        public_items.append(row)
    return public_items


def delete_chat_attachments(raw_attachments) -> None:
    if not isinstance(raw_attachments, list):
        return
    root = CHAT_UPLOADS_DIR.resolve()
    for item in raw_attachments:
        if not isinstance(item, dict):
            continue
        target = _resolve_upload_path(item.get("path"))
        if target is None:
            continue
        try:
            if target.is_file():
                target.unlink()
        except Exception:
            continue
        parent = target.parent
        while parent != root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
