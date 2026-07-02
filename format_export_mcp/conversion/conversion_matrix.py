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
    "pdf_to_docx": "第一版采用文本提取策略生成可编辑 docx，不保证复杂版式还原",
    "docx_to_pdf": "不使用 LibreOffice，第一版采用提取文本后重新生成 PDF 的方式，不保证原 Word 版式完全一致",
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
