from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse

from .tools.export_document import ExportDocumentResult, export_document
from .tools.storage import resolve_export_file


def create_mcp() -> FastMCP:
    mcp = FastMCP("Format Export MCP")

    @mcp.tool(name="export_document")
    def export_document_tool(title: str, content: str, format: str) -> ExportDocumentResult:
        """
        Export plain text or generated content to pdf, docx, doc, xlsx, xls, csv, txt, md, or html.

        Args:
            title: Document title and filename stem.
            content: Text content to export.
            format: Target format: pdf, docx, doc, xlsx, xls, csv, txt, md, markdown, or html.
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

    @mcp.custom_route("/api/export_document", methods=["POST"])
    async def export_document_api(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
            result = export_document(
                title=str(payload.get("title", "")),
                content=str(payload.get("content", "")),
                format=str(payload.get("format", "")),
            )
        except ValueError as exc:
            return JSONResponse({"success": False, "message": str(exc)}, status_code=400)
        return JSONResponse(result)

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
