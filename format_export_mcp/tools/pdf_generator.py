from __future__ import annotations

from pathlib import Path

from .image_sources import load_image_assets
from .markdown_blocks import parse_markdown_blocks, render_markdown_inlines_as_reportlab


def generate_pdf(title: str, content: str, output_path: Path, images: list[str] | None = None) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

    font_name = "STSong-Light"

    def _register_font() -> None:
        try:
            pdfmetrics.getFont(font_name)
        except KeyError:
            pdfmetrics.registerFont(UnicodeCIDFont(font_name))

    _register_font()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ChineseTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=20,
        leading=28,
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "ChineseBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=11,
        leading=18,
        spaceAfter=8,
    )
    code_style = ParagraphStyle(
        "CodeBody",
        parent=body_style,
        fontName="Courier",
        fontSize=9,
        leading=14,
        leftIndent=8 * mm,
        backColor=colors.HexColor("#f3f4f6"),
        borderPadding=6,
        spaceBefore=2,
        spaceAfter=8,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title or "Export",
    )

    story = [Paragraph(render_markdown_inlines_as_reportlab(title or "Export"), title_style), Spacer(1, 6 * mm)]
    heading_styles = {
        1: ParagraphStyle("Heading1", parent=body_style, fontName=font_name, fontSize=18, leading=24, spaceBefore=6, spaceAfter=8),
        2: ParagraphStyle("Heading2", parent=body_style, fontName=font_name, fontSize=16, leading=22, spaceBefore=6, spaceAfter=8),
        3: ParagraphStyle("Heading3", parent=body_style, fontName=font_name, fontSize=14, leading=20, spaceBefore=4, spaceAfter=6),
        4: ParagraphStyle("Heading4", parent=body_style, fontName=font_name, fontSize=13, leading=18, spaceBefore=4, spaceAfter=6),
    }

    def _build_image_story(image_ref: str) -> list:
        image_asset = load_image_assets([image_ref])[0]
        image_buffer = image_asset.open_bytes()
        image_reader = ImageReader(image_buffer)
        image_width, image_height = image_reader.getSize()
        target_width = 170 * mm
        target_height = target_width * image_height / image_width
        return [Spacer(1, 4 * mm), Image(image_buffer, width=target_width, height=target_height)]

    for block in parse_markdown_blocks(content or "") or [None]:
        if block is None:
            story.append(Paragraph("", body_style))
            continue

        if block.kind == "heading":
            story.append(Paragraph(render_markdown_inlines_as_reportlab(block.text), heading_styles[min(block.level, 4)]))
            continue

        if block.kind == "bullet_item":
            story.append(Paragraph(f"• {render_markdown_inlines_as_reportlab(block.text)}", body_style))
            continue

        if block.kind == "ordered_item":
            story.append(Paragraph(f"{block.level}. {render_markdown_inlines_as_reportlab(block.text)}", body_style))
            continue

        if block.kind == "code":
            story.append(Preformatted(block.text, code_style))
            continue

        if block.kind == "image" and block.image_src:
            story.extend(_build_image_story(block.image_src))
            continue

        if block.kind == "table" and block.rows:
            table_data = [
                [Paragraph(render_markdown_inlines_as_reportlab(cell), body_style) for cell in row]
                for row in block.rows
            ]
            table = Table(table_data, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 6 * mm))
            continue

        story.append(Paragraph(render_markdown_inlines_as_reportlab(block.text), body_style))

    for image_asset in load_image_assets(list(images or [])):
        image_buffer = image_asset.open_bytes()
        image_reader = ImageReader(image_buffer)
        image_width, image_height = image_reader.getSize()
        target_width = 170 * mm
        target_height = target_width * image_height / image_width
        story.append(Spacer(1, 4 * mm))
        story.append(Image(image_buffer, width=target_width, height=target_height))

    doc.build(story)
