from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class Section:
    """A section in the document (paragraph, heading, table, etc.)."""

    type: Literal["heading", "paragraph", "table", "image", "list", "code"]
    level: int = 0  # For headings: 1-6
    content: Any = None
    style: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentIR:
    """Intermediate representation for document content (semantic layer).

    This is a lightweight structure that captures the logical content
    of a document without worrying about precise layout/positioning.
    All engines should try to map their output to this structure.
    """

    metadata: dict[str, Any] = field(default_factory=dict)
    sections: list[Section] = field(default_factory=list)

    def add_heading(
        self, text: str, level: int = 1, style: dict[str, Any] | None = None
    ) -> None:
        """Add a heading section."""
        self.sections.append(
            Section(type="heading", level=level, content=text, style=style or {})
        )

    def add_paragraph(self, text: str, style: dict[str, Any] | None = None) -> None:
        """Add a paragraph section."""
        self.sections.append(Section(type="paragraph", content=text, style=style or {}))

    def add_table(
        self, rows: list[list[str]], style: dict[str, Any] | None = None
    ) -> None:
        """Add a table section."""
        self.sections.append(Section(type="table", content=rows, style=style or {}))

    def add_code(
        self, code: str, language: str = "", style: dict[str, Any] | None = None
    ) -> None:
        """Add a code block section."""
        style_with_lang = style or {}
        if language:
            style_with_lang["language"] = language
        self.sections.append(Section(type="code", content=code, style=style_with_lang))
