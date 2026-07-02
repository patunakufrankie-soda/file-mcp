from __future__ import annotations

import logging
from pathlib import Path

from .base import BaseEngine, ConversionResult

logger = logging.getLogger(__name__)


class Pdf2DocxEngine(BaseEngine):
    """PDF to DOCX conversion using pdf2docx library.

    This engine uses the pdf2docx library which provides better layout preservation
    for complex PDFs. Falls back gracefully if not installed.
    """

    @property
    def name(self) -> str:
        return "pdf2docx"

    def can_convert(self, source_format: str, target_format: str) -> bool:
        """Check if this engine can handle the conversion."""
        return source_format == "pdf" and target_format == "docx"

    def convert(
        self,
        source_path: Path,
        source_format: str,
        target_format: str,
        output_path: Path,
    ) -> ConversionResult:
        """Convert PDF to DOCX using pdf2docx library."""
        try:
            from pdf2docx import Converter
        except ImportError:
            return ConversionResult(
                success=False,
                error_message=(
                    "pdf2docx library not installed. "
                    "Install with: pip install pdf2docx\n"
                    "Note: This is optional. System will use fallback engine."
                ),
            )

        try:
            # Create converter and convert
            cv = Converter(str(source_path))
            cv.convert(str(output_path))
            cv.close()

            # Get basic stats
            file_size = output_path.stat().st_size if output_path.exists() else 0

            logger.info(
                f"PDF → DOCX conversion complete using pdf2docx: "
                f"output size {file_size} bytes"
            )

            return ConversionResult(
                success=True,
                output_path=output_path,
                metadata={
                    "engine": self.name,
                    "output_file_size": file_size,
                    "quality_report": {
                        "quality_level": "high",
                        "output_file_size": file_size,
                        "issues": [],
                    },
                },
            )

        except Exception as e:
            logger.error(f"pdf2docx conversion failed: {e}", exc_info=True)
            return ConversionResult(
                success=False,
                error_message=f"pdf2docx conversion failed: {str(e)}",
            )
