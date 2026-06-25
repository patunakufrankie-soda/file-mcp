from __future__ import annotations

from pathlib import Path
from importlib import import_module
from typing import Callable, Literal, TypedDict

from .csv_generator import generate_csv
from .html_generator import generate_html
from .image_sources import load_image_assets
from .md_generator import generate_md
from .storage import build_file_url, build_output_path, prune_expired_exports, store_export_file
from .xlsx_generator import generate_xlsx
from .txt_generator import generate_txt


ExportFormat = Literal["pdf", "docx", "xlsx", "csv", "txt", "md", "html"]


class ExportDocumentResult(TypedDict):
    success: bool
    file_name: str
    file_url: str


Generator = Callable[[str, str, Path, list[str]], None]


def _lazy_generator(module_name: str, function_name: str) -> Generator:
    def _generator(title: str, content: str, output_path: Path, images: list[str]) -> None:
        module = import_module(f".{module_name}", package=__package__)
        generator = getattr(module, function_name)
        generator(title, content, output_path, images=images)

    return _generator


def _text_only_generator(generator: Callable[[str, str, Path], None]) -> Generator:
    def _wrapped(title: str, content: str, output_path: Path, images: list[str]) -> None:
        if images:
            raise ValueError("Image content only supports pdf or docx")
        generator(title, content, output_path)

    return _wrapped


GENERATORS: dict[str, tuple[str, Generator]] = {
    "pdf": ("pdf", _lazy_generator("pdf_generator", "generate_pdf")),
    "docx": ("docx", _lazy_generator("docx_generator", "generate_docx")),
    "xlsx": ("xlsx", _text_only_generator(generate_xlsx)),
    "csv": ("csv", _text_only_generator(generate_csv)),
    "txt": ("txt", _text_only_generator(generate_txt)),
    "md": ("md", _text_only_generator(generate_md)),
    "markdown": ("md", _text_only_generator(generate_md)),
    "html": ("html", _text_only_generator(generate_html)),
}


def export_document(title: str, content: str, format: str, images: list[str] | None = None) -> ExportDocumentResult:
    """Export text content, or text plus images, and return a download URL."""
    normalized_format = (format or "").strip().lower()
    if normalized_format not in GENERATORS:
        supported = ", ".join(["pdf", "docx", "xlsx", "csv", "txt", "md", "html"])
        raise ValueError(f"Unsupported format: {format}. Supported formats: {supported}")

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
