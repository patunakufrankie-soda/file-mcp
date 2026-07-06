from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re


@dataclass(slots=True)
class MarkdownBlock:
    kind: str
    text: str
    level: int = 0
    depth: int = 0
    rows: tuple[tuple[str, ...], ...] | None = None
    image_src: str | None = None
    info: str | None = None


@dataclass(slots=True)
class MarkdownInlineSpan:
    text: str
    styles: frozenset[str] = frozenset()
    href: str | None = None


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_ORDERED_ITEM_RE = re.compile(r"^(\d+)\.\s*(.*)$")
_BULLET_ITEM_RE = re.compile(r"^[-*+]\s+(.*)$")
_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\((.+)\)$")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_HORIZONTAL_RULE_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
_MARKDOWN_TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$"
)
_INLINE_TOKEN_RE = re.compile(
    r"`([^`\n]+)`"
    r"|\*\*([^*\n]+?)\*\*"
    r"|\*([^*\n]+?)\*"
    r"|</?(?:u|del|s|strong|b|em|i)>"
)
_INLINE_TAG_STYLE_MAP = {
    "<u>": "underline",
    "</u>": "underline",
    "<del>": "strike",
    "</del>": "strike",
    "<s>": "strike",
    "</s>": "strike",
    "<strong>": "bold",
    "</strong>": "bold",
    "<b>": "bold",
    "</b>": "bold",
    "<em>": "italic",
    "</em>": "italic",
    "<i>": "italic",
    "</i>": "italic",
}


def _split_table_row(line: str) -> list[str]:
    normalized = line.strip()
    if normalized.startswith("|"):
        normalized = normalized[1:]
    if normalized.endswith("|"):
        normalized = normalized[:-1]

    cells: list[str] = []
    current: list[str] = []
    escape_next = False
    for char in normalized:
        if escape_next:
            current.append(char)
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)

    cells.append("".join(current).strip())
    return cells


def _collect_table_rows(
    lines: list[str], start_index: int
) -> tuple[list[list[str]], int] | None:
    if start_index + 1 >= len(lines):
        return None

    header_line = lines[start_index].strip()
    separator_line = lines[start_index + 1].strip()
    if "|" not in header_line or not _MARKDOWN_TABLE_SEPARATOR_RE.match(separator_line):
        return None

    rows: list[list[str]] = [_split_table_row(header_line)]
    index = start_index + 2
    while index < len(lines):
        candidate = lines[index].strip()
        if not candidate:
            break
        if "|" not in candidate:
            break
        if (
            _HEADING_RE.match(candidate)
            or _ORDERED_ITEM_RE.match(candidate)
            or _BULLET_ITEM_RE.match(candidate)
        ):
            break
        rows.append(_split_table_row(candidate))
        index += 1

    if not rows:
        return None

    return rows, index


def parse_markdown_blocks(content: str) -> list[MarkdownBlock]:
    blocks: list[MarkdownBlock] = []
    paragraph_lines: list[str] = []
    in_code_block = False
    code_lines: list[str] = []
    code_info: str | None = None

    def flush_paragraph() -> None:
        if paragraph_lines:
            blocks.append(
                MarkdownBlock(
                    kind="paragraph",
                    text="\n".join(paragraph_lines).strip(),
                )
            )
            paragraph_lines.clear()

    def flush_code_block() -> None:
        if code_lines:
            blocks.append(
                MarkdownBlock(
                    kind="code",
                    text="\n".join(code_lines).rstrip(),
                    info=code_info,
                )
            )
            code_lines.clear()

    lines = (content or "").splitlines()
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        stripped_line = raw_line.strip()

        if stripped_line.startswith("```"):
            flush_paragraph()
            if in_code_block:
                flush_code_block()
                in_code_block = False
                code_info = None
            else:
                in_code_block = True
                code_info = stripped_line[3:].strip() or None
            index += 1
            continue

        if in_code_block:
            code_lines.append(raw_line)
            index += 1
            continue

        if not stripped_line:
            flush_paragraph()
            index += 1
            continue

        if stripped_line.startswith(">"):
            flush_paragraph()
            quote_lines: list[str] = []
            while index < len(lines):
                quote_line = lines[index].strip()
                if not quote_line.startswith(">"):
                    break
                quote_lines.append(quote_line[1:].lstrip())
                index += 1
            blocks.append(
                MarkdownBlock(kind="blockquote", text="\n".join(quote_lines))
            )
            continue

        if _HORIZONTAL_RULE_RE.match(stripped_line.replace(" ", "")):
            flush_paragraph()
            blocks.append(MarkdownBlock(kind="horizontal_rule", text=""))
            index += 1
            continue

        table_rows = _collect_table_rows(lines, index)
        if table_rows is not None:
            flush_paragraph()
            rows, next_index = table_rows
            blocks.append(
                MarkdownBlock(
                    kind="table",
                    text="",
                    rows=tuple(tuple(cell for cell in row) for row in rows),
                )
            )
            index = next_index
            continue

        heading_match = _HEADING_RE.match(stripped_line)
        if heading_match:
            flush_paragraph()
            hashes, text = heading_match.groups()
            blocks.append(
                MarkdownBlock(
                    kind="heading",
                    text=text.strip(),
                    level=len(hashes),
                )
            )
            index += 1
            continue

        ordered_match = _ORDERED_ITEM_RE.match(stripped_line)
        if ordered_match:
            flush_paragraph()
            number, text = ordered_match.groups()
            indentation = len(raw_line.expandtabs(4)) - len(
                raw_line.expandtabs(4).lstrip()
            )
            blocks.append(
                MarkdownBlock(
                    kind="ordered_item",
                    text=text.strip(),
                    level=int(number),
                    depth=indentation // 2,
                )
            )
            index += 1
            continue

        bullet_match = _BULLET_ITEM_RE.match(stripped_line)
        if bullet_match:
            flush_paragraph()
            indentation = len(raw_line.expandtabs(4)) - len(
                raw_line.expandtabs(4).lstrip()
            )
            blocks.append(
                MarkdownBlock(
                    kind="bullet_item",
                    text=bullet_match.group(1).strip(),
                    depth=indentation // 2,
                )
            )
            index += 1
            continue

        image_match = _IMAGE_RE.match(stripped_line)
        if image_match:
            flush_paragraph()
            alt_text, image_src = image_match.groups()
            blocks.append(
                MarkdownBlock(
                    kind="image",
                    text=alt_text.strip(),
                    image_src=image_src.strip(),
                )
            )
            index += 1
            continue

        paragraph_lines.append(raw_line)
        index += 1

    flush_paragraph()
    flush_code_block()
    return blocks


def parse_plain_text_blocks(content: str) -> list[MarkdownBlock]:
    return [
        MarkdownBlock(kind="paragraph", text=part.strip())
        for part in re.split(r"\n\s*\n", content or "")
        if part.strip()
    ]


def parse_markdown_inlines(text: str) -> list[MarkdownInlineSpan]:
    spans: list[MarkdownInlineSpan] = []
    source = text or ""
    active_styles: list[str] = []
    buffer: list[str] = []
    index = 0
    code_active = False

    tag_tokens = sorted(_INLINE_TAG_STYLE_MAP.keys(), key=len, reverse=True)

    def current_styles() -> frozenset[str]:
        return frozenset({"code"}) if code_active else frozenset(active_styles)

    def push_style(style: str) -> None:
        if style in active_styles:
            active_styles.remove(style)
        else:
            active_styles.append(style)

    def flush_buffer() -> None:
        if buffer:
            spans.append(
                MarkdownInlineSpan(
                    text="".join(buffer),
                    styles=current_styles(),
                )
            )
            buffer.clear()

    while index < len(source):
        if code_active:
            next_backtick = source.find("`", index)
            if next_backtick == -1:
                buffer.append(source[index:])
                index = len(source)
                break
            buffer.append(source[index:next_backtick])
            flush_buffer()
            code_active = False
            index = next_backtick + 1
            continue

        if source.startswith("~~", index):
            flush_buffer()
            push_style("strike")
            index += 2
            continue

        if source.startswith("**", index):
            flush_buffer()
            push_style("bold")
            index += 2
            continue

        if source[index] == "*":
            flush_buffer()
            push_style("italic")
            index += 1
            continue

        if source[index] == "`":
            flush_buffer()
            code_active = True
            index += 1
            continue

        link_match = _LINK_RE.match(source, index)
        if link_match:
            flush_buffer()
            label, href = link_match.groups()
            spans.append(
                MarkdownInlineSpan(
                    text=label,
                    styles=current_styles(),
                    href=href,
                )
            )
            index = link_match.end()
            continue

        matched_tag = None
        for token in tag_tokens:
            if source.startswith(token, index):
                matched_tag = token
                break
        if matched_tag is not None:
            flush_buffer()
            push_style(_INLINE_TAG_STYLE_MAP[matched_tag])
            index += len(matched_tag)
            continue

        buffer.append(source[index])
        index += 1

    flush_buffer()
    return spans


def render_markdown_inlines_as_text(text: str) -> str:
    fragments: list[str] = []
    for span in parse_markdown_inlines(text):
        fragments.append(span.text)
        if span.href and span.href != span.text:
            fragments.append(f" ({span.href})")
    return "".join(fragments)


def render_markdown_as_text(content: str) -> str:
    sections: list[str] = []

    for block in parse_markdown_blocks(content):
        if block.kind in {"heading", "paragraph"}:
            sections.append(render_markdown_inlines_as_text(block.text))
            continue
        if block.kind == "bullet_item":
            indent = "  " * block.depth
            sections.append(
                f"{indent}• {render_markdown_inlines_as_text(block.text)}"
            )
            continue
        if block.kind == "ordered_item":
            indent = "  " * block.depth
            sections.append(
                f"{indent}{block.level}. "
                f"{render_markdown_inlines_as_text(block.text)}"
            )
            continue
        if block.kind == "blockquote":
            quote = render_markdown_inlines_as_text(block.text)
            sections.append("\n".join(f"  {line}" for line in quote.splitlines()))
            continue
        if block.kind == "horizontal_rule":
            sections.append("-" * 40)
            continue
        if block.kind == "code":
            sections.append(block.text)
            continue
        if block.kind == "image":
            image_text = block.text or block.image_src or ""
            if (
                block.text
                and block.image_src
                and not block.image_src.startswith("data:")
            ):
                image_text = f"{block.text} ({block.image_src})"
            sections.append(image_text)
            continue
        if block.kind == "table" and block.rows:
            rows = [
                "\t".join(render_markdown_inlines_as_text(cell) for cell in row)
                for row in block.rows
            ]
            sections.append("\n".join(rows))

    return "\n\n".join(section for section in sections if section)


def render_markdown_inlines_as_html(text: str) -> str:
    fragments: list[str] = []
    for span in parse_markdown_inlines(text):
        escaped_text = escape(span.text)
        wrapped = escaped_text
        if "code" in span.styles:
            wrapped = f"<code>{wrapped}</code>"
        else:
            if "strike" in span.styles:
                wrapped = f"<del>{wrapped}</del>"
            if "underline" in span.styles:
                wrapped = f"<u>{wrapped}</u>"
            if "italic" in span.styles:
                wrapped = f"<em>{wrapped}</em>"
            if "bold" in span.styles:
                wrapped = f"<strong>{wrapped}</strong>"
        if span.href:
            wrapped = f'<a href="{escape(span.href, quote=True)}">{wrapped}</a>'
        fragments.append(wrapped)
    return "".join(fragments)


def render_markdown_inlines_as_reportlab(text: str) -> str:
    fragments: list[str] = []
    for span in parse_markdown_inlines(text):
        escaped_text = escape(span.text)
        wrapped = escaped_text
        if "code" in span.styles:
            wrapped = f'<font face="Courier">{wrapped}</font>'
        else:
            if "strike" in span.styles:
                wrapped = f"<strike>{wrapped}</strike>"
            if "underline" in span.styles:
                wrapped = f"<u>{wrapped}</u>"
            if "italic" in span.styles:
                wrapped = f"<i>{wrapped}</i>"
            if "bold" in span.styles:
                wrapped = f"<b>{wrapped}</b>"
        if span.href:
            wrapped = (
                f'<a href="{escape(span.href, quote=True)}" color="blue">'
                f"{wrapped}</a>"
            )
        fragments.append(wrapped)
    return "".join(fragments)
