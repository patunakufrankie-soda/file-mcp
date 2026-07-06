from __future__ import annotations

import asyncio
import base64
import json
import os
import threading
import tempfile
import time
import unittest
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from zipfile import is_zipfile

import httpx


PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mP8/5+hHgAHggJ/Pv8U/wAAAABJRU5ErkJggg=="
)
PNG_BYTES = base64.b64decode(PNG_DATA_URL.split(",", 1)[1])


def extract_decoded_pdf_streams(pdf_path: Path) -> list[bytes]:
    data = pdf_path.read_bytes()
    streams: list[bytes] = []
    cursor = 0

    while True:
        start = data.find(b"stream\n", cursor)
        if start == -1:
            break
        end = data.find(b"endstream", start)
        if end == -1:
            break

        raw_stream = data[start + len(b"stream\n") : end].rstrip(b"\r\n")
        try:
            decoded_stream = zlib.decompress(base64.a85decode(raw_stream, adobe=True))
        except Exception:
            try:
                decoded_stream = zlib.decompress(raw_stream)
            except Exception:
                decoded_stream = raw_stream

        streams.append(decoded_stream)
        cursor = end + len(b"\nendstream")

    return streams


def request_asgi(app, method: str, url: str, **kwargs) -> httpx.Response:
    async def _request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, url, **kwargs)

    return asyncio.run(_request())


class FakeHTTPResponse:
    def __init__(self, body: bytes, content_type: str = "image/png") -> None:
        self._body = body
        self.headers = {"Content-Type": content_type}

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class SimpleFileHandler(BaseHTTPRequestHandler):
    directory = "."

    def do_GET(self):
        file_path = Path(self.directory) / self.path.lstrip("/")
        if not file_path.exists():
            self.send_response(404)
            self.end_headers()
            return

        body = file_path.read_bytes()
        self.send_response(200)
        if file_path.suffix == ".txt":
            self.send_header("Content-Type", "text/plain; charset=utf-8")
        elif file_path.suffix == ".md":
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
        elif file_path.suffix == ".pdf":
            self.send_header("Content-Type", "application/pdf")
        elif file_path.suffix == ".docx":
            self.send_header(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class ExportDocumentFormatTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["FORMAT_EXPORT_STORAGE_DIR"] = self._tmpdir.name
        os.environ["FORMAT_EXPORT_PUBLIC_BASE_URL"] = "/downloads"
        self._http_server = None
        self._http_thread = None

    def tearDown(self) -> None:
        if self._http_server is not None:
            self._http_server.shutdown()
            self._http_server.server_close()
        if self._http_thread is not None:
            self._http_thread.join(timeout=2)
        self._tmpdir.cleanup()

    def _start_file_server(self, directory: Path) -> str:
        handler = type(
            "TempFileHandler", (SimpleFileHandler,), {"directory": str(directory)}
        )
        self._http_server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._http_thread = threading.Thread(
            target=self._http_server.serve_forever, daemon=True
        )
        self._http_thread.start()
        server_address = self._http_server.server_address
        host = server_address[0]
        port = server_address[1]
        return f"http://{host}:{port}"

    def _create_sample_pdf(self, title: str, content: str) -> Path:
        from format_export_mcp.export.service import export_document

        result = export_document(title=title, content=content, format="pdf")
        return Path(self._tmpdir.name) / result["file_name"]

    def _create_sample_docx(self, title: str, content: str) -> Path:
        from format_export_mcp.export.service import export_document

        result = export_document(title=title, content=content, format="docx")
        return Path(self._tmpdir.name) / result["file_name"]

    def test_exports_doc_xlsx_xls_and_csv(self) -> None:
        from format_export_mcp.export.service import export_document

        cases = [
            (
                "xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".xlsx",
            ),
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
            self.assertTrue(
                file_path.exists(), msg=f"expected exported file for {format_name}"
            )

            if format_name == "xlsx":
                self.assertTrue(is_zipfile(file_path))
            elif format_name == "csv":
                self.assertTrue(
                    file_path.read_text(encoding="utf-8-sig").startswith("标题,内容")
                )

    def test_tabular_exports_preserve_quoted_commas(self) -> None:
        from format_export_mcp.export.service import export_document

        content = '标题,内容\nA,"b,c"'

        csv_result = export_document(title="表格", content=content, format="csv")
        csv_path = Path(self._tmpdir.name) / csv_result["file_name"]
        self.assertEqual(
            csv_path.read_text(encoding="utf-8-sig"), '标题,内容\nA,"b,c"\n'
        )

        xlsx_result = export_document(title="表格", content=content, format="xlsx")
        xlsx_path = Path(self._tmpdir.name) / xlsx_result["file_name"]
        with ZipFile(xlsx_path) as archive:
            sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn('r="A2"', sheet_xml)
        self.assertIn('r="B2"', sheet_xml)
        self.assertNotIn('r="C2"', sheet_xml)
        self.assertIn("b,c", sheet_xml)

    def test_exports_images_only_to_pdf_and_docx(self) -> None:
        from format_export_mcp.export.service import export_document

        pdf_result = export_document(
            title="图片PDF", content="", format="pdf", images=[PNG_DATA_URL]
        )
        pdf_path = Path(self._tmpdir.name) / pdf_result["file_name"]
        self.assertTrue(pdf_path.exists())
        self.assertIn(b"/Image", pdf_path.read_bytes())

        docx_result = export_document(
            title="图片DOCX", content="", format="docx", images=[PNG_DATA_URL]
        )
        docx_path = Path(self._tmpdir.name) / docx_result["file_name"]
        self.assertTrue(docx_path.exists())
        with ZipFile(docx_path) as archive:
            media_names = [
                name for name in archive.namelist() if name.startswith("word/media/")
            ]
        self.assertEqual(len(media_names), 1)

    def test_remote_image_urls_can_be_embedded_into_pdf(self) -> None:
        from format_export_mcp.export.service import export_document

        remote_url = "https://kb.example.com/api/file/abc123"

        def fake_urlopen(request, timeout=None):
            self.assertEqual(request.full_url, remote_url)
            self.assertIsNotNone(timeout)
            return FakeHTTPResponse(PNG_BYTES)

        with patch(
            "format_export_mcp.utils.image_sources.urlopen", side_effect=fake_urlopen
        ):
            result = export_document(
                title="远程图片PDF", content="", format="pdf", images=[remote_url]
            )

        pdf_path = Path(self._tmpdir.name) / result["file_name"]
        self.assertTrue(pdf_path.exists())
        self.assertIn(b"/Image", pdf_path.read_bytes())

    def test_relative_api_image_urls_can_be_embedded_into_docx(self) -> None:
        from format_export_mcp.export.service import export_document

        content = "导出前文字\n\n![知识库图片](/api/image/abc123)\n\n导出后文字"
        seen_urls: list[str] = []

        def fake_urlopen(request, timeout=None):
            seen_urls.append(request.full_url)
            self.assertIsNotNone(timeout)
            return FakeHTTPResponse(PNG_BYTES)

        with patch.dict(
            os.environ,
            {"FORMAT_EXPORT_IMAGE_SOURCE_BASE_URL": "https://kb.example.com"},
        ):
            with patch(
                "format_export_mcp.utils.image_sources.urlopen",
                side_effect=fake_urlopen,
            ):
                result = export_document(
                    title="远程图片DOCX", content=content, format="docx"
                )

        docx_path = Path(self._tmpdir.name) / result["file_name"]
        self.assertTrue(docx_path.exists())
        self.assertEqual(seen_urls, ["https://kb.example.com/api/image/abc123"])
        with ZipFile(docx_path) as archive:
            media_names = [
                name for name in archive.namelist() if name.startswith("word/media/")
            ]
        self.assertEqual(len(media_names), 1)

    def test_markdown_is_rendered_in_docx_exports(self) -> None:
        from format_export_mcp.export.service import export_document

        markdown = "# Flow Title\n\n- FFmpeg\n- Pandas\n\n```bash\nffmpeg -i input.avi output.mp4\n```"
        result = export_document(title="Markdown DOCX", content=markdown, format="docx")
        docx_path = Path(self._tmpdir.name) / result["file_name"]

        with ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")

        self.assertIn('w:pStyle w:val="Heading1"', document_xml)
        self.assertIn("Flow Title", document_xml)
        self.assertNotIn("# Flow Title", document_xml)
        self.assertIn("FFmpeg", document_xml)
        self.assertNotIn("- FFmpeg", document_xml)
        self.assertIn("ffmpeg -i input.avi output.mp4", document_xml)

    def test_markdown_parser_identifies_headings_lists_and_code_blocks(self) -> None:
        from format_export_mcp.utils.markdown_blocks import parse_markdown_blocks

        blocks = parse_markdown_blocks(
            "# Flow Title\n\n1. Identify Formats\n2. Select Conversion Method\n\n```bash\nffmpeg -i input.avi output.mp4\n```"
        )

        self.assertEqual(
            [(block.kind, block.text, block.level) for block in blocks],
            [
                ("heading", "Flow Title", 1),
                ("ordered_item", "Identify Formats", 1),
                ("ordered_item", "Select Conversion Method", 2),
                ("code", "ffmpeg -i input.avi output.mp4", 0),
            ],
        )

    def test_markdown_parser_accepts_ordered_items_without_space_after_number(
        self,
    ) -> None:
        from format_export_mcp.utils.markdown_blocks import parse_markdown_blocks

        blocks = parse_markdown_blocks(
            "1.**数字化转型加速**：越来越多的企业投入到数字化转型中，以提高效率和市场竞争力。\n"
            "2.**绿色能源发展**：在全球对可持续发展的重视下，绿色能源行业取得了显著进展。\n"
            "3.**消费升级**：消费者的购买行为逐渐向高品质和个性化产品转移。"
        )

        self.assertEqual(
            [(block.kind, block.level, block.text) for block in blocks],
            [
                (
                    "ordered_item",
                    1,
                    "**数字化转型加速**：越来越多的企业投入到数字化转型中，以提高效率和市场竞争力。",
                ),
                (
                    "ordered_item",
                    2,
                    "**绿色能源发展**：在全球对可持续发展的重视下，绿色能源行业取得了显著进展。",
                ),
                (
                    "ordered_item",
                    3,
                    "**消费升级**：消费者的购买行为逐渐向高品质和个性化产品转移。",
                ),
            ],
        )

    def test_markdown_parser_preserves_common_business_document_structure(
        self,
    ) -> None:
        from format_export_mcp.utils.markdown_blocks import (
            parse_markdown_blocks,
            parse_markdown_inlines,
        )

        blocks = parse_markdown_blocks(
            "## 小节\n\n"
            "- 父项\n"
            "  - 子项\n"
            "1. 第一项\n"
            "  2. 第二层\n\n"
            "> 引用 **内容**\n"
            "> 第二行\n\n"
            "[项目地址](https://example.com)  \n"
            "下一行\n\n"
            "---\n\n"
            "```python\nprint('ok')\n```"
        )

        self.assertEqual(
            [block.kind for block in blocks],
            [
                "heading",
                "bullet_item",
                "bullet_item",
                "ordered_item",
                "ordered_item",
                "blockquote",
                "paragraph",
                "horizontal_rule",
                "code",
            ],
        )
        self.assertEqual(blocks[2].depth, 1)
        self.assertEqual(blocks[4].depth, 1)
        self.assertEqual(blocks[5].text, "引用 **内容**\n第二行")
        self.assertEqual(blocks[6].text, "[项目地址](https://example.com)  \n下一行")
        self.assertEqual(blocks[8].info, "python")

        spans = parse_markdown_inlines("[项目地址](https://example.com)")
        self.assertEqual(spans[0].text, "项目地址")
        self.assertEqual(spans[0].href, "https://example.com")

        strike_spans = parse_markdown_inlines("~~删除内容~~")
        self.assertEqual(strike_spans[0].text, "删除内容")
        self.assertIn("strike", strike_spans[0].styles)

    def test_markdown_plain_text_renderer_keeps_semantics_without_markup(
        self,
    ) -> None:
        from format_export_mcp.utils.markdown_blocks import render_markdown_as_text

        output = render_markdown_as_text(
            "## 小节\n\n"
            "- 父项\n"
            "  - **子项**\n\n"
            "> 引用 [地址](https://example.com)\n\n"
            "![架构图](https://example.com/architecture.png)\n\n"
            "---"
        )

        self.assertIn("小节", output)
        self.assertIn("• 父项", output)
        self.assertIn("  • 子项", output)
        self.assertIn("  引用 地址 (https://example.com)", output)
        self.assertIn(
            "架构图 (https://example.com/architecture.png)",
            output,
        )
        self.assertIn("----------------------------------------", output)
        self.assertNotIn("**", output)
        self.assertNotIn("> ", output)

    def test_markdown_parser_identifies_standalone_images(self) -> None:
        from format_export_mcp.utils.markdown_blocks import parse_markdown_blocks

        blocks = parse_markdown_blocks(
            f"导出前文字\n\n![示意图]({PNG_DATA_URL})\n\n导出后文字"
        )

        self.assertEqual(
            [block.kind for block in blocks], ["paragraph", "image", "paragraph"]
        )
        self.assertEqual(blocks[1].text, "示意图")
        self.assertEqual(blocks[1].image_src, PNG_DATA_URL)

    def test_markdown_images_render_in_docx_at_original_position(self) -> None:
        from format_export_mcp.export.service import export_document

        content = f"导出前文字\n\n![示意图]({PNG_DATA_URL})\n\n导出后文字"
        result = export_document(title="图片位置", content=content, format="docx")
        docx_path = Path(self._tmpdir.name) / result["file_name"]

        with ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
            media_names = [
                name for name in archive.namelist() if name.startswith("word/media/")
            ]

        self.assertEqual(len(media_names), 1)
        self.assertIn("导出前文字", document_xml)
        self.assertIn("导出后文字", document_xml)
        self.assertIn("w:drawing", document_xml)
        self.assertLess(
            document_xml.index("导出前文字"), document_xml.index("w:drawing")
        )
        self.assertLess(
            document_xml.index("w:drawing"), document_xml.index("导出后文字")
        )

    def test_markdown_images_render_in_pdf(self) -> None:
        from format_export_mcp.export.service import export_document

        content = f"导出前文字\n\n![示意图]({PNG_DATA_URL})\n\n导出后文字"
        result = export_document(title="图片位置", content=content, format="pdf")
        pdf_path = Path(self._tmpdir.name) / result["file_name"]

        self.assertTrue(pdf_path.exists())
        self.assertIn(b"/Image", pdf_path.read_bytes())

    def test_inline_markdown_is_rendered_cleanly_in_pdf_docx_and_html_exports(
        self,
    ) -> None:
        from format_export_mcp.export.service import export_document

        content = (
            "1.**数字化转型加速**：越来越多的企业投入到数字化转型中，以提高效率和市场竞争力。\n"
            "2.**绿色能源发展**：在全球对可持续发展的重视下，绿色能源行业取得了显著进展。\n"
            "3.**消费升级**：消费者的购买行为逐渐向高品质和个性化产品转移。"
        )

        pdf_result = export_document(title="格式测试", content=content, format="pdf")
        pdf_path = Path(self._tmpdir.name) / pdf_result["file_name"]
        pdf_streams = extract_decoded_pdf_streams(pdf_path)
        self.assertTrue(pdf_streams)
        self.assertFalse(any(b"\x00*\x00*" in stream for stream in pdf_streams))

        docx_result = export_document(title="格式测试", content=content, format="docx")
        docx_path = Path(self._tmpdir.name) / docx_result["file_name"]
        with ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertNotIn("**", document_xml)
        self.assertIn("数字化转型加速", document_xml)
        self.assertIn("w:b", document_xml)

        html_result = export_document(title="格式测试", content=content, format="html")
        html_path = Path(self._tmpdir.name) / html_result["file_name"]
        html_text = html_path.read_text(encoding="utf-8")
        self.assertNotIn("**", html_text)
        self.assertIn("<strong>数字化转型加速</strong>", html_text)
        self.assertIn("<ol>", html_text)

    def test_plain_txt_is_not_interpreted_as_markdown_in_pdf_or_docx(
        self,
    ) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = Path(self._tmpdir.name) / "literal.txt"
        source.write_text("# Literal Heading\n- Literal Item", encoding="utf-8")

        docx_result = convert_file_document(str(source), "docx")
        self.assertTrue(docx_result.get("success"))
        with ZipFile(str(docx_result.get("output_path"))) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("# Literal Heading", document_xml)
        self.assertIn("- Literal Item", document_xml)
        self.assertEqual(document_xml.count('w:pStyle w:val="Heading1"'), 1)

        pdf_result = convert_file_document(str(source), "pdf")
        self.assertTrue(pdf_result.get("success"))
        import fitz

        with fitz.open(str(pdf_result.get("output_path"))) as pdf:
            pdf_text = "\n".join(page.get_text() for page in pdf)
        self.assertIn("# Literal Heading", pdf_text)
        self.assertIn("- Literal Item", pdf_text)

    def test_enhanced_markdown_structure_renders_in_docx(self) -> None:
        from format_export_mcp.export.service import export_document

        content = (
            "# Business Report\n\n"
            "##### Heading Five\n\n"
            "- Parent\n"
            "  - Child\n\n"
            "> Quoted [reference](https://example.com)\n\n"
            "```python\nprint('ok')\n```\n\n"
            "| Name | State |\n| --- | --- |\n| Alice | Ready |\n\n"
            "---"
        )
        result = export_document(
            title="Business Report",
            content=content,
            format="docx",
        )
        docx_path = Path(self._tmpdir.name) / result["file_name"]

        with ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
            relationships_xml = archive.read(
                "word/_rels/document.xml.rels"
            ).decode("utf-8")

        self.assertEqual(document_xml.count("Business Report"), 1)
        self.assertIn('w:pStyle w:val="Heading5"', document_xml)
        self.assertIn("w:ind", document_xml)
        self.assertIn('w:pStyle w:val="IntenseQuote"', document_xml)
        self.assertIn("w:hyperlink", document_xml)
        self.assertIn("https://example.com", relationships_xml)
        self.assertIn("w:pBdr", document_xml)
        self.assertIn("w:tblHeader", document_xml)

    def test_enhanced_markdown_structure_renders_in_pdf(self) -> None:
        import fitz

        from format_export_mcp.export.service import export_document

        content = (
            "# Business Report\n\n"
            "##### Heading Five\n\n"
            "- Parent\n"
            "  - Child\n\n"
            "> Quoted [reference](https://example.com)\n\n"
            "---"
        )
        result = export_document(
            title="Business Report",
            content=content,
            format="pdf",
        )
        pdf_path = Path(self._tmpdir.name) / result["file_name"]

        with fitz.open(pdf_path) as pdf:
            pdf_text = "\n".join(page.get_text() for page in pdf)
            links = [link for page in pdf for link in page.get_links()]

        self.assertEqual(pdf_text.count("Business Report"), 1)
        self.assertIn("Heading Five", pdf_text)
        self.assertIn("Parent", pdf_text)
        self.assertIn("Child", pdf_text)
        self.assertIn("Quoted reference", pdf_text)
        self.assertTrue(
            any(link.get("uri") == "https://example.com" for link in links)
        )

    def test_inline_html_styles_and_markdown_tables_survive_common_exports(
        self,
    ) -> None:
        from format_export_mcp.export.service import export_document

        content = (
            "答：安全是指没有受到<u>威胁</u>、没有<del>危险</del>、<strong>损失</strong>。\n\n"
            "| 姓名 | 工号 | 年龄 |\n"
            "| --- | --- | --- |\n"
            "| 张三 | 001 | 18 |\n"
            "| 李四 | 002 | 19 |"
        )

        pdf_result = export_document(title="样式测试", content=content, format="pdf")
        pdf_path = Path(self._tmpdir.name) / pdf_result["file_name"]
        pdf_streams = extract_decoded_pdf_streams(pdf_path)
        self.assertTrue(pdf_streams)
        self.assertFalse(
            any(
                b"<u>" in stream or b"<del>" in stream or b"<strong>" in stream
                for stream in pdf_streams
            )
        )

        docx_result = export_document(title="样式测试", content=content, format="docx")
        docx_path = Path(self._tmpdir.name) / docx_result["file_name"]
        with ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("w:u", document_xml)
        self.assertIn("w:strike", document_xml)
        self.assertIn("w:b", document_xml)
        self.assertIn("w:tbl", document_xml)
        self.assertIn("张三", document_xml)
        self.assertNotIn("| 姓名 |", document_xml)

        html_result = export_document(title="样式测试", content=content, format="html")
        html_path = Path(self._tmpdir.name) / html_result["file_name"]
        html_text = html_path.read_text(encoding="utf-8")
        self.assertIn("<u>威胁</u>", html_text)
        self.assertIn("<del>危险</del>", html_text)
        self.assertIn("<strong>损失</strong>", html_text)
        self.assertIn("<table>", html_text)
        self.assertIn("<td>张三</td>", html_text)
        self.assertNotIn("| 姓名 |", html_text)

        xlsx_result = export_document(title="样式测试", content=content, format="xlsx")
        xlsx_path = Path(self._tmpdir.name) / xlsx_result["file_name"]
        with ZipFile(xlsx_path) as archive:
            sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn('r="A1"', sheet_xml)
        self.assertIn('r="B2"', sheet_xml)
        self.assertIn("张三", sheet_xml)
        self.assertIn("李四", sheet_xml)
        self.assertNotIn("| 姓名 |", sheet_xml)

    def test_convert_file_document_local_txt_to_md(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = Path(self._tmpdir.name) / "sample.txt"
        source.write_text("# 普通文本标题\n- 普通文本条目", encoding="utf-8")

        result = convert_file_document(str(source), "md")
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("source_format"), "txt")
        self.assertEqual(result.get("target_format"), "md")
        output_path = str(result.get("output_path"))
        self.assertTrue(output_path.endswith(".md"))
        self.assertEqual(
            Path(output_path).read_text(encoding="utf-8"),
            "# 普通文本标题\n- 普通文本条目",
        )

    def test_convert_file_document_local_txt_to_docx(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = Path(self._tmpdir.name) / "sample.txt"
        source.write_text("Alpha\nBeta", encoding="utf-8")

        result = convert_file_document(str(source), "docx")
        self.assertTrue(result.get("success"))
        output_path = str(result.get("output_path"))
        self.assertTrue(Path(output_path).exists())
        with ZipFile(output_path) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("Alpha", document_xml)

    def test_convert_file_document_local_md_to_txt(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = Path(self._tmpdir.name) / "sample.md"
        source.write_text(
            "# 标题\n\n- **条目**\n\n"
            "| 姓名 | 状态 |\n| --- | --- |\n| 张三 | 正常 |",
            encoding="utf-8",
        )

        result = convert_file_document(str(source), "txt")
        self.assertTrue(result.get("success"))
        output_text = Path(str(result.get("output_path"))).read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("标题", output_text)
        self.assertIn("条目", output_text)
        self.assertNotIn("# ", output_text)
        self.assertNotIn("**", output_text)
        self.assertNotIn("| ---", output_text)
        self.assertIn("姓名\t状态", output_text)
        self.assertIn("张三\t正常", output_text)

    def test_convert_file_document_local_pdf_to_txt(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = self._create_sample_pdf("PDF样例", "第一页内容")
        result = convert_file_document(str(source), "txt")
        self.assertTrue(result.get("success"))
        output_text = Path(str(result.get("output_path"))).read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("PDF样例", output_text)
        self.assertIn("第一页内容", output_text)

    def test_convert_file_document_local_pdf_to_md(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = self._create_sample_pdf("PDF样例", "第一页内容")
        result = convert_file_document(str(source), "md")
        self.assertTrue(result.get("success"))
        output_text = Path(str(result.get("output_path"))).read_text(encoding="utf-8")
        self.assertIn("PDF样例", output_text)
        self.assertIn("第一页内容", output_text)

    def test_convert_file_document_local_pdf_to_docx(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = self._create_sample_pdf("PDF样例", "第一页内容")
        result = convert_file_document(str(source), "docx")
        self.assertTrue(result.get("success"))
        with ZipFile(str(result.get("output_path"))) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("PDF样例", document_xml)
        self.assertIn("第一页内容", document_xml)

    def test_convert_file_document_local_docx_to_txt(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = self._create_sample_docx(
            "DOCX样例",
            "表格前\n\n| 列1 | 列2 |\n| --- | --- |\n| 表格A | 表格B |\n\n表格后",
        )
        result = convert_file_document(str(source), "txt")
        self.assertTrue(result.get("success"))
        output_text = Path(str(result.get("output_path"))).read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("表格A\t表格B", output_text)
        self.assertLess(output_text.index("表格前"), output_text.index("表格A"))
        self.assertLess(output_text.index("表格A"), output_text.index("表格后"))

    def test_convert_file_document_local_docx_to_md(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = self._create_sample_docx(
            "真实文档标题",
            "| 列1 | 列2 |\n| --- | --- |\n| 表格A | 表格B |\n\n正文",
        )
        result = convert_file_document(str(source), "md")
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("message"), "转换成功")
        output_text = Path(str(result.get("output_path"))).read_text(encoding="utf-8")
        self.assertEqual(output_text.count("# 真实文档标题"), 1)
        self.assertNotIn(f"# {source.stem}", output_text)
        self.assertIn("| 表格A | 表格B |", output_text)
        self.assertIn("正文", output_text)

    def test_convert_file_document_local_txt_to_pdf(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = Path(self._tmpdir.name) / "sample.txt"
        source.write_text("中文 PDF 内容", encoding="utf-8")

        result = convert_file_document(str(source), "pdf")
        self.assertTrue(result.get("success"))
        self.assertTrue(Path(str(result.get("output_path"))).exists())

    def test_convert_file_document_local_docx_to_pdf(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = self._create_sample_docx("DOCX样例", "第一段\n\n第二段")
        result = convert_file_document(str(source), "pdf")
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("message"), "转换成功")

    def test_convert_file_document_downloads_url_input_before_converting(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source_dir = Path(self._tmpdir.name) / "remote"
        source_dir.mkdir()
        remote_file = source_dir / "remote.txt"
        remote_file.write_text("来自 URL 的内容", encoding="utf-8")
        base_url = self._start_file_server(source_dir)

        result = convert_file_document(f"{base_url}/remote.txt", "md")
        self.assertTrue(result.get("success"))
        self.assertIn("/downloads/", str(result.get("output_url")))
        self.assertIn(
            "来自 URL 的内容",
            Path(str(result.get("output_path"))).read_text(encoding="utf-8"),
        )

    def test_convert_file_document_rejects_unsupported_source_format(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = Path(self._tmpdir.name) / "sample.rtf"
        source.write_text("rtf", encoding="utf-8")

        result = convert_file_document(str(source), "pdf")
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error_type"), "unsupported_format")

    def test_convert_file_document_rejects_unsupported_target_format(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = Path(self._tmpdir.name) / "sample.txt"
        source.write_text("hello", encoding="utf-8")

        result = convert_file_document(str(source), "xlsx")
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error_type"), "validation_error")

    def test_md_to_docx_falls_back_cleanly_without_pandoc(self) -> None:
        from format_export_mcp.conversion.file_document_convert import (
            convert_file_document,
        )

        source = Path(self._tmpdir.name) / "sample.md"
        source.write_text("# 标题\n\n正文", encoding="utf-8")

        result = convert_file_document(str(source), "docx")

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("message"), "转换成功")

    def test_get_supported_conversions_returns_expected_shape(self) -> None:
        from format_export_mcp.conversion.conversion_matrix import (
            get_supported_conversions,
        )

        result = get_supported_conversions()
        self.assertTrue(result["success"])
        self.assertEqual(result["formats"], ["txt", "md", "pdf", "docx"])
        self.assertIn("pdf_to_docx", result["notes"])

    def test_supported_conversions_have_real_routes(self) -> None:
        from format_export_mcp.conversion.conversion_matrix import (
            SUPPORTED_CONVERSIONS,
        )
        from format_export_mcp.conversion.router import ConversionRouter
        from format_export_mcp.conversion.services.format_detector import (
            DocumentFeatures,
        )

        router = ConversionRouter()
        for source_format, target_formats in SUPPORTED_CONVERSIONS.items():
            for target_format in target_formats:
                self.assertNotEqual(source_format, target_format)
                route = router.get_route(
                    source_format,
                    target_format,
                    DocumentFeatures(recommended_strategy="text_pdf"),
                )
                self.assertIsNotNone(
                    route,
                    msg=f"missing route for {source_format} -> {target_format}",
                )

    def test_convert_file_document_api_accepts_txt_to_md(self) -> None:
        from format_export_mcp.server_common import create_http_middleware, create_mcp

        source = Path(self._tmpdir.name) / "sample.txt"
        source.write_text("api content", encoding="utf-8")
        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/", middleware=create_http_middleware())

        response = request_asgi(
            app,
            "POST",
            "/api/convert_file_document",
            json={"input_uri": str(source), "target_format": "md", "mode": "normal"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["target_format"], "md")

    def test_supported_conversions_api_returns_matrix(self) -> None:
        from format_export_mcp.server_common import create_http_middleware, create_mcp

        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/", middleware=create_http_middleware())

        response = request_asgi(app, "GET", "/api/supported_conversions")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIn("docx", response.json()["formats"])

    def test_removed_convert_document_api_returns_404(self) -> None:
        from format_export_mcp.server_common import create_http_middleware, create_mcp

        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/", middleware=create_http_middleware())

        response = request_asgi(
            app,
            "POST",
            "/api/convert_document",
            json={
                "title": "市场分析",
                "source_format": "markdown",
                "target_format": "pdf",
                "content": "# 标题",
            },
        )

        self.assertEqual(response.status_code, 404)

    def test_removed_extract_text_api_returns_404(self) -> None:
        from format_export_mcp.server_common import create_http_middleware, create_mcp

        source = Path(self._tmpdir.name) / "sample.txt"
        source.write_text("extract me", encoding="utf-8")
        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/", middleware=create_http_middleware())

        response = request_asgi(
            app,
            "POST",
            "/api/extract_text",
            json={"input_uri": str(source)},
        )

        self.assertEqual(response.status_code, 404)

    def test_rejects_non_document_formats_when_images_are_present(self) -> None:
        from format_export_mcp.export.service import export_document

        with self.assertRaisesRegex(
            ValueError, "Image content only supports pdf or docx"
        ):
            export_document(
                title="图片", content="", format="txt", images=[PNG_DATA_URL]
            )

    def test_exports_local_image_paths(self) -> None:
        from format_export_mcp.export.service import export_document

        image_path = Path(self._tmpdir.name) / "sample.png"
        image_path.write_bytes(base64.b64decode(PNG_DATA_URL.split(",", 1)[1]))

        result = export_document(
            title="本地图片", content="", format="docx", images=[str(image_path)]
        )
        docx_path = Path(self._tmpdir.name) / result["file_name"]
        with ZipFile(docx_path) as archive:
            media_names = [
                name for name in archive.namelist() if name.startswith("word/media/")
            ]
        self.assertEqual(len(media_names), 1)

    def test_http_payload_validation_rejects_none_and_non_string_values(self) -> None:
        from format_export_mcp.server_common import _parse_export_payload

        self.assertEqual(
            _parse_export_payload(
                {"title": "标题", "content": "内容", "format": "pdf"}
            ),
            ("标题", "内容", "pdf", []),
        )

        self.assertEqual(
            _parse_export_payload(
                {
                    "title": "标题",
                    "content": "内容",
                    "format": "pdf",
                    "images": [PNG_DATA_URL],
                }
            ),
            ("标题", "内容", "pdf", [PNG_DATA_URL]),
        )

        with self.assertRaisesRegex(ValueError, "title must be a string"):
            _parse_export_payload({"title": None, "content": "内容", "format": "pdf"})

        with self.assertRaisesRegex(ValueError, "content must be a string"):
            _parse_export_payload({"title": "标题", "content": 123, "format": "pdf"})

        with self.assertRaisesRegex(ValueError, "images must be a list of strings"):
            _parse_export_payload(
                {"title": "标题", "content": "内容", "format": "pdf", "images": [123]}
            )

        with self.assertRaisesRegex(ValueError, "JSON object"):
            _parse_export_payload(["not", "an", "object"])

    def test_legacy_doc_and_xls_formats_are_rejected(self) -> None:
        from format_export_mcp.export.service import export_document

        with self.assertRaisesRegex(ValueError, "Unsupported format: doc"):
            export_document(title="标题", content="内容", format="doc")

        with self.assertRaisesRegex(ValueError, "Unsupported format: xls"):
            export_document(title="标题", content="内容", format="xls")

    def test_export_prunes_expired_files_before_writing_new_one(self) -> None:
        from format_export_mcp.export.service import export_document

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

        run.assert_called_once()
        _, kwargs = run.call_args
        self.assertEqual(kwargs["transport"], "sse")
        self.assertEqual(kwargs["host"], "0.0.0.0")
        self.assertEqual(kwargs["port"], 8000)
        self.assertEqual(len(kwargs["middleware"]), 1)
        self.assertEqual(kwargs["middleware"][0].cls.__name__, "CORSMiddleware")

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

    def test_export_document_api_returns_structured_error_for_runtime_failures(
        self,
    ) -> None:
        from format_export_mcp.server_common import create_http_middleware, create_mcp

        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/", middleware=create_http_middleware())

        with patch(
            "format_export_mcp.server_common.export_document",
            side_effect=PermissionError("no write"),
        ):
            with self.assertLogs("format_export_mcp.server_common", level="ERROR"):
                response = request_asgi(
                    app,
                    "POST",
                    "/api/export_document",
                    json={
                        "title": "标题",
                        "content": "内容",
                        "format": "txt",
                        "images": [],
                    },
                    headers={"X-Request-ID": "req-storage-failure"},
                )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["x-request-id"], "req-storage-failure")
        self.assertEqual(
            response.json(),
            {
                "success": False,
                "request_id": "req-storage-failure",
                "error": {
                    "code": "storage_error",
                    "message": "Failed to store exported file",
                },
            },
        )

    def test_export_document_api_returns_request_id_and_structured_success_log(
        self,
    ) -> None:
        from format_export_mcp.server_common import create_http_middleware, create_mcp

        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/", middleware=create_http_middleware())

        with self.assertLogs("format_export_mcp.server_common", level="INFO") as logs:
            response = request_asgi(
                app,
                "POST",
                "/api/export_document",
                json={
                    "title": "标题",
                    "content": "内容",
                    "format": "txt",
                    "images": [],
                },
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

    def test_export_document_api_handles_cors_preflight_requests(self) -> None:
        from format_export_mcp.server_common import create_http_middleware, create_mcp

        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/", middleware=create_http_middleware())

        response = request_asgi(
            app,
            "OPTIONS",
            "/api/export_document",
            headers={
                "Origin": "http://10.89.6.208:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-request-id",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"], "http://10.89.6.208:3000"
        )
        self.assertIn("POST", response.headers["access-control-allow-methods"])
        self.assertIn(
            "content-type", response.headers["access-control-allow-headers"].lower()
        )
        self.assertIn(
            "x-request-id", response.headers["access-control-allow-headers"].lower()
        )

    def test_export_document_api_includes_cors_headers_on_post(self) -> None:
        from format_export_mcp.server_common import create_http_middleware, create_mcp

        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/", middleware=create_http_middleware())

        response = request_asgi(
            app,
            "POST",
            "/api/export_document",
            json={"title": "标题", "content": "内容", "format": "txt", "images": []},
            headers={"Origin": "http://10.89.6.208:3000"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"], "http://10.89.6.208:3000"
        )

    def test_export_document_api_rejects_images_for_txt(self) -> None:
        from format_export_mcp.server_common import create_http_middleware, create_mcp

        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/", middleware=create_http_middleware())

        response = request_asgi(
            app,
            "POST",
            "/api/export_document",
            json={
                "title": "标题",
                "content": "",
                "format": "txt",
                "images": [PNG_DATA_URL],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            {
                "code": "invalid_request",
                "message": "Image content only supports pdf or docx",
            },
        )

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
        from format_export_mcp.server_common import create_http_middleware, create_mcp

        mcp = create_mcp()
        app = mcp.http_app(path="/mcp/", middleware=create_http_middleware())

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
