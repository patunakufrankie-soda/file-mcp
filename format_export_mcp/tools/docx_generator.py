from __future__ import annotations

from pathlib import Path

def generate_docx(title: str, content: str, output_path: Path) -> None:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Pt

    def _set_east_asia_font(run, font_name: str) -> None:
        run.font.name = font_name
        run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)

    document = Document()
    document.core_properties.title = title or "Export"

    heading = document.add_heading(level=1)
    heading_run = heading.add_run(title or "Export")
    _set_east_asia_font(heading_run, "Microsoft YaHei")
    heading_run.font.size = Pt(18)

    for block in (content or "").splitlines() or [""]:
        paragraph = document.add_paragraph()
        run = paragraph.add_run(block)
        _set_east_asia_font(run, "Microsoft YaHei")
        run.font.size = Pt(11)

    document.save(output_path)
