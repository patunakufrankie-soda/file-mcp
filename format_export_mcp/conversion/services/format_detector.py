from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
import logging


logger = logging.getLogger(__name__)


@dataclass
class DocumentFeatures:
    """Features detected from a document."""

    is_scanned: bool = False
    has_text_layer: bool = True
    has_tables: bool = False
    has_images: bool = False
    has_multicolumn: bool = False
    has_formulas: bool = False
    page_count: int = 1
    estimated_complexity: str = "simple"  # "simple" | "moderate" | "complex"

    # Enhanced PDF analysis fields
    image_count: int = 0
    table_count: int = 0
    text_block_count: int = 0
    text_coverage_ratio: float = 0.0  # 0.0 - 1.0
    has_multipage: bool = False

    # Analysis metadata
    analysis_method: str = "basic"
    analysis_confidence: str = "high"  # "high" | "medium" | "low"
    detected_format: str = ""

    # Routing strategy recommendation (Phase 2)
    recommended_strategy: str = ""  # "text_pdf" | "scanned_pdf" | "mixed_pdf" | "complex_layout_pdf" | "office_like_pdf"


class FormatDetector:
    """Detect document format and analyze features."""

    @staticmethod
    def detect_format(file_path: Path) -> str:
        """Detect format from file path.

        Args:
            file_path: Path to the file

        Returns:
            Format string (e.g., 'pdf', 'docx', 'txt')
        """
        suffix = file_path.suffix.lower().lstrip(".")

        # Normalize common variations
        if suffix in ("markdown", "mdown", "mkd"):
            return "md"
        if suffix == "text":
            return "txt"
        if suffix in ("jpeg", "jpg"):
            return "jpg"

        # Use mimetype as fallback
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            mime_map = {
                "application/pdf": "pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
                "text/plain": "txt",
                "text/markdown": "md",
                "text/csv": "csv",
                "text/html": "html",
            }
            detected = mime_map.get(mime_type)
            if detected:
                return detected

        return suffix or "unknown"

    @staticmethod
    def analyze_features(file_path: Path, format: str) -> DocumentFeatures:
        """Analyze document features for routing decisions.

        Args:
            file_path: Path to the file
            format: Detected format

        Returns:
            DocumentFeatures with detected characteristics
        """
        features = DocumentFeatures(detected_format=format)

        # PDF-specific analysis
        if format == "pdf":
            features = FormatDetector._analyze_pdf(file_path)

        # Text formats are simple by default
        elif format in ("txt", "md"):
            features.estimated_complexity = "simple"
            features.page_count = 1
            features.analysis_method = "text_format"
            features.analysis_confidence = "high"

        # Office formats - assume moderate complexity
        elif format in ("docx", "xlsx", "pptx"):
            features.estimated_complexity = "moderate"
            features.has_tables = format == "xlsx"
            features.analysis_method = "office_heuristic"
            features.analysis_confidence = "medium"

        return features

    @staticmethod
    def _analyze_pdf(file_path: Path) -> DocumentFeatures:
        """Analyze PDF-specific features with deep inspection.

        Detects:
        - Text layer presence and coverage
        - Scanned vs native PDF
        - Image count and distribution
        - Table detection
        - Text block count
        - Multi-column layout
        - Complexity estimation
        """
        features = DocumentFeatures(detected_format="pdf")

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            features.page_count = len(doc)
            features.has_multipage = features.page_count > 1
            features.analysis_method = "pymupdf_deep"

            total_text_length = 0
            total_page_area = 0
            total_images = 0
            total_text_blocks = 0

            # Analyze all pages (sample first 5 for large docs)
            sample_pages = min(5, features.page_count)
            for page_idx in range(sample_pages):
                page = doc[page_idx]

                # Text analysis
                text = page.get_text()
                if isinstance(text, str) and text:
                    total_text_length += len(text.strip())

                # Text blocks analysis (indicates structure)
                text_blocks = page.get_text("blocks")
                total_text_blocks += len(text_blocks)

                # Image analysis
                image_list = page.get_images()
                total_images += len(image_list)

                # Page area for coverage calculation
                rect = page.rect
                total_page_area += rect.width * rect.height

                # Multi-column detection: check if text blocks span < 60% of page width
                if len(text_blocks) > 3:
                    narrow_blocks = sum(
                        1
                        for block in text_blocks
                        if len(block) >= 5
                        and isinstance(block[2], (int, float))
                        and isinstance(block[0], (int, float))
                        and (float(block[2]) - float(block[0])) < rect.width * 0.6
                    )
                    if narrow_blocks > len(text_blocks) * 0.6:
                        features.has_multicolumn = True

            # Calculate averages
            features.image_count = total_images
            features.text_block_count = total_text_blocks
            features.has_images = total_images > 0

            # Text layer detection
            features.has_text_layer = total_text_length > 50
            features.is_scanned = not features.has_text_layer

            # Text coverage ratio (simple heuristic)
            if total_text_length > 0:
                features.text_coverage_ratio = min(
                    1.0, total_text_length / (sample_pages * 2000)
                )

            # Table detection (heuristic: check for structured blocks)
            if total_text_blocks > sample_pages * 10:
                features.has_tables = True
                features.table_count = total_text_blocks // 15

            # Complexity estimation
            complexity_score = 0
            if features.page_count > 10:
                complexity_score += 1
            if features.page_count > 50:
                complexity_score += 1
            if features.has_multicolumn:
                complexity_score += 1
            if features.image_count > 5:
                complexity_score += 1
            if features.has_tables:
                complexity_score += 1
            if features.is_scanned:
                complexity_score += 2

            if complexity_score >= 4:
                features.estimated_complexity = "complex"
            elif complexity_score >= 2:
                features.estimated_complexity = "moderate"
            else:
                features.estimated_complexity = "simple"

            features.analysis_confidence = "high"

            # Determine recommended strategy for PDF → DOCX routing
            features.recommended_strategy = FormatDetector._determine_pdf_strategy(
                features
            )

            doc.close()

            logger.info(
                f"PDF analysis: {features.page_count} pages, "
                f"{features.image_count} images, "
                f"{features.text_block_count} text blocks, "
                f"complexity={features.estimated_complexity}, "
                f"scanned={features.is_scanned}, "
                f"strategy={features.recommended_strategy}"
            )

        except ImportError:
            features.has_text_layer = True
            features.is_scanned = False
            features.estimated_complexity = "moderate"
            features.analysis_method = "fallback"
            features.analysis_confidence = "low"
            logger.warning("PyMuPDF not available, using fallback analysis")

        except Exception as e:
            features.estimated_complexity = "moderate"
            features.analysis_method = "error_fallback"
            features.analysis_confidence = "low"
            logger.error(f"PDF analysis failed: {e}")

        return features

    @staticmethod
    def _determine_pdf_strategy(features: DocumentFeatures) -> str:
        """Determine recommended conversion strategy for PDF based on features.

        Returns one of:
        - text_pdf: Clean text-based PDF, good for text extraction
        - scanned_pdf: Image-based PDF, needs OCR
        - mixed_pdf: Contains both text and significant images
        - complex_layout_pdf: Multi-column, tables, complex structure
        - office_like_pdf: Appears to be generated from Office docs
        """
        # Scanned PDF: no text layer (is_scanned flag is authoritative)
        if features.is_scanned:
            return "scanned_pdf"

        # Complex layout: multi-column, many tables, or high structural complexity
        if features.has_multicolumn or features.table_count > 3:
            return "complex_layout_pdf"

        # Office-like: moderate complexity, has text, some structure
        # Heuristic: generated from Office if text-heavy with some structure
        if (
            features.text_coverage_ratio > 0.3
            and features.text_block_count > 3
            and features.image_count <= 2
            and not features.has_multicolumn
        ):
            return "office_like_pdf"

        # Mixed: significant images and text
        if features.has_images and features.image_count >= 3:
            return "mixed_pdf"

        # Default: text PDF (includes low text coverage but has_text_layer)
        return "text_pdf"
