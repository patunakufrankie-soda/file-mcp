from __future__ import annotations

import ipaddress
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from .format_utils import (
    ConversionError,
    infer_format_from_content_type,
    infer_format_from_name,
)


DEFAULT_DOWNLOAD_TIMEOUT_SECONDS = 20
DEFAULT_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


@dataclass(slots=True)
class LoadedInput:
    input_uri: str
    local_path: Path
    source_format: str
    cleanup_dir: tempfile.TemporaryDirectory[str] | None = None

    def cleanup(self) -> None:
        if self.cleanup_dir is not None:
            self.cleanup_dir.cleanup()


def _validate_source_format(source_format: str | None, input_uri: str) -> str:
    if source_format is None:
        raise ConversionError(
            "unsupported_format",
            f"Unable to determine source format from input_uri: {input_uri}. Supported formats: txt, md, pdf, docx",
        )
    return source_format


def _load_local_input(input_uri: str) -> LoadedInput:
    local_path = Path(input_uri).expanduser()
    if not local_path.exists() or not local_path.is_file():
        raise ConversionError("file_not_found", f"Input file not found: {input_uri}")

    source_format = _validate_source_format(
        infer_format_from_name(local_path.name), input_uri
    )
    return LoadedInput(
        input_uri=input_uri, local_path=local_path, source_format=source_format
    )


def _is_local_or_internal(url: str) -> bool:
    """判断是否为本地或内网地址，应跳过代理"""
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return False

    # localhost
    if host in ("localhost", "127.0.0.1", "::1"):
        return True

    # 内网段（10.x.x.x, 172.16-31.x.x, 192.168.x.x）
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback
    except ValueError:
        # 域名形式，检查常见内网后缀
        return host.endswith((".local", ".internal", ".lan"))


def _download_remote_input(input_uri: str) -> LoadedInput:
    parsed = urlparse(input_uri)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ConversionError(
            "validation_error",
            f"Unsupported input URI scheme: {parsed.scheme or 'unknown'}",
        )

    temp_dir = tempfile.TemporaryDirectory(prefix="format-export-input-")

    # 内网/本地地址跳过代理
    proxies = (
        {"http": None, "https": None} if _is_local_or_internal(input_uri) else None
    )

    try:
        response = requests.get(
            input_uri,
            stream=True,
            timeout=DEFAULT_DOWNLOAD_TIMEOUT_SECONDS,
            proxies=proxies,
        )
    except requests.RequestException as exc:
        temp_dir.cleanup()
        raise ConversionError(
            "download_failed", f"Failed to download input file: {exc}"
        ) from exc

    try:
        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if (
            content_length is not None
            and int(content_length) > DEFAULT_MAX_DOWNLOAD_BYTES
        ):
            raise ConversionError(
                "download_failed", "Input file is too large to download"
            )

        source_format = infer_format_from_name(
            parsed.path
        ) or infer_format_from_content_type(response.headers.get("Content-Type"))
        source_format = _validate_source_format(source_format, input_uri)

        output_path = Path(temp_dir.name) / f"downloaded-input.{source_format}"
        written = 0
        with output_path.open("wb") as file_obj:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                written += len(chunk)
                if written > DEFAULT_MAX_DOWNLOAD_BYTES:
                    raise ConversionError(
                        "download_failed",
                        "Input file exceeds the maximum supported size",
                    )
                file_obj.write(chunk)

        return LoadedInput(
            input_uri=input_uri,
            local_path=output_path,
            source_format=source_format,
            cleanup_dir=temp_dir,
        )
    except Exception:
        temp_dir.cleanup()
        raise
    finally:
        response.close()


def load_input(input_uri: str) -> LoadedInput:
    if not isinstance(input_uri, str) or not input_uri.strip():
        raise ConversionError(
            "validation_error", "input_uri must be a non-empty string"
        )

    normalized = input_uri.strip()

    # 自动拼接内网文件服务 URL：检测到 /api/file/ 开头的相对路径时自动补全
    if normalized.startswith("/api/file/") or normalized.startswith("/"):
        import os
        from ..nacos.manager import NacosManager

        # 优先从 Nacos 获取，其次环境变量
        base_url = NacosManager.get_config("file_server.base_url")
        if not base_url:
            base_url = os.getenv("FILE_SERVER_BASE_URL")

        if not base_url:
            raise ConversionError(
                "validation_error",
                f"Relative file path detected ({normalized}) but base URL not configured. "
                "Set file_server.base_url in Nacos or FILE_SERVER_BASE_URL environment variable",
            )
        normalized = base_url.rstrip("/") + normalized

    parsed = urlparse(normalized)
    if parsed.scheme in {"", None}:
        return _load_local_input(normalized)
    if parsed.scheme.lower() in {"http", "https"}:
        return _download_remote_input(normalized)
    raise ConversionError(
        "validation_error", f"Unsupported input URI scheme: {parsed.scheme}"
    )
