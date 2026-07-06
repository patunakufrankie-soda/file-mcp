from __future__ import annotations

from typing import TypedDict


SUPPORTED_FORMATS = ["txt", "md", "pdf", "docx"]
SUPPORTED_CONVERSIONS = {
    "txt": ["md", "pdf", "docx"],
    "md": ["txt", "pdf", "docx"],
    "pdf": ["txt", "md", "docx"],
    "docx": ["txt", "md", "pdf"],
}
NOTES = {
    "pdf_to_docx": (
        "采用可编辑内容重建；复杂版式可选用 pdf2docx，"
        "未安装时回退到 PyMuPDF + python-docx"
    ),
    "docx_to_pdf": "依赖 LibreOffice headless 转换并尽量保留原始版式",
    "scanned_pdf": "扫描型 PDF 尚未实现 OCR，转换时返回 OCR_REQUIRED",
}


class SupportedConversionsResult(TypedDict):
    success: bool
    formats: list[str]
    conversions: dict[str, list[str]]
    notes: dict[str, str]


def get_supported_conversions() -> SupportedConversionsResult:
    return {
        "success": True,
        "formats": list(SUPPORTED_FORMATS),
        "conversions": {
            key: list(value) for key, value in SUPPORTED_CONVERSIONS.items()
        },
        "notes": dict(NOTES),
    }
