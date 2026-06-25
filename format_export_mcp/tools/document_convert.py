from __future__ import annotations

from typing import Literal, TypedDict

from .export_document import export_document


SourceFormat = Literal["markdown", "md", "text", "txt", "csv"]
TargetFormat = Literal["pdf", "docx", "xlsx"]


class ConvertDocumentResult(TypedDict):
    success: bool
    file_name: str
    file_url: str


def convert_document(
    title: str,
    source_format: str,
    target_format: str,
    content: str,
) -> ConvertDocumentResult:
    normalized_source = (source_format or "").strip().lower()
    normalized_target = (target_format or "").strip().lower()

    if normalized_source in {"markdown", "md", "text", "txt"} and normalized_target in {"pdf", "docx"}:
        return export_document(title=title, content=content, format=normalized_target)

    if normalized_source == "csv" and normalized_target == "xlsx":
        return export_document(title=title, content=content, format="xlsx")

    raise ValueError(
        f"Unsupported conversion: {source_format} -> {target_format}. "
        "Supported conversions: markdown/text -> pdf/docx, csv -> xlsx"
    )
