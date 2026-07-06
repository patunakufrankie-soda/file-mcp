from __future__ import annotations

from dataclasses import dataclass
from typing import Type

from .engines.base import BaseEngine
from .engines.pdf_engine import PdfEngine
from .engines.libreoffice_engine import LibreOfficeEngine
from .engines.markdown_engine import MarkdownEngine
from .engines.docx_engine import DocxEngine
from .engines.pdf_to_docx_engine import PdfToDocxEngine
from .engines.pdf2docx_engine import Pdf2DocxEngine
from .services.format_detector import DocumentFeatures


@dataclass
class ConversionRoute:
    """A conversion route with primary and fallback engines."""

    primary: Type[BaseEngine]
    fallbacks: list[Type[BaseEngine]]


class ConversionRouter:
    """Route conversions to appropriate engines based on format and features.

    This implements the routing logic discussed:
    - DOCX/PPT/XLS → PDF: LibreOffice
    - PDF → DOCX: (Future: FreeP2W, fallback to text extraction)
    - PDF → MD/TXT: PDF engine (text extraction or OCR)
    - MD/TXT → DOCX/PDF: Markdown engine
    """

    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], ConversionRoute] = {}
        self._engines: dict[str, BaseEngine] = {}
        self._init_routes()

    def _init_routes(self) -> None:
        """Initialize routing table."""

        # Office → PDF: LibreOffice
        for office_format in [
            "docx",
            "doc",
            "odt",
            "xlsx",
            "xls",
            "ods",
            "pptx",
            "ppt",
            "odp",
        ]:
            self._routes[(office_format, "pdf")] = ConversionRoute(
                primary=LibreOfficeEngine, fallbacks=[]
            )

        # PDF → Text formats: PDF engine
        for text_format in ["txt", "md"]:
            self._routes[("pdf", text_format)] = ConversionRoute(
                primary=PdfEngine, fallbacks=[]
            )

        # Markdown/Text → Other formats: Markdown engine
        for source in ["md", "markdown", "txt"]:
            for target in ["pdf", "docx", "html", "txt"]:
                self._routes[(source, target)] = ConversionRoute(
                    primary=MarkdownEngine, fallbacks=[]
                )
        self._routes[("txt", "md")] = ConversionRoute(
            primary=MarkdownEngine, fallbacks=[]
        )

        # DOCX → Text formats: Docx engine (extracts text using python-docx)
        for text_format in ["txt", "md"]:
            self._routes[("docx", text_format)] = ConversionRoute(
                primary=DocxEngine, fallbacks=[]
            )

        # Office ↔ Office (same family): LibreOffice
        word_formats = ["docx", "doc", "odt"]
        for src in word_formats:
            for tgt in word_formats:
                if src != tgt:
                    self._routes[(src, tgt)] = ConversionRoute(
                        primary=LibreOfficeEngine, fallbacks=[]
                    )

    def get_route(
        self,
        source_format: str,
        target_format: str,
        features: DocumentFeatures | None = None,
    ) -> ConversionRoute | None:
        """Get conversion route for given format pair.

        Args:
            source_format: Source format
            target_format: Target format
            features: Optional document features for advanced routing

        Returns:
            ConversionRoute or None if no route exists
        """
        # Normalize formats
        source_format = source_format.lower()
        target_format = target_format.lower()

        # Phase 2: Dynamic routing for PDF → DOCX based on features
        if source_format == "pdf" and target_format == "docx" and features:
            return self._route_pdf_to_docx(features)

        # Direct lookup
        route = self._routes.get((source_format, target_format))
        if route:
            return route

        return None

    def _route_pdf_to_docx(self, features: DocumentFeatures) -> ConversionRoute | None:
        """Route PDF → DOCX based on document features and recommended strategy.

        Strategy routing:
        - text_pdf: PdfToDocxEngine (our custom text extractor)
        - scanned_pdf: Return OCR_REQUIRED error (OCR not implemented yet)
        - mixed_pdf: PdfToDocxEngine with fallback to Pdf2DocxEngine
        - complex_layout_pdf: Pdf2DocxEngine with fallback to PdfToDocxEngine
        - office_like_pdf: LibreOffice (future) or Pdf2DocxEngine fallback
        """
        strategy = features.recommended_strategy

        if strategy == "text_pdf":
            # Simple text extraction works best
            return ConversionRoute(
                primary=PdfToDocxEngine,
                fallbacks=[Pdf2DocxEngine],
            )

        elif strategy == "scanned_pdf":
            # OCR not implemented - return None to trigger OCR_REQUIRED error
            return None

        elif strategy == "complex_layout_pdf":
            # pdf2docx handles complex layouts better
            return ConversionRoute(
                primary=Pdf2DocxEngine,
                fallbacks=[PdfToDocxEngine],
            )

        elif strategy == "mixed_pdf":
            # Both text and images - our engine handles this
            return ConversionRoute(
                primary=PdfToDocxEngine,
                fallbacks=[Pdf2DocxEngine],
            )

        elif strategy == "office_like_pdf":
            # Prefer pdf2docx for office-like documents
            return ConversionRoute(
                primary=Pdf2DocxEngine,
                fallbacks=[PdfToDocxEngine],
            )

        else:
            # Default fallback
            return ConversionRoute(
                primary=PdfToDocxEngine,
                fallbacks=[Pdf2DocxEngine],
            )

    def get_engine_instance(self, engine_class: Type[BaseEngine]) -> BaseEngine:
        """Get or create engine instance (singleton per class)."""
        engine_name = engine_class.__name__
        if engine_name not in self._engines:
            self._engines[engine_name] = engine_class()
        return self._engines[engine_name]

    def list_supported_conversions(self) -> list[tuple[str, str]]:
        """List all supported conversion pairs."""
        return list(self._routes.keys())
