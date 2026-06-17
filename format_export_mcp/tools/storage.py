from __future__ import annotations

import os
import re
import secrets
import time
import unicodedata
from pathlib import Path
from urllib.parse import urljoin


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_DIR = PROJECT_ROOT / "storage" / "exports"


def get_export_dir() -> Path:
    """Return the export directory, typically an NFS mount in production."""
    export_dir = Path(os.getenv("FORMAT_EXPORT_STORAGE_DIR", str(DEFAULT_EXPORT_DIR)))
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def get_public_base_url() -> str:
    return os.getenv("FORMAT_EXPORT_PUBLIC_BASE_URL", "/downloads").rstrip("/")


def get_file_ttl_seconds() -> int:
    raw_value = os.getenv("FORMAT_EXPORT_FILE_TTL_SECONDS", str(7 * 24 * 60 * 60))
    try:
        return max(0, int(raw_value))
    except ValueError as exc:
        raise ValueError("FORMAT_EXPORT_FILE_TTL_SECONDS must be an integer") from exc


def safe_stem(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title or "").strip().lower()
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"[^\w\-\u4e00-\u9fff]+", "", normalized, flags=re.UNICODE)
    normalized = normalized.strip("-_")
    return normalized[:80] or "export"


def build_output_path(title: str, extension: str) -> Path:
    suffix = extension.lower().lstrip(".")
    token = secrets.token_hex(4)
    return get_export_dir() / f"{safe_stem(title)}-{token}.{suffix}"


def join_public_url(file_name: str, base_url: str | None = None, object_key: str | None = None) -> str:
    base = (base_url or get_public_base_url()).rstrip("/")
    target = object_key or file_name
    if base.startswith("http://") or base.startswith("https://"):
        return urljoin(f"{base}/", target)
    return f"{base}/{target}"


def build_file_url(file_name: str) -> str:
    return join_public_url(file_name)


def prune_expired_exports(now: float | None = None) -> None:
    ttl_seconds = get_file_ttl_seconds()
    if ttl_seconds <= 0:
        return

    cutoff = (now if now is not None else time.time()) - ttl_seconds
    export_dir = get_export_dir()
    for candidate in export_dir.iterdir():
        if not candidate.is_file():
            continue
        try:
            if candidate.stat().st_mtime < cutoff:
                candidate.unlink()
        except FileNotFoundError:
            continue


def store_export_file(local_path: Path, file_name: str) -> Path:
    export_dir = get_export_dir()
    target = export_dir / file_name
    if local_path.resolve() != target.resolve():
        target.write_bytes(local_path.read_bytes())
    return target


def resolve_export_file(file_name: str) -> Path:
    export_dir = get_export_dir().resolve()
    candidate = (export_dir / Path(file_name).name).resolve()
    if export_dir not in candidate.parents and candidate != export_dir:
        raise ValueError("Invalid export file path")
    return candidate
