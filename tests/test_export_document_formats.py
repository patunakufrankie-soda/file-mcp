from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from zipfile import is_zipfile


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
            ("doc", "application/msword", ".doc"),
            ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
            ("xls", "application/vnd.ms-excel", ".xls"),
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

            if format_name == "doc":
                self.assertTrue(file_path.read_text(encoding="utf-8").startswith("{\\rtf1"))
            elif format_name == "xlsx":
                self.assertTrue(is_zipfile(file_path))
            elif format_name == "xls":
                xls_content = file_path.read_text(encoding="utf-8")
                self.assertTrue(xls_content.startswith("<?xml"))
                self.assertIn("<Workbook", xls_content)
            elif format_name == "csv":
                self.assertTrue(file_path.read_text(encoding="utf-8-sig").startswith("标题,内容"))


if __name__ == "__main__":
    unittest.main()
