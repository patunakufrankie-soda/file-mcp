from __future__ import annotations

from html import escape
from pathlib import Path


def generate_html(title: str, content: str, output_path: Path) -> None:
    safe_title = escape(title or "Export")
    paragraphs = "".join(
        f"<p>{escape(line)}</p>" if line.strip() else "<br>"
        for line in (content or "").splitlines()
    )
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

