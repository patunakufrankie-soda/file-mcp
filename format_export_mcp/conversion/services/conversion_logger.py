from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
from datetime import datetime
import json


logger = logging.getLogger(__name__)


@dataclass
class ConversionLog:
    """Unified conversion log entry."""

    # Basic info
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source_format: str = ""
    target_format: str = ""

    # Engine info
    engine_name: str = ""
    engine_version: str = ""

    # File info
    source_file: str = ""
    output_file: str = ""
    source_size_bytes: int = 0
    output_size_bytes: int = 0

    # Performance
    duration_seconds: float = 0.0

    # Result
    success: bool = False
    error_message: str = ""
    fallback_used: bool = False

    # Quality metrics
    quality_level: str = ""  # "high" | "medium" | "low" | "fallback"
    page_count_source: int = 0
    page_count_output: int = 0
    text_completeness: float = 0.0
    image_count_source: int = 0
    image_count_output: int = 0
    table_count_source: int = 0
    table_count_output: int = 0

    # Features detected
    source_features: dict[str, Any] = field(default_factory=dict)

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def log_to_console(self) -> None:
        """Log to console with appropriate level."""
        if self.success:
            logger.info(
                f"✓ {self.source_format} → {self.target_format} | "
                f"{self.engine_name} | {self.duration_seconds:.2f}s | "
                f"{self.source_size_bytes} → {self.output_size_bytes} bytes"
                + (f" | quality={self.quality_level}" if self.quality_level else "")
            )
        else:
            logger.error(
                f"✗ {self.source_format} → {self.target_format} | "
                f"{self.engine_name} | {self.duration_seconds:.2f}s | "
                f"Error: {self.error_message}"
            )


class ConversionLoggerService:
    """Service for logging conversions."""

    def __init__(self, log_file: Path | None = None):
        self.log_file = log_file

    def create_log(
        self,
        source_format: str,
        target_format: str,
        engine_name: str,
    ) -> ConversionLog:
        """Create a new conversion log entry."""
        return ConversionLog(
            source_format=source_format,
            target_format=target_format,
            engine_name=engine_name,
        )

    def record_start(self, log: ConversionLog, source_path: Path) -> float:
        """Record conversion start."""
        log.source_file = str(source_path)
        if source_path.exists():
            log.source_size_bytes = source_path.stat().st_size
        return time.time()

    def record_end(
        self,
        log: ConversionLog,
        start_time: float,
        success: bool,
        output_path: Path | None = None,
        error_message: str = "",
    ) -> None:
        """Record conversion end."""
        log.duration_seconds = time.time() - start_time
        log.success = success
        log.error_message = error_message

        if output_path and output_path.exists():
            log.output_file = str(output_path)
            log.output_size_bytes = output_path.stat().st_size

    def save_log(self, log: ConversionLog) -> None:
        """Save log entry to file and console."""
        log.log_to_console()

        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(log.to_json() + "\n")
            except Exception as e:
                logger.warning(f"Failed to write log to file: {e}")
