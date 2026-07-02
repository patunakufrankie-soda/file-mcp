from __future__ import annotations

from typing import TypedDict

from ..export.service import (
    ExportDocumentResult,
    export_document as export_document_impl,
)
from ..conversion.file_document_convert import (
    FileConvertResult,
    convert_file_document as convert_file_impl,
)
from ..conversion.conversion_matrix import (
    SupportedConversionsResult,
    get_supported_conversions as get_conversions_impl,
)


def export_document(
    title: str, content: str, format: str, images: list[str] | None = None
) -> ExportDocumentResult:
    """Export markdown content to various document formats.

    MCP Tool: Converts markdown text (e.g., AI-generated content) into formatted documents.

    Args:
        title: Document title and filename stem
        content: Markdown content to export
        format: Target format: pdf, docx, xlsx, csv, txt, md, markdown, html
        images: Optional image URLs/paths (only for pdf/docx)

    Returns:
        ExportDocumentResult with success, file_name, and file_url
    """
    return export_document_impl(
        title=title, content=content, format=format, images=images
    )


def convert_file_document(input_uri: str, target_format: str) -> FileConvertResult:
    """Convert a document file from one format to another.

    MCP Tool: Converts between document formats (DOCX, PDF, MD, TXT, etc.).

    Args:
        input_uri: Local file path or HTTP/HTTPS URL to source document
        target_format: Target format: txt, md, pdf, docx, etc.

    Returns:
        FileConvertResult with success, source_format, target_format, output_path
    """
    return convert_file_impl(input_uri=input_uri, target_format=target_format)


def get_supported_conversions() -> SupportedConversionsResult:
    """Get the supported file format conversion matrix.

    MCP Tool: Returns all supported source → target format conversions.

    Returns:
        SupportedConversionsResult with format conversion matrix
    """
    return get_conversions_impl()
