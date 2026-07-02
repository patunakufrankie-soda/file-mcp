from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TypedDict

from ..utils.format_utils import (
    ConversionError,
    build_failure_result,
    ensure_supported_target_format,
)
from ..utils.input_loader import load_input
from ..storage.manager import build_file_url, build_output_path, store_export_file
from .services.conversion_service import ConversionService


logger = logging.getLogger(__name__)


class FileConvertResult(TypedDict, total=False):
    success: bool
    input_uri: str
    output_path: str
    output_url: str
    source_format: str
    target_format: str
    message: str
    error_type: str


# Global conversion service instance
_conversion_service: ConversionService | None = None


def _get_conversion_service() -> ConversionService:
    """Get or create the global conversion service instance."""
    global _conversion_service
    if _conversion_service is None:
        _conversion_service = ConversionService()
        logger.info("Initialized ConversionService")
    return _conversion_service


def convert_file_document(input_uri: str, target_format: str) -> FileConvertResult:
    """Convert a document file from one format to another.

    This is the new implementation using ConversionService architecture.

    Args:
        input_uri: Local file path or HTTP/HTTPS URL to source document
        target_format: Target format (txt, md, pdf, docx, etc.)

    Returns:
        FileConvertResult with success status, paths, and metadata
    """
    loaded_input = None
    temp_output = None

    try:
        # 1. Validate and normalize target format
        normalized_target = ensure_supported_target_format(target_format)
        logger.info(f"Converting {input_uri} to {normalized_target}")

        # 2. Load input file (handles local files and URLs)
        loaded_input = load_input(input_uri)
        source_format = loaded_input.source_format
        source_path = loaded_input.local_path

        logger.info(f"Detected source format: {source_format}")

        # 3. Generate output path in temp directory first
        title = source_path.stem
        temp_output = build_output_path(title, normalized_target)

        # 4. Use ConversionService to perform conversion
        service = _get_conversion_service()
        result = service.convert(
            source_file=source_path,
            target_format=normalized_target,
            output_path=temp_output,
        )

        # 5. Handle conversion result
        if not result.success:
            error_message = result.error_message or "Conversion failed"
            logger.error(f"Conversion failed: {error_message}")
            return build_failure_result(
                input_uri=input_uri,
                source_format=source_format,
                target_format=normalized_target,
                error_type="conversion_failed",
                message=error_message,
            )

        # 6. Store converted file in exports directory
        if result.output_path and result.output_path.exists():
            stored_path = store_export_file(result.output_path, result.output_path.name)

            logger.info(f"Conversion successful: {stored_path}")

            return {
                "success": True,
                "input_uri": input_uri,
                "output_path": str(stored_path),
                "output_url": build_file_url(stored_path.name),
                "source_format": source_format,
                "target_format": normalized_target,
                "message": "转换成功",
            }
        else:
            logger.error("Conversion succeeded but output file not found")
            return build_failure_result(
                input_uri=input_uri,
                source_format=source_format,
                target_format=normalized_target,
                error_type="conversion_failed",
                message="Output file not generated",
            )

    except ConversionError as e:
        logger.error(f"Conversion error: {e.error_type} - {e.message}")
        return build_failure_result(
            input_uri=input_uri,
            source_format=None,
            target_format=target_format,
            error_type=e.error_type,
            message=e.message,
        )

    except Exception as e:
        logger.exception(f"Unexpected error during conversion: {e}")
        return build_failure_result(
            input_uri=input_uri,
            source_format=None,
            target_format=None,
            error_type="internal_error",
            message=f"Internal error: {str(e)}",
        )

    finally:
        # Cleanup temporary files
        if loaded_input:
            try:
                loaded_input.cleanup()
            except Exception as e:
                logger.warning(f"Failed to cleanup loaded input: {e}")
