from __future__ import annotations

import csv
from pathlib import Path


def generate_csv(title: str, content: str, output_path: Path) -> None:
    rows = [line.split(",") for line in (content or "").splitlines()]
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(rows)

