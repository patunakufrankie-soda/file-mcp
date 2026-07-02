from __future__ import annotations

from pathlib import Path
from importlib import import_module
from typing import Callable, Literal, TypedDict

from ..utils.image_sources import load_image_assets
from ..storage.manager import (
    build_file_url,
    build_output_path,
    prune_expired_exports,
    store_export_file,
)


ExportFormat = Literal["pdf", "docx", "xlsx", "csv", "txt", "md", "html"]


class ExportDocumentResult(TypedDict):
    success: bool
    file_name: str
    file_url: str


Generator = Callable[[str, str, Path, list[str]], None]


def _lazy_generator(module_name: str, function_name: str) -> Generator:
    def _generator(
        title: str, content: str, output_path: Path, images: list[str]
    ) -> None:
        module = import_module(
            f"..export.generators.{module_name}", package=__package__
        )
        generator = getattr(module, function_name)
        generator(title, content, output_path, images=images)

    return _generator


def _text_only_generator(generator: Callable[[str, str, Path], None]) -> Generator:
    def _wrapped(
        title: str, content: str, output_path: Path, images: list[str]
    ) -> None:
        if images:
            raise ValueError("Image content only supports pdf or docx")
        generator(title, content, output_path)

    return _wrapped


def _import_text_generator(
    module_name: str, function_name: str
) -> Callable[[str, str, Path], None]:
    def _generator(title: str, content: str, output_path: Path) -> None:
        module = import_module(
            f"..export.generators.{module_name}", package=__package__
        )
        generator = getattr(module, function_name)
        generator(title, content, output_path)

    return _generator


GENERATORS: dict[str, tuple[str, Generator]] = {
    "pdf": ("pdf", _lazy_generator("pdf_generator", "generate_pdf")),
    "docx": ("docx", _lazy_generator("docx_generator", "generate_docx")),
    "xlsx": (
        "xlsx",
        _text_only_generator(_import_text_generator("xlsx_generator", "generate_xlsx")),
    ),
    "csv": (
        "csv",
        _text_only_generator(_import_text_generator("csv_generator", "generate_csv")),
    ),
    "txt": (
        "txt",
        _text_only_generator(_import_text_generator("txt_generator", "generate_txt")),
    ),
    "md": (
        "md",
        _text_only_generator(_import_text_generator("md_generator", "generate_md")),
    ),
    "markdown": (
        "md",
        _text_only_generator(_import_text_generator("md_generator", "generate_md")),
    ),
    "html": (
        "html",
        _text_only_generator(_import_text_generator("html_generator", "generate_html")),
    ),
}


def export_document(
    title: str, content: str, format: str, images: list[str] | None = None
) -> ExportDocumentResult:
    """Export markdown content to various document formats.

    Args:
        title: Document title and filename stem
        content: Markdown content to export
        format: Target format (pdf, docx, xlsx, csv, txt, md, html)
        images: Optional image list for pdf/docx formats

    Returns:
        ExportDocumentResult with success status, filename, and download URL
    """
    normalized_format = (format or "").strip().lower()
    if normalized_format not in GENERATORS:
        supported = ", ".join(["pdf", "docx", "xlsx", "csv", "txt", "md", "html"])
        raise ValueError(
            f"Unsupported format: {format}. Supported formats: {supported}"
        )

    image_list = list(images or [])
    if image_list:
        load_image_assets(image_list)

    prune_expired_exports()
    clean_title = (title or "Export").strip() or "Export"
    extension, generator = GENERATORS[normalized_format]
    output_path = build_output_path(clean_title, extension)
    generator(clean_title, content or "", output_path, image_list)
    stored_path = store_export_file(output_path, output_path.name)

    return {
        "success": True,
        "file_name": stored_path.name,
        "file_url": build_file_url(stored_path.name),
    }
