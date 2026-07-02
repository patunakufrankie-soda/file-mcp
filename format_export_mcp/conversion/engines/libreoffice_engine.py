from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .base import BaseEngine, ConversionResult


logger = logging.getLogger(__name__)


class LibreOfficeEngine(BaseEngine):
    """LibreOffice conversion engine.

    Uses LibreOffice in headless mode for document conversions.

    Supports:
    - DOCX/DOC/ODT → PDF
    - XLSX/XLS/ODS → PDF
    - PPTX/PPT/ODP → PDF
    - Various Office format conversions
    """

    @property
    def name(self) -> str:
        return "LibreOffice"

    def can_convert(self, source_format: str, target_format: str) -> bool:
        """Check if this engine can handle the conversion."""
        office_formats = {
            "docx",
            "doc",
            "odt",
            "xlsx",
            "xls",
            "ods",
            "pptx",
            "ppt",
            "odp",
        }

        # Office → PDF
        if source_format in office_formats and target_format == "pdf":
            return True

        # Office ↔ Office (same family)
        word_formats = {"docx", "doc", "odt"}
        sheet_formats = {"xlsx", "xls", "ods"}

        if source_format in word_formats and target_format in word_formats:
            return True
        if source_format in sheet_formats and target_format in sheet_formats:
            return True

        return False

    def convert(
        self,
        source_path: Path,
        source_format: str,
        target_format: str,
        output_path: Path,
    ) -> ConversionResult:
        """Convert using LibreOffice headless mode."""

        # Check if LibreOffice is available
        if not self._is_libreoffice_available():
            return ConversionResult(
                success=False,
                error_message="LibreOffice is not installed or not in PATH",
            )

        try:
            # LibreOffice command
            # soffice --headless --convert-to pdf --outdir output_dir input_file
            cmd = [
                "soffice",
                "--headless",
                "--convert-to",
                target_format,
                "--outdir",
                str(output_path.parent),
                str(source_path),
            ]

            logger.info(f"Running LibreOffice: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # 60 seconds timeout
                check=False,
            )

            if result.returncode != 0:
                logger.error(f"LibreOffice failed: {result.stderr}")
                return ConversionResult(
                    success=False,
                    error_message=f"LibreOffice conversion failed: {result.stderr}",
                )

            # LibreOffice generates filename based on source, need to rename
            expected_output = output_path.parent / f"{source_path.stem}.{target_format}"
            if expected_output.exists() and expected_output != output_path:
                expected_output.rename(output_path)

            if not output_path.exists():
                return ConversionResult(
                    success=False,
                    error_message="LibreOffice completed but output file not found",
                )

            logger.info(
                f"Successfully converted {source_format} to {target_format} using LibreOffice"
            )
            return ConversionResult(success=True, output_path=output_path)

        except subprocess.TimeoutExpired:
            logger.error("LibreOffice conversion timed out")
            return ConversionResult(
                success=False, error_message="Conversion timed out (60s limit)"
            )

        except Exception as e:
            logger.error(f"LibreOffice conversion failed: {e}")
            return ConversionResult(
                success=False, error_message=f"LibreOffice conversion failed: {str(e)}"
            )

    def _is_libreoffice_available(self) -> bool:
        """Check if LibreOffice is available."""
        try:
            result = subprocess.run(
                ["soffice", "--version"], capture_output=True, timeout=5, check=False
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
