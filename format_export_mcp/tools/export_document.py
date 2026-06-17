from __future__ import annotations

from pathlib import Path
from importlib import import_module
from typing import Callable, Literal, TypedDict

from .csv_generator import generate_csv
from .html_generator import generate_html
from .md_generator import generate_md
from .storage import build_file_url, build_output_path, prune_expired_exports, store_export_file
from .xlsx_generator import generate_xlsx
from .txt_generator import generate_txt


ExportFormat = Literal["pdf", "docx", "xlsx", "csv", "txt", "md", "html"]


class ExportDocumentResult(TypedDict):
    success: bool
    file_name: str
    file_url: str


def _lazy_generator(module_name: str, function_name: str) -> Callable[[str, str, Path], None]:
    def _generator(title: str, content: str, output_path: Path) -> None:
        module = import_module(f".{module_name}", package=__package__)
        generator = getattr(module, function_name)
        generator(title, content, output_path)

    return _generator


GENERATORS: dict[str, tuple[str, Callable[[str, str, Path], None]]] = {
    "pdf": ("pdf", _lazy_generator("pdf_generator", "generate_pdf")),
    "docx": ("docx", _lazy_generator("docx_generator", "generate_docx")),
    "xlsx": ("xlsx", generate_xlsx),
    "csv": ("csv", generate_csv),
    "txt": ("txt", generate_txt),
    "md": ("md", generate_md),
    "markdown": ("md", generate_md),
    "html": ("html", generate_html),
}


def export_document(title: str, content: str, format: str) -> ExportDocumentResult:
    """Export text content to pdf, docx, txt, md, or html and return a download URL."""
    normalized_format = (format or "").strip().lower()
    if normalized_format not in GENERATORS:
        supported = ", ".join(["pdf", "docx", "xlsx", "csv", "txt", "md", "html"])
        raise ValueError(f"Unsupported format: {format}. Supported formats: {supported}")

    prune_expired_exports()
    clean_title = (title or "Export").strip() or "Export"
    extension, generator = GENERATORS[normalized_format]
    output_path = build_output_path(clean_title, extension)
    generator(clean_title, content or "", output_path)
    stored_path = store_export_file(output_path, output_path.name)

    return {
        "success": True,
        "file_name": stored_path.name,
        "file_url": build_file_url(stored_path.name),
    }
