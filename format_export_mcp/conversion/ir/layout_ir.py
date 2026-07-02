from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LayoutElement:
    """A positioned element on a page."""

    x: float
    y: float
    width: float
    height: float
    type: str  # "text", "image", "line", etc.
    content: Any = None
    style: dict[str, Any] = field(default_factory=dict)


@dataclass
class Page:
    """A single page with positioned elements."""

    width: float
    height: float
    elements: list[LayoutElement] = field(default_factory=list)


@dataclass
class LayoutIR:
    """Intermediate representation for document layout (positioning layer).

    This structure captures precise positioning and layout information,
    useful for high-fidelity conversions where visual layout matters.

    Currently reserved for future use. First version focuses on DocumentIR.
    """

    pages: list[Page] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
