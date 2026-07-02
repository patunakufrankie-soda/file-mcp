from __future__ import annotations

from html import escape
from pathlib import Path

from ...utils.markdown_blocks import (
    parse_markdown_blocks,
    render_markdown_inlines_as_html,
)


def generate_html(title: str, content: str, output_path: Path) -> None:
    safe_title = escape(title or "Export")
    fragments: list[str] = []
    pending_list_kind: str | None = None
    pending_list_items: list[str] = []

    def flush_list() -> None:
        nonlocal pending_list_kind, pending_list_items
        if not pending_list_kind:
            return
        tag_name = "ol" if pending_list_kind == "ordered_item" else "ul"
        items_html = "".join(f"<li>{item}</li>" for item in pending_list_items)
        fragments.append(f"<{tag_name}>{items_html}</{tag_name}>")
        pending_list_kind = None
        pending_list_items = []

    for block in parse_markdown_blocks(content or ""):
        if block.kind in {"bullet_item", "ordered_item"}:
            if pending_list_kind and pending_list_kind != block.kind:
                flush_list()
            pending_list_kind = block.kind
            pending_list_items.append(render_markdown_inlines_as_html(block.text))
            continue

        flush_list()
        if block.kind == "heading":
            level = min(block.level + 1, 6)
            fragments.append(
                f"<h{level}>{render_markdown_inlines_as_html(block.text)}</h{level}>"
            )
        elif block.kind == "code":
            fragments.append(f"<pre><code>{escape(block.text)}</code></pre>")
        elif block.kind == "table" and block.rows:
            header_row, *body_rows = block.rows
            header_html = "".join(
                f"<th>{render_markdown_inlines_as_html(cell)}</th>"
                for cell in header_row
            )
            body_html = "".join(
                "<tr>"
                + "".join(
                    f"<td>{render_markdown_inlines_as_html(cell)}</td>" for cell in row
                )
                + "</tr>"
                for row in body_rows
            )
            fragments.append(
                f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"
            )
        else:
            fragments.append(f"<p>{render_markdown_inlines_as_html(block.text)}</p>")

    flush_list()

    paragraphs = "".join(fragments) or "<p></p>"
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    body {{
      max-width: 880px;
      margin: 48px auto;
      padding: 0 24px;
      color: #1f2937;
      font-family: "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
      line-height: 1.75;
    }}
    h1 {{
      margin-bottom: 28px;
      font-size: 28px;
      line-height: 1.3;
    }}
    p {{
      margin: 0 0 12px;
      white-space: pre-wrap;
    }}
    pre {{
      margin: 0 0 16px;
      padding: 12px 14px;
      border-radius: 10px;
      background: #f3f4f6;
      overflow-x: auto;
      font-family: "SFMono-Regular", Consolas, monospace;
    }}
    li {{
      margin: 0 0 8px;
    }}
    ul, ol {{
      margin: 0 0 14px 20px;
      padding: 0;
    }}
    table {{
      border-collapse: collapse;
      margin: 0 0 18px;
      width: 100%;
    }}
    th, td {{
      border: 1px solid #d1d5db;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f9fafb;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <h1>{safe_title}</h1>
  <main>
    {paragraphs}
  </main>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
