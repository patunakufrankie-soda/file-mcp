from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import BaseEngine, ConversionResult

logger = logging.getLogger(__name__)

_HEADING_STYLE_RE = re.compile(r"^Heading\s*([1-9])$", re.IGNORECASE)


@dataclass(frozen=True)
class _ParagraphBlock:
    text: str
    heading_level: int | None = None


@dataclass(frozen=True)
class _TableBlock:
    rows: tuple[tuple[str, ...], ...]


class DocxEngine(BaseEngine):
    """Extract paragraphs and table cells from DOCX files."""

    @property
    def name(self) -> str:
        return "Docx"

    def can_convert(self, source_format: str, target_format: str) -> bool:
        if source_format != "docx":
            return False
        return target_format in ("txt", "md")

    def convert(
        self,
        source_path: Path,
        source_format: str,
        target_format: str,
        output_path: Path,
    ) -> ConversionResult:
        try:
            import docx
        except ImportError:
            return ConversionResult(
                success=False,
                error_message="python-docx is not installed. Run: pip install python-docx",
            )

        try:
            doc = docx.Document(str(source_path))
            blocks = self._extract_blocks(doc)
            title = (doc.core_properties.title or "").strip()

            if target_format == "txt":
                content = self._render_text(blocks)
            else:
                content = self._render_markdown(blocks, title)

            output_path.write_text(content, encoding="utf-8")

            return ConversionResult(
                success=True,
                output_path=output_path,
                metadata={
                    "engine": self.name,
                    "paragraph_count": sum(
                        isinstance(block, _ParagraphBlock) for block in blocks
                    ),
                    "table_count": sum(
                        isinstance(block, _TableBlock) for block in blocks
                    ),
                },
            )

        except Exception as exc:
            logger.exception(f"DOCX extraction failed: {exc}")
            return ConversionResult(
                success=False,
                error_message=f"Failed to extract text from DOCX: {exc}",
            )

    def _extract_blocks(
        self, document: Any
    ) -> list[_ParagraphBlock | _TableBlock]:
        blocks: list[_ParagraphBlock | _TableBlock] = []

        for item in document.iter_inner_content():
            if hasattr(item, "rows"):
                rows = tuple(
                    tuple(self._extract_cell_text(cell) for cell in row.cells)
                    for row in item.rows
                )
                if rows:
                    blocks.append(_TableBlock(rows=rows))
                continue

            text = item.text.strip()
            if text:
                blocks.append(
                    _ParagraphBlock(
                        text=text,
                        heading_level=self._heading_level(item),
                    )
                )

        return blocks

    def _extract_cell_text(self, cell: Any) -> str:
        parts: list[str] = []

        for item in cell.iter_inner_content():
            if hasattr(item, "rows"):
                for row in item.rows:
                    nested_cells = [
                        self._extract_cell_text(nested_cell).strip()
                        for nested_cell in row.cells
                    ]
                    nested_row = "\t".join(nested_cells).strip()
                    if nested_row:
                        parts.append(nested_row)
                continue

            text = item.text.strip()
            if text:
                parts.append(text)

        return "\n".join(parts)

    @staticmethod
    def _heading_level(paragraph: Any) -> int | None:
        style = paragraph.style
        style_name = (getattr(style, "name", "") or "").strip()
        style_id = (getattr(style, "style_id", "") or "").strip()

        if style_name.lower() == "title":
            return 1

        for value in (style_name, style_id):
            match = _HEADING_STYLE_RE.match(value)
            if match:
                return int(match.group(1))

        return None

    @staticmethod
    def _render_text(blocks: list[_ParagraphBlock | _TableBlock]) -> str:
        sections: list[str] = []

        for block in blocks:
            if isinstance(block, _ParagraphBlock):
                sections.append(block.text)
                continue

            rows = [
                "\t".join(cell.replace("\n", " ") for cell in row)
                for row in block.rows
            ]
            sections.append("\n".join(rows))

        return "\n\n".join(sections)

    def _render_markdown(
        self,
        blocks: list[_ParagraphBlock | _TableBlock],
        document_title: str,
    ) -> str:
        sections: list[str] = []
        title_rendered = False

        for block in blocks:
            if isinstance(block, _TableBlock):
                sections.append(self._render_markdown_table(block.rows))
                continue

            heading_level = block.heading_level
            if document_title and not title_rendered and block.text == document_title:
                heading_level = 1
                title_rendered = True

            if heading_level is not None:
                sections.append(f"{'#' * heading_level} {block.text}")
            else:
                sections.append(block.text)

        if document_title and not title_rendered:
            sections.insert(0, f"# {document_title}")

        return "\n\n".join(sections)

    @staticmethod
    def _render_markdown_table(rows: tuple[tuple[str, ...], ...]) -> str:
        column_count = max(len(row) for row in rows)

        def render_row(row: tuple[str, ...]) -> str:
            cells = list(row) + [""] * (column_count - len(row))
            escaped = [
                cell.replace("\\", "\\\\")
                .replace("|", "\\|")
                .replace("\r\n", "\n")
                .replace("\n", "<br>")
                for cell in cells
            ]
            return f"| {' | '.join(escaped)} |"

        lines = [
            render_row(rows[0]),
            f"| {' | '.join('---' for _ in range(column_count))} |",
        ]
        lines.extend(render_row(row) for row in rows[1:])
        return "\n".join(lines)
