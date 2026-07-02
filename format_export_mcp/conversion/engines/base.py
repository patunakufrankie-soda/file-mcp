from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ConversionResult:
    """Result from engine conversion."""

    success: bool
    output_path: Path | None = None
    error_message: str | None = None
    metadata: dict[str, Any] | None = None


class BaseEngine(ABC):
    """Base class for all conversion engines."""

    @abstractmethod
    def can_convert(self, source_format: str, target_format: str) -> bool:
        """Check if this engine can handle the conversion."""
        pass

    @abstractmethod
    def convert(
        self,
        source_path: Path,
        source_format: str,
        target_format: str,
        output_path: Path,
    ) -> ConversionResult:
        """Execute the conversion.

        Args:
            source_path: Path to source file
            source_format: Source format (e.g., 'pdf', 'docx')
            target_format: Target format
            output_path: Where to write the output

        Returns:
            ConversionResult with success status and optional error message
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine name for logging."""
        pass
