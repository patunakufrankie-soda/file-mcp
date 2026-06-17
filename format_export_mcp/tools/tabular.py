from __future__ import annotations

import csv
from io import StringIO


def parse_delimited_rows(content: str) -> list[list[str]]:
    text = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    if not text:
        return [[]]

    reader = csv.reader(StringIO(text))
    rows = [row for row in reader]
    return rows or [[]]
