from __future__ import annotations

import json
import logging
import os
import secrets
import time
from collections import deque
from pathlib import Path
from typing import Any, Mapping

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse

from .conversion.conversion_matrix import (
    SupportedConversionsResult,
    get_supported_conversions,
)
from .export.service import ExportDocumentResult, export_document
from .conversion.file_document_convert import FileConvertResult, convert_file_document
from .utils.format_utils import ConversionError, status_code_for_error_type
from .storage.manager import get_export_dir, resolve_export_file

logger = logging.getLogger(__name__)


class FixedWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        if self.limit <= 0:
            return True

        current_time = now if now is not None else time.time()
        window_start = current_time - self.window_seconds
        entries = self._requests.setdefault(key, deque())

        while entries and entries[0] <= window_start:
            entries.popleft()

        if len(entries) >= self.limit:
            return False

        entries.append(current_time)
        return True


def _get_rate_limit_per_minute() -> int:
    raw_value = os.getenv("FORMAT_EXPORT_RATE_LIMIT_PER_MINUTE", "20")
    try:
        return max(0, int(raw_value))
    except ValueError as exc:
        raise ValueError(
            "FORMAT_EXPORT_RATE_LIMIT_PER_MINUTE must be an integer"
        ) from exc


def _get_allowed_origins() -> list[str]:
    raw_value = os.getenv("FORMAT_EXPORT_ALLOWED_ORIGINS", "*")
    origins = [item.strip() for item in raw_value.split(",") if item.strip()]
    return origins or ["*"]


_EXPORT_RATE_LIMITER = FixedWindowRateLimiter(
    limit=_get_rate_limit_per_minute(), window_seconds=60
)


def _request_id_from(request: Request) -> str:
    request_id = request.headers.get("x-request-id", "").strip()
    return request_id or secrets.token_hex(8)


def _duration_ms(start_time: float) -> float:
    return round((time.perf_counter() - start_time) * 1000, 2)


def _log_event(level: int, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))


def classify_export_error(exc: Exception) -> tuple[int, str, str]:
    if isinstance(exc, ConversionError):
        return status_code_for_error_type(exc.error_type), exc.error_type, exc.message
    if isinstance(exc, ValueError):
        return 400, "invalid_request", str(exc)
    if isinstance(exc, PermissionError):
        return 500, "storage_error", "Failed to store exported file"
    if isinstance(exc, OSError):
        return 503, "storage_error", "Export storage is temporarily unavailable"
    return 500, "internal_error", "Internal server error"


def check_storage_readiness() -> tuple[bool, dict[str, Any]]:
    try:
        export_dir = get_export_dir()
        probe_file = export_dir / ".write-check"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink()
        return True, {"status": "ok", "storage_dir": str(export_dir)}
    except PermissionError:
        return (
            False,
            {
                "status": "error",
                "error": {
                    "code": "storage_unavailable",
                    "message": "Export storage is not writable",
                },
            },
        )
    except OSError:
        return (
            False,
            {
                "status": "error",
                "error": {
                    "code": "storage_unavailable",
                    "message": "Export storage is temporarily unavailable",
                },
            },
        )


def _parse_export_payload(payload: Any) -> tuple[str, str, str, list[str]]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")

    parsed_values: list[str] = []
    for field_name in ("title", "content", "format"):
        value = payload.get(field_name, "")
        if value is None or not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        parsed_values.append(value)

    images = payload.get("images", [])
    if images is None:
        images = []
    if not isinstance(images, list) or any(
        not isinstance(item, str) for item in images
    ):
        raise ValueError("images must be a list of strings")

    return tuple(parsed_values + [images])  # type: ignore[return-value]


def _parse_convert_file_payload(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")

    input_uri = payload.get("input_uri", "")
    target_format = payload.get("target_format", "")

    if not isinstance(input_uri, str):
        raise ValueError("input_uri must be a string")
    if not isinstance(target_format, str):
        raise ValueError("target_format must be a string")
    return input_uri, target_format


def _http_result_with_request_id(
    result: Mapping[str, Any], request_id: str
) -> dict[str, Any]:
    return {**result, "request_id": request_id}


def create_http_middleware() -> list[Middleware]:
    allowed_origins = _get_allowed_origins()
    cors_kwargs: dict[str, Any] = {
        "allow_methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["*"],
        "expose_headers": ["X-Request-ID"],
    }
    if allowed_origins == ["*"]:
        # Keep wildcard CORS behavior stable across Starlette releases:
        # some versions emit "*", others mirror the request origin only when
        # credentials or a regex path is involved.
        cors_kwargs["allow_origins"] = ["*"]
        cors_kwargs["allow_origin_regex"] = None
        cors_kwargs["allow_credentials"] = False
    else:
        cors_kwargs["allow_origins"] = allowed_origins
    return [Middleware(CORSMiddleware, **cors_kwargs)]


def create_mcp() -> FastMCP:
    mcp = FastMCP("Format Export MCP")

    @mcp.tool(name="export_document")
    def export_document_tool(
        title: str,
        content: str,
        format: str,
        images: list[str] | None = None,
    ) -> ExportDocumentResult:
        """
        Export text content, or text plus images, to a document file.

        Args:
            title: Document title and filename stem.
            content: Text content to export.
            format: Target format: pdf, docx, xlsx, csv, txt, md, markdown, or html.
            images: Optional image list. If present, only pdf and docx are supported.
        """
        return export_document(
            title=title, content=content, format=format, images=images
        )

    @mcp.tool(name="convert_file_document")
    def convert_file_document_tool(
        input_uri: str,
        target_format: str,
    ) -> FileConvertResult:
        """
        Convert a local file path or HTTP/HTTPS file URL into another supported document format.

        Args:
            input_uri: Local file path or remote file URL.
            target_format: Target format: txt, md, pdf, or docx.
        """
        return convert_file_document(input_uri=input_uri, target_format=target_format)

    @mcp.tool(name="get_supported_conversions")
    def get_supported_conversions_tool() -> SupportedConversionsResult:
        """Return the supported file conversion matrix."""
        return get_supported_conversions()

    @mcp.custom_route("/", methods=["GET"])
    async def index(request: Request) -> HTMLResponse:
        html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Format Export MCP</title>
  <style>
    body { max-width: 760px; margin: 48px auto; padding: 0 24px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2937; line-height: 1.7; }
    code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>Format Export MCP</h1>
  <p>Service is running.</p>
  <p>MCP endpoint: <code>/mcp/</code></p>
  <p>Health check: <code>/health</code></p>
  <p>Frontend export API: <code>POST /api/export_document</code></p>
  <p>Frontend file convert API: <code>POST /api/convert_file_document</code></p>
  <p>Supported conversions API: <code>GET /api/supported_conversions</code></p>
</body>
</html>"""
        return HTMLResponse(html)

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "Format Export MCP"})

    @mcp.custom_route("/ready", methods=["GET"])
    async def readiness_check(request: Request) -> JSONResponse:
        ready, payload = check_storage_readiness()
        return JSONResponse(payload, status_code=200 if ready else 503)

    @mcp.custom_route("/api/export_document", methods=["POST"])
    async def export_document_api(request: Request) -> JSONResponse:
        start_time = time.perf_counter()
        request_id = _request_id_from(request)
        client_host = request.client.host if request.client else "unknown"
        if not _EXPORT_RATE_LIMITER.allow(client_host):
            _log_event(
                logging.WARNING,
                "export_document.rate_limited",
                request_id=request_id,
                client_host=client_host,
                status_code=429,
                duration_ms=_duration_ms(start_time),
            )
            return JSONResponse(
                {
                    "success": False,
                    "request_id": request_id,
                    "error": {"code": "rate_limited", "message": "Rate limit exceeded"},
                },
                status_code=429,
                headers={"X-Request-ID": request_id},
            )

        try:
            payload = await request.json()
            title, content, format_name, images = _parse_export_payload(payload)
            result = export_document(
                title=title, content=content, format=format_name, images=images
            )
        except Exception as exc:
            status_code, error_code, message = classify_export_error(exc)
            _log_event(
                logging.ERROR,
                "export_document.failed",
                request_id=request_id,
                client_host=client_host,
                status_code=status_code,
                error_code=error_code,
                exception_type=type(exc).__name__,
                duration_ms=_duration_ms(start_time),
            )
            return JSONResponse(
                {
                    "success": False,
                    "request_id": request_id,
                    "error": {"code": error_code, "message": message},
                },
                status_code=status_code,
                headers={"X-Request-ID": request_id},
            )

        _log_event(
            logging.INFO,
            "export_document.completed",
            request_id=request_id,
            client_host=client_host,
            status_code=200,
            format=format_name,
            file_name=result["file_name"],
            duration_ms=_duration_ms(start_time),
        )
        return JSONResponse(result, headers={"X-Request-ID": request_id})

    @mcp.custom_route("/api/convert_file_document", methods=["POST"])
    async def convert_file_document_api(request: Request) -> JSONResponse:
        start_time = time.perf_counter()
        request_id = _request_id_from(request)
        client_host = request.client.host if request.client else "unknown"
        if not _EXPORT_RATE_LIMITER.allow(client_host):
            _log_event(
                logging.WARNING,
                "convert_file_document.rate_limited",
                request_id=request_id,
                client_host=client_host,
                status_code=429,
                duration_ms=_duration_ms(start_time),
            )
            return JSONResponse(
                {
                    "success": False,
                    "request_id": request_id,
                    "error": {"code": "rate_limited", "message": "Rate limit exceeded"},
                },
                status_code=429,
                headers={"X-Request-ID": request_id},
            )

        try:
            payload = await request.json()
            input_uri, target_format = _parse_convert_file_payload(payload)
            result = convert_file_document(
                input_uri=input_uri, target_format=target_format
            )
        except Exception as exc:
            status_code, error_code, message = classify_export_error(exc)
            _log_event(
                logging.ERROR,
                "convert_file_document.failed",
                request_id=request_id,
                client_host=client_host,
                status_code=status_code,
                error_code=error_code,
                exception_type=type(exc).__name__,
                duration_ms=_duration_ms(start_time),
            )
            return JSONResponse(
                {
                    "success": False,
                    "request_id": request_id,
                    "error": {"code": error_code, "message": message},
                },
                status_code=status_code,
                headers={"X-Request-ID": request_id},
            )

        if not result.get("success", False):
            error_type = str(result.get("error_type", "conversion_failed"))
            status_code = status_code_for_error_type(error_type)
            log_level = logging.WARNING if status_code < 500 else logging.ERROR
            _log_event(
                log_level,
                "convert_file_document.failed",
                request_id=request_id,
                client_host=client_host,
                status_code=status_code,
                error_code=error_type,
                duration_ms=_duration_ms(start_time),
            )
            return JSONResponse(
                _http_result_with_request_id(result, request_id),
                status_code=status_code,
                headers={"X-Request-ID": request_id},
            )

        _log_event(
            logging.INFO,
            "convert_file_document.completed",
            request_id=request_id,
            client_host=client_host,
            status_code=200,
            source_format=result.get("source_format"),
            target_format=result.get("target_format"),
            output_path=result.get("output_path"),
            duration_ms=_duration_ms(start_time),
        )
        return JSONResponse(
            _http_result_with_request_id(result, request_id),
            headers={"X-Request-ID": request_id},
        )

    @mcp.custom_route("/api/supported_conversions", methods=["GET"])
    async def supported_conversions_api(request: Request) -> JSONResponse:
        request_id = _request_id_from(request)
        return JSONResponse(
            _http_result_with_request_id(get_supported_conversions(), request_id),
            headers={"X-Request-ID": request_id},
        )

    @mcp.custom_route("/api/get_supported_conversions", methods=["POST"])
    async def supported_conversions_post_api(request: Request) -> JSONResponse:
        request_id = _request_id_from(request)
        return JSONResponse(
            _http_result_with_request_id(get_supported_conversions(), request_id),
            headers={"X-Request-ID": request_id},
        )

    @mcp.custom_route("/downloads/{file_name}", methods=["GET"])
    async def download_file(request: Request) -> FileResponse | JSONResponse:
        file_name = request.path_params["file_name"]
        try:
            file_path = resolve_export_file(file_name)
        except ValueError as exc:
            return JSONResponse(
                {"success": False, "message": str(exc)}, status_code=400
            )

        if not Path(file_path).exists():
            return JSONResponse(
                {"success": False, "message": "File not found"}, status_code=404
            )
        return FileResponse(file_path, filename=file_path.name)

    return mcp
