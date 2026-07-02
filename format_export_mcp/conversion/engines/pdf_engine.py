from __future__ import annotations

import logging
from pathlib import Path

from .base import BaseEngine, ConversionResult
from ..ir.document_ir import DocumentIR


logger = logging.getLogger(__name__)


class PdfEngine(BaseEngine):
    """PDF conversion engine using PyMuPDF (fitz).

    Supports:
    - PDF → TXT: Extract plain text
    - PDF → MD: Extract text with basic structure (headings, paragraphs)
    - PDF → DocumentIR: Parse into intermediate representation
    """

    @property
    def name(self) -> str:
        return "PyMuPDF"

    def can_convert(self, source_format: str, target_format: str) -> bool:
        """Check if this engine can handle the conversion."""
        if source_format != "pdf":
            return False
        return target_format in ("txt", "md", "ir")

    def convert(
        self,
        source_path: Path,
        source_format: str,
        target_format: str,
        output_path: Path,
    ) -> ConversionResult:
        """Convert PDF to text-based formats."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return ConversionResult(
                success=False,
                error_message="PyMuPDF (fitz) is not installed. Install with: pip install PyMuPDF",
            )

        try:
            doc = fitz.open(source_path)

            if target_format == "txt":
                text = self._extract_plain_text(doc)
                output_path.write_text(text, encoding="utf-8")

            elif target_format == "md":
                markdown = self._extract_markdown(doc)
                output_path.write_text(markdown, encoding="utf-8")

            elif target_format == "ir":
                # For IR, we return the DocumentIR object in metadata
                ir = self._extract_to_ir(doc)
                # Store as JSON for now
                import json

                output_path.write_text(
                    json.dumps(
                        {
                            "metadata": ir.metadata,
                            "sections": [
                                {
                                    "type": s.type,
                                    "level": s.level,
                                    "content": s.content,
                                    "style": s.style,
                                }
                                for s in ir.sections
                            ],
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

            page_count = len(doc)
            doc.close()

            logger.info(f"Successfully converted PDF to {target_format} using PyMuPDF")
            return ConversionResult(
                success=True,
                output_path=output_path,
                metadata={"page_count": page_count},
            )

        except Exception as e:
            logger.error(f"PyMuPDF conversion failed: {e}")
            return ConversionResult(
                success=False, error_message=f"PDF conversion failed: {str(e)}"
            )

    def _extract_plain_text(self, doc) -> str:
        """Extract plain text from all pages."""
        text_parts = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                text_parts.append(text)
        return "\n\n".join(text_parts)

    def _extract_markdown(self, doc) -> str:
        """Extract text with basic markdown structure.

        This is a simple implementation. Future improvements:
        - Detect headings by font size
        - Preserve lists
        - Extract tables
        - Handle multi-column layouts
        """
        markdown_parts = []

        for page_num, page in enumerate(doc):
            text = page.get_text()
            if not text.strip():
                continue

            # Simple heuristic: if a line is short and followed by blank line, treat as heading
            lines = text.split("\n")
            processed = []
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue

                # Check if this looks like a heading (short line, next line is empty or different)
                if len(line) < 80 and i + 1 < len(lines) and not lines[i + 1].strip():
                    processed.append(f"## {line}\n")
                    i += 2
                else:
                    processed.append(line)
                    i += 1

            markdown_parts.append("\n\n".join(processed))

        return "\n\n---\n\n".join(markdown_parts)

    def _extract_to_ir(self, doc) -> DocumentIR:
        """Extract PDF content into DocumentIR."""
        ir = DocumentIR()
        ir.metadata = {"page_count": len(doc), "source": "pdf", "engine": self.name}

        for page in doc:
            text = page.get_text()
            if not text.strip():
                continue

            # Simple paragraph extraction for now
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for para in paragraphs:
                # Very simple heuristic: short lines might be headings
                if len(para) < 80 and "\n" not in para:
                    ir.add_heading(para, level=2)
                else:
                    ir.add_paragraph(para)

        return ir
