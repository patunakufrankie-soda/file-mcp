from __future__ import annotations

import csv
from io import StringIO

from .markdown_blocks import parse_markdown_blocks


def _markdown_table_rows(content: str) -> list[list[str]] | None:
    for block in parse_markdown_blocks(content):
        if block.kind == "table" and block.rows:
            return [list(row) for row in block.rows]
    return None


def parse_delimited_rows(content: str) -> list[list[str]]:
    text = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    if not text:
        return [[]]

    markdown_rows = _markdown_table_rows(text)
    if markdown_rows is not None:
        return markdown_rows

    reader = csv.reader(StringIO(text))
    rows = [row for row in reader]
    return rows or [[]]
