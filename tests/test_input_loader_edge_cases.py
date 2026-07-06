"""
边界条件和异常场景测试
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from format_export_mcp.utils.input_loader import load_input
from format_export_mcp.utils.format_utils import ConversionError


class InputLoaderEdgeCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_rejects_empty_input_uri(self) -> None:
        with self.assertRaisesRegex(ConversionError, "non-empty string"):
            load_input("")

    def test_rejects_whitespace_only_input_uri(self) -> None:
        with self.assertRaisesRegex(ConversionError, "non-empty string"):
            load_input("   ")

    def test_rejects_non_string_input_uri(self) -> None:
        with self.assertRaisesRegex(ConversionError, "non-empty string"):
            load_input(None)  # type: ignore

    def test_rejects_non_existent_local_file(self) -> None:
        with self.assertRaisesRegex(ConversionError, "Input file not found"):
            load_input("/nonexistent/path/to/file.txt")

    def test_rejects_unsupported_file_extension(self) -> None:
        source = Path(self._tmpdir.name) / "unsupported.xyz"
        source.write_text("content", encoding="utf-8")
        with self.assertRaisesRegex(
            ConversionError, "Unable to determine source format"
        ):
            load_input(str(source))

    def test_rejects_unsupported_url_scheme(self) -> None:
        with self.assertRaisesRegex(ConversionError, "Unsupported input URI scheme"):
            load_input("ftp://example.com/file.txt")

    def test_rejects_relative_api_path_without_base_url(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                ConversionError, "base URL not configured"
            ):
                load_input("/api/file/12345.txt")

    def test_accepts_relative_api_path_with_base_url(self) -> None:
        source = Path(self._tmpdir.name) / "remote.txt"
        source.write_text("api content", encoding="utf-8")

        # 模拟内网文件服务URL拼接
        with patch.dict(os.environ, {"FILE_SERVER_BASE_URL": "http://localhost:8000"}):
            with patch(
                "format_export_mcp.utils.input_loader._download_remote_input"
            ) as mock_download:
                # 模拟成功下载
                from format_export_mcp.utils.input_loader import LoadedInput

                mock_download.return_value = LoadedInput(
                    input_uri="http://localhost:8000/api/file/12345.txt",
                    local_path=source,
                    source_format="txt",
                    cleanup_dir=None,
                )
                result = load_input("/api/file/12345.txt")
                self.assertEqual(result.source_format, "txt")
                mock_download.assert_called_once_with(
                    "http://localhost:8000/api/file/12345.txt"
                )

    def test_accepts_utf8_sig_bom_files(self) -> None:
        source = Path(self._tmpdir.name) / "bom.txt"
        source.write_text("\ufeffUTF-8 BOM content", encoding="utf-8-sig")

        result = load_input(str(source))
        self.assertEqual(result.source_format, "txt")
        self.assertTrue(result.local_path.exists())
        result.cleanup()

    def test_load_local_md_file(self) -> None:
        source = Path(self._tmpdir.name) / "sample.md"
        source.write_text("# Markdown", encoding="utf-8")

        result = load_input(str(source))
        self.assertEqual(result.source_format, "md")
        self.assertEqual(result.input_uri, str(source))
        result.cleanup()

    def test_load_local_pdf_file(self) -> None:
        from format_export_mcp.export.service import export_document

        os.environ["FORMAT_EXPORT_STORAGE_DIR"] = self._tmpdir.name
        pdf_result = export_document(
            title="Sample", content="PDF content", format="pdf"
        )
        pdf_path = Path(self._tmpdir.name) / pdf_result["file_name"]

        result = load_input(str(pdf_path))
        self.assertEqual(result.source_format, "pdf")
        result.cleanup()

    def test_load_local_docx_file(self) -> None:
        from format_export_mcp.export.service import export_document

        os.environ["FORMAT_EXPORT_STORAGE_DIR"] = self._tmpdir.name
        docx_result = export_document(
            title="Sample", content="DOCX content", format="docx"
        )
        docx_path = Path(self._tmpdir.name) / docx_result["file_name"]

        result = load_input(str(docx_path))
        self.assertEqual(result.source_format, "docx")
        result.cleanup()

    def test_cleanup_temporary_directory(self) -> None:
        source = Path(self._tmpdir.name) / "cleanup.txt"
        source.write_text("cleanup test", encoding="utf-8")

        result = load_input(str(source))
        temp_path = result.local_path

        # 本地文件不应该有临时目录
        self.assertIsNone(result.cleanup_dir)
        result.cleanup()  # 应该安全执行
        self.assertTrue(temp_path.exists())  # 原始文件应该仍然存在


if __name__ == "__main__":
    unittest.main()
