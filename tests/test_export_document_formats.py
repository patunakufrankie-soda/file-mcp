from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from zipfile import is_zipfile

import httpx


def request_asgi(app, method: str, url: str, **kwargs) -> httpx.Response:
    async def _request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, url, **kwargs)

    return asyncio.run(_request())


class ExportDocumentFormatTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["FORMAT_EXPORT_STORAGE_DIR"] = self._tmpdir.name
        os.environ["FORMAT_EXPORT_PUBLIC_BASE_URL"] = "/downloads"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_exports_doc_xlsx_xls_and_csv(self) -> None:
        from format_export_mcp.tools.export_document import export_document

        cases = [
            ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
            ("csv", "text/csv", ".csv"),
        ]

        for format_name, _, suffix in cases:
            result = export_document(
                title="测试导出",
                content="标题,内容\nA,1\nB,2",
                format=format_name,
            )
            file_path = Path(self._tmpdir.name) / result["file_name"]

            self.assertTrue(result["success"])
            self.assertTrue(result["file_name"].endswith(suffix))
            self.assertEqual(result["file_url"], f"/downloads/{result['file_name']}")
            self.assertTrue(file_path.exists(), msg=f"expected exported file for {format_name}")

            if format_name == "xlsx":
                self.assertTrue(is_zipfile(file_path))
            elif format_name == "csv":
                self.assertTrue(file_path.read_text(encoding="utf-8-sig").startswith("标题,内容"))

    def test_tabular_exports_preserve_quoted_commas(self) -> None:
        from format_export_mcp.tools.export_document import export_document

        content = '标题,内容\nA,"b,c"'

        csv_result = export_document(title="表格", content=content, format="csv")
        csv_path = Path(self._tmpdir.name) / csv_result["file_name"]
        self.assertEqual(csv_path.read_text(encoding="utf-8-sig"), '标题,内容\nA,"b,c"\n')

        xlsx_result = export_document(title="表格", content=content, format="xlsx")
        xlsx_path = Path(self._tmpdir.name) / xlsx_result["file_name"]
        with ZipFile(xlsx_path) as archive:
            sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn('r="A2"', sheet_xml)
        self.assertIn('r="B2"', sheet_xml)
        self.assertNotIn('r="C2"', sheet_xml)
        self.assertIn("<t>b,c</t>", sheet_xml)

    def test_http_payload_validation_rejects_none_and_non_string_values(self) -> None:
        from format_export_mcp.server_common import _parse_export_payload

        self.assertEqual(
            _parse_export_payload({"title": "标题", "content": "内容", "format": "pdf"}),
            ("标题", "内容", "pdf"),
        )

        with self.assertRaisesRegex(ValueError, "title must be a string"):
            _parse_export_payload({"title": None, "content": "内容", "format": "pdf"})

        with self.assertRaisesRegex(ValueError, "content must be a string"):
            _parse_export_payload({"title": "标题", "content": 123, "format": "pdf"})

        with self.assertRaisesRegex(ValueError, "JSON object"):
            _parse_export_payload(["not", "an", "object"])

    def test_legacy_doc_and_xls_formats_are_rejected(self) -> None:
        from format_export_mcp.tools.export_document import export_document

        with self.assertRaisesRegex(ValueError, "Unsupported format: doc"):
            export_document(title="标题", content="内容", format="doc")

        with self.assertRaisesRegex(ValueError, "Unsupported format: xls"):
            export_document(title="标题", content="内容", format="xls")

    def test_export_prunes_expired_files_before_writing_new_one(self) -> None:
        from format_export_mcp.tools.export_document import export_document

        os.environ["FORMAT_EXPORT_FILE_TTL_SECONDS"] = "60"
        expired_file = Path(self._tmpdir.name) / "expired.txt"
        expired_file.write_text("old", encoding="utf-8")
        old_timestamp = time.time() - 120
        os.utime(expired_file, (old_timestamp, old_timestamp))

        result = export_document(title="新文件", content="内容", format="txt")
        new_file = Path(self._tmpdir.name) / result["file_name"]

        self.assertFalse(expired_file.exists())
        self.assertTrue(new_file.exists())

    def test_fixed_window_rate_limiter_blocks_after_limit(self) -> None:
        from format_export_mcp.server_common import FixedWindowRateLimiter

        limiter = FixedWindowRateLimiter(limit=2, window_seconds=60)

        self.assertTrue(limiter.allow("127.0.0.1", now=100.0))
        self.assertTrue(limiter.allow("127.0.0.1", now=110.0))
        self.assertFalse(limiter.allow("127.0.0.1", now=120.0))
        self.assertTrue(limiter.allow("127.0.0.1", now=161.0))

    def test_sse_server_defaults_to_all_interfaces(self) -> None:
        from format_export_mcp import server_sse

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(server_sse.mcp, "run") as run:
                server_sse.main()

        run.assert_called_once_with(transport="sse", host="0.0.0.0", port=8000)

    def test_classify_export_error_maps_common_runtime_failures(self) -> None:
        from format_export_mcp.server_common import classify_export_error

        status_code, error_code, _ = classify_export_error(ValueError("bad input"))
        self.assertEqual((status_code, error_code), (400, "invalid_request"))

        status_code, error_code, _ = classify_export_error(PermissionError("no write"))
        self.assertEqual((status_code, error_code), (500, "storage_error"))

        status_code, error_code, _ = classify_export_error(OSError("disk full"))
        self.assertEqual((status_code, error_code), (503, "storage_error"))

        status_code, error_code, _ = classify_export_error(RuntimeError("boom"))
        self.assertEqual((status_code, error_code), (500, "internal_error"))

    def test_export_document_api_returns_structured_error_for_runtime_failures(self) -> None:
        from format_export_mcp.server_common import create_mcp

        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/")

        with patch(
            "format_export_mcp.server_common.export_document",
            side_effect=PermissionError("no write"),
        ):
            with self.assertLogs("format_export_mcp.server_common", level="ERROR"):
                response = request_asgi(
                    app,
                    "POST",
                    "/api/export_document",
                    json={"title": "标题", "content": "内容", "format": "txt"},
                    headers={"X-Request-ID": "req-storage-failure"},
                )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["x-request-id"], "req-storage-failure")
        self.assertEqual(
            response.json(),
            {
                "success": False,
                "request_id": "req-storage-failure",
                "error": {"code": "storage_error", "message": "Failed to store exported file"},
            },
        )

    def test_export_document_api_returns_request_id_and_structured_success_log(self) -> None:
        from format_export_mcp.server_common import create_mcp

        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/")

        with self.assertLogs("format_export_mcp.server_common", level="INFO") as logs:
            response = request_asgi(
                app,
                "POST",
                "/api/export_document",
                json={"title": "标题", "content": "内容", "format": "txt"},
                headers={"X-Request-ID": "req-success"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-request-id"], "req-success")

        event = json.loads(logs.records[0].getMessage())
        self.assertEqual(event["event"], "export_document.completed")
        self.assertEqual(event["request_id"], "req-success")
        self.assertEqual(event["status_code"], 200)
        self.assertEqual(event["format"], "txt")
        self.assertIn("duration_ms", event)
        self.assertIn("file_name", event)

    def test_storage_readiness_checks_directory_writability(self) -> None:
        from format_export_mcp.server_common import check_storage_readiness

        ready, details = check_storage_readiness()
        self.assertTrue(ready)
        self.assertEqual(details["status"], "ok")
        self.assertEqual(details["storage_dir"], self._tmpdir.name)

    def test_storage_readiness_reports_os_errors(self) -> None:
        from format_export_mcp.server_common import check_storage_readiness

        with patch(
            "format_export_mcp.server_common.get_export_dir",
            side_effect=OSError("disk offline"),
        ):
            ready, details = check_storage_readiness()

        self.assertFalse(ready)
        self.assertEqual(details["status"], "error")
        self.assertEqual(details["error"]["code"], "storage_unavailable")

    def test_ready_endpoint_returns_503_when_storage_not_ready(self) -> None:
        from format_export_mcp.server_common import create_mcp

        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/")

        with patch(
            "format_export_mcp.server_common.check_storage_readiness",
            return_value=(
                False,
                {
                    "status": "error",
                    "error": {
                        "code": "storage_unavailable",
                        "message": "Export storage is temporarily unavailable",
                    },
                },
            ),
        ):
            response = request_asgi(app, "GET", "/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "storage_unavailable")


if __name__ == "__main__":
    unittest.main()
