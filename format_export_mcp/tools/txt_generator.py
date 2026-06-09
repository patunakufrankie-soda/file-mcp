from __future__ import annotations

from pathlib import Path


def generate_txt(title: str, content: str, output_path: Path) -> None:
    body = content or ""
    output_path.write_text(body, encoding="utf-8")

