from __future__ import annotations

from pathlib import Path
from typing import Final
from urllib.parse import urlparse

from ..conversion.conversion_matrix import SUPPORTED_FORMATS


CONTENT_TYPE_TO_FORMAT: Final[dict[str, str]] = {
    "text/plain": "txt",
    "text/markdown": "md",
    "text/x-markdown": "md",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


class ConversionError(Exception):
    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message


def normalize_format_name(format_name: str) -> str:
    normalized = (format_name or "").strip().lower()
    if normalized == "markdown":
        return "md"
    if normalized == "text":
        return "txt"
    return normalized


def infer_format_from_name(name: str) -> str | None:
    suffix = Path(name).suffix.lower().lstrip(".")
    normalized = normalize_format_name(suffix)
    if normalized in SUPPORTED_FORMATS:
        return normalized
    return None


def infer_format_from_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    normalized = content_type.split(";", 1)[0].strip().lower()
    return CONTENT_TYPE_TO_FORMAT.get(normalized)


def ensure_supported_target_format(target_format: str) -> str:
    normalized = normalize_format_name(target_format)
    if normalized not in SUPPORTED_FORMATS:
        raise ConversionError(
            "validation_error",
            f"Unsupported target_format: {target_format}. Supported formats: {', '.join(SUPPORTED_FORMATS)}",
        )
    return normalized


def title_from_input_uri(input_uri: str) -> str:
    parsed = urlparse(input_uri)
    candidate = parsed.path if parsed.scheme else input_uri
    stem = Path(candidate).stem.strip()
    return stem or "converted-document"


def format_from_input_uri(input_uri: str) -> str | None:
    parsed = urlparse(input_uri)
    candidate = parsed.path if parsed.scheme else input_uri
    return infer_format_from_name(candidate)


def is_http_url(input_uri: str) -> bool:
    scheme = urlparse(input_uri).scheme.lower()
    return scheme in {"http", "https"}


def is_local_path(input_uri: str) -> bool:
    return not urlparse(input_uri).scheme


def build_failure_result(
    *,
    input_uri: str,
    source_format: str | None = None,
    target_format: str | None = None,
    error_type: str,
    message: str,
) -> dict[str, str | bool]:
    result: dict[str, str | bool] = {
        "success": False,
        "input_uri": input_uri,
        "error_type": error_type,
        "message": message,
    }
    if source_format is not None:
        result["source_format"] = source_format
    if target_format is not None:
        result["target_format"] = target_format
    return result


def status_code_for_error_type(error_type: str) -> int:
    return {
        "validation_error": 400,
        "unsupported_format": 400,
        "file_not_found": 404,
        "download_failed": 502,
        "dependency_missing": 503,
        "conversion_failed": 500,
    }.get(error_type, 500)
