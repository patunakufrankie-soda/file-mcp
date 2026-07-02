from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def is_pandoc_available() -> bool:
    return shutil.which("pandoc") is not None


def run_command(
    arguments: list[str], *, timeout: int = 60, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
