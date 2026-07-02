from __future__ import annotations

import logging
from pathlib import Path

from .base import BaseEngine, ConversionResult
from ...export.service import export_document


logger = logging.getLogger(__name__)


class MarkdownEngine(BaseEngine):
    """Markdown conversion engine.

    Uses the existing export service to convert markdown to other formats.

    Supports:
    - MD → PDF
    - MD → DOCX
    - MD → TXT
    - MD → HTML
    """

    @property
    def name(self) -> str:
        return "Markdown"

    def can_convert(self, source_format: str, target_format: str) -> bool:
        """Check if this engine can handle the conversion."""
        if source_format not in ("md", "markdown", "txt"):
            return False

        return target_format in ("pdf", "docx", "txt", "html", "md")

    def convert(
        self,
        source_path: Path,
        source_format: str,
        target_format: str,
        output_path: Path,
    ) -> ConversionResult:
        """Convert markdown content using export service."""

        try:
            # Read markdown content
            content = source_path.read_text(encoding="utf-8")
            title = source_path.stem

            # Use export service to generate the target format
            # Note: export_document generates files in storage/exports with special naming
            # We need to generate to a temp location then move
            from ...storage.manager import build_output_path, store_export_file

            # Generate using export service
            temp_output = build_output_path(title, target_format)

            # Import the appropriate generator
            if target_format == "pdf":
                from ...export.generators.pdf_generator import generate_pdf

                generate_pdf(title, content, temp_output, images=[])
            elif target_format == "docx":
                from ...export.generators.docx_generator import generate_docx

                generate_docx(title, content, temp_output, images=[])
            elif target_format == "txt":
                from ...export.generators.txt_generator import generate_txt

                generate_txt(title, content, temp_output)
            elif target_format == "html":
                from ...export.generators.html_generator import generate_html

                generate_html(title, content, temp_output)
            elif target_format == "md":
                from ...export.generators.md_generator import generate_md

                generate_md(title, content, temp_output)
            else:
                return ConversionResult(
                    success=False,
                    error_message=f"Unsupported target format: {target_format}",
                )

            # Move to final location if needed
            if temp_output != output_path:
                import shutil

                shutil.move(str(temp_output), str(output_path))

            logger.info(f"Successfully converted markdown to {target_format}")
            return ConversionResult(success=True, output_path=output_path)

        except Exception as e:
            logger.error(f"Markdown conversion failed: {e}")
            return ConversionResult(
                success=False, error_message=f"Markdown conversion failed: {str(e)}"
            )
