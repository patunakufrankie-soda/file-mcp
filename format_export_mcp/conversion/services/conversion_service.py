from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .format_detector import DocumentFeatures, FormatDetector
from .conversion_logger import ConversionLoggerService, ConversionLog
from ..engines.base import BaseEngine, ConversionResult
from ..router import ConversionRouter
from ..ir.document_ir import DocumentIR


logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """Quality assessment of conversion result."""

    level: str  # "high" | "medium" | "low" | "fallback"
    score: float  # 0-100
    issues: list[str]
    page_count_match: bool = False
    text_completeness: float = 0.0
    image_count_match: bool = False
    table_count_match: bool = False


class ConversionService:
    """Main service for orchestrating document conversions.

    Responsibilities:
    - Format detection
    - Routing to appropriate engines
    - Fallback handling
    - Post-processing
    - Quality assessment
    - Conversion logging
    """

    def __init__(self, log_file: Path | None = None) -> None:
        self.detector = FormatDetector()
        self.router = ConversionRouter()
        self.logger_service = ConversionLoggerService(log_file)

    def convert(
        self,
        source_file: Path,
        target_format: str,
        output_path: Path | None = None,
    ) -> ConversionResult:
        """Convert a document from source format to target format.

        Args:
            source_file: Path to source document
            target_format: Target format (e.g., 'pdf', 'docx', 'md')
            output_path: Optional output path; auto-generated if not provided

        Returns:
            ConversionResult with success status and output path or error
        """
        # 1. Detect format and features
        source_format = self.detector.detect_format(source_file)
        features = self.detector.analyze_features(source_file, source_format)

        logger.info(
            f"Converting {source_format} -> {target_format}, "
            f"complexity={features.estimated_complexity}, "
            f"scanned={features.is_scanned}, "
            f"pages={features.page_count}, "
            f"images={features.image_count}"
        )

        # 2. Get conversion route
        route = self.router.get_route(source_format, target_format, features)
        if not route:
            # Special handling for scanned PDFs
            if source_format == "pdf" and features.is_scanned:
                return ConversionResult(
                    success=False,
                    error_message="OCR_REQUIRED: This is a scanned PDF without text layer. OCR functionality is not yet implemented.",
                    metadata={
                        "error_code": "OCR_REQUIRED",
                        "recommended_strategy": features.recommended_strategy,
                        "is_scanned": True,
                    },
                )
            return ConversionResult(
                success=False,
                error_message=f"No conversion route for {source_format} -> {target_format}",
            )

        # 3. Generate output path if not provided
        if output_path is None:
            output_path = source_file.parent / f"{source_file.stem}.{target_format}"

        # 4. Create conversion log
        primary_engine = self.router.get_engine_instance(route.primary)
        conv_log = self.logger_service.create_log(
            source_format=source_format,
            target_format=target_format,
            engine_name=primary_engine.name,
        )

        # Store source features
        conv_log.source_features = {
            "complexity": features.estimated_complexity,
            "is_scanned": features.is_scanned,
            "has_text_layer": features.has_text_layer,
            "has_images": features.has_images,
            "has_tables": features.has_tables,
        }
        conv_log.page_count_source = features.page_count
        conv_log.image_count_source = features.image_count
        conv_log.table_count_source = features.table_count

        # 5. Try primary engine
        logger.info(f"Using primary engine: {primary_engine.name}")
        start_time = self.logger_service.record_start(conv_log, source_file)

        result = primary_engine.convert(
            source_path=source_file,
            source_format=source_format,
            target_format=target_format,
            output_path=output_path,
        )

        # 6. Try fallback engines if primary fails
        if not result.success and route.fallbacks:
            logger.warning(f"Primary engine failed: {result.error_message}")
            for fallback_class in route.fallbacks:
                fallback_engine = self.router.get_engine_instance(fallback_class)
                logger.info(f"Trying fallback engine: {fallback_engine.name}")

                conv_log.fallback_used = True
                conv_log.engine_name = fallback_engine.name

                result = fallback_engine.convert(
                    source_path=source_file,
                    source_format=source_format,
                    target_format=target_format,
                    output_path=output_path,
                )

                if result.success:
                    logger.info(f"Fallback engine succeeded: {fallback_engine.name}")
                    break

        # 7. Record end and evaluate quality
        self.logger_service.record_end(
            conv_log,
            start_time,
            result.success,
            output_path if result.success else None,
            result.error_message or "",
        )

        if result.success:
            # Merge quality report from engine metadata if available
            if result.metadata and "quality_report" in result.metadata:
                engine_quality = result.metadata["quality_report"]
                conv_log.quality_level = engine_quality.get("quality_level", "unknown")

                # Store engine quality metrics
                if "text_length" in engine_quality:
                    conv_log.text_completeness = min(
                        1.0, engine_quality["text_length"] / 1000.0
                    )
            else:
                # Fallback: evaluate quality using service method
                quality = self.evaluate_quality(source_file, output_path, features)
                conv_log.quality_level = quality.level
                conv_log.text_completeness = quality.text_completeness

            # Apply post-processing
            self._apply_postprocessing(result, target_format)

        # 8. Save log
        self.logger_service.save_log(conv_log)

        return result

    def _apply_postprocessing(
        self, result: ConversionResult, target_format: str
    ) -> None:
        """Apply post-processing fixes to the converted document.

        Placeholder for future implementation:
        - Fix common conversion artifacts
        - Normalize styles
        - Validate structure
        """
        pass

    def evaluate_quality(
        self,
        source_path: Path,
        output_path: Path,
        source_features: DocumentFeatures,
    ) -> QualityReport:
        """Evaluate conversion quality.

        Compares source and output to assess conversion fidelity.
        """
        issues = []
        score = 100.0

        # Detect output format
        output_format = self.detector.detect_format(output_path)
        output_features = self.detector.analyze_features(output_path, output_format)

        # Page count comparison
        page_count_match = source_features.page_count == output_features.page_count
        if not page_count_match and source_features.page_count > 1:
            issues.append(
                f"Page count mismatch: {source_features.page_count} → {output_features.page_count}"
            )
            score -= 20

        # Image count comparison
        image_count_match = source_features.image_count == output_features.image_count
        if not image_count_match and source_features.image_count > 0:
            issues.append(
                f"Image count mismatch: {source_features.image_count} → {output_features.image_count}"
            )
            score -= 15

        # Table count comparison
        table_count_match = source_features.table_count == output_features.table_count
        if not table_count_match and source_features.table_count > 0:
            issues.append(
                f"Table count mismatch: {source_features.table_count} → {output_features.table_count}"
            )
            score -= 15

        # Text completeness (simplified heuristic)
        text_completeness = 1.0
        if source_features.text_coverage_ratio > 0:
            text_completeness = min(
                1.0,
                output_features.text_coverage_ratio
                / source_features.text_coverage_ratio,
            )
            if text_completeness < 0.8:
                issues.append(f"Text completeness: {text_completeness:.0%}")
                score -= 20

        # Determine quality level
        if score >= 90:
            level = "high"
        elif score >= 70:
            level = "medium"
        elif score >= 50:
            level = "low"
        else:
            level = "fallback"

        return QualityReport(
            level=level,
            score=max(0, score),
            issues=issues,
            page_count_match=page_count_match,
            text_completeness=text_completeness,
            image_count_match=image_count_match,
            table_count_match=table_count_match,
        )
