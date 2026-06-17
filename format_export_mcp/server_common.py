from __future__ import annotations

import json
import logging
import os
import secrets
import time
from collections import deque
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse

from .tools.export_document import ExportDocumentResult, export_document
from .tools.storage import get_export_dir, resolve_export_file

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
        raise ValueError("FORMAT_EXPORT_RATE_LIMIT_PER_MINUTE must be an integer") from exc


_EXPORT_RATE_LIMITER = FixedWindowRateLimiter(limit=_get_rate_limit_per_minute(), window_seconds=60)


def _request_id_from(request: Request) -> str:
    request_id = request.headers.get("x-request-id", "").strip()
    return request_id or secrets.token_hex(8)


def _duration_ms(start_time: float) -> float:
    return round((time.perf_counter() - start_time) * 1000, 2)


def _log_event(level: int, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))


def classify_export_error(exc: Exception) -> tuple[int, str, str]:
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


def _parse_export_payload(payload: Any) -> tuple[str, str, str]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")

    parsed_values: list[str] = []
    for field_name in ("title", "content", "format"):
        value = payload.get(field_name, "")
        if value is None or not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        parsed_values.append(value)

    return tuple(parsed_values)  # type: ignore[return-value]


def create_mcp() -> FastMCP:
    mcp = FastMCP("Format Export MCP")

    @mcp.tool(name="export_document")
    def export_document_tool(title: str, content: str, format: str) -> ExportDocumentResult:
        """
        Export plain text or generated content to pdf, docx, xlsx, csv, txt, md, or html.

        Args:
            title: Document title and filename stem.
            content: Text content to export.
            format: Target format: pdf, docx, xlsx, csv, txt, md, markdown, or html.
        """
        return export_document(title=title, content=content, format=format)

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
            title, content, format_name = _parse_export_payload(payload)
            result = export_document(title=title, content=content, format=format_name)
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

    @mcp.custom_route("/downloads/{file_name}", methods=["GET"])
    async def download_file(request: Request) -> FileResponse | JSONResponse:
        file_name = request.path_params["file_name"]
        try:
            file_path = resolve_export_file(file_name)
        except ValueError as exc:
            return JSONResponse({"success": False, "message": str(exc)}, status_code=400)

        if not Path(file_path).exists():
            return JSONResponse({"success": False, "message": "File not found"}, status_code=404)
        return FileResponse(file_path, filename=file_path.name)

    return mcp
