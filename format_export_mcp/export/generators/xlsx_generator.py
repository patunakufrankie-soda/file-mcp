from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from ...utils.markdown_blocks import parse_markdown_inlines
from ...utils.tabular import parse_delimited_rows


def _cell_reference(row_index: int, col_index: int) -> str:
    letters = ""
    n = col_index + 1
    while n:
        n, remainder = divmod(n - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{row_index + 1}"


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _escape_xml_text(text: str) -> str:
    return _escape_xml(text).replace("\n", "&#10;")


def _run_xml(text: str, styles: frozenset[str]) -> str:
    properties: list[str] = []
    if "bold" in styles:
        properties.append("<b/>")
    if "italic" in styles:
        properties.append("<i/>")
    if "underline" in styles:
        properties.append('<u val="single"/>')
    if "strike" in styles:
        properties.append("<strike/>")
    if "code" in styles:
        properties.append('<rFont val="Courier New"/>')

    properties_xml = f"<rPr>{''.join(properties)}</rPr>" if properties else ""
    return (
        f'<r>{properties_xml}<t xml:space="preserve">{_escape_xml_text(text)}</t></r>'
    )


def _inline_string_xml(text: str, force_bold: bool = False) -> str:
    spans = parse_markdown_inlines(text)
    if not spans:
        return "<is><t></t></is>"

    if len(spans) == 1 and not spans[0].styles and not force_bold:
        return f'<is><t xml:space="preserve">{_escape_xml_text(spans[0].text)}</t></is>'

    runs: list[str] = []
    for span in spans:
        styles = set(span.styles)
        if force_bold:
            styles.add("bold")
        runs.append(_run_xml(span.text, frozenset(styles)))
    return f"<is>{''.join(runs)}</is>"


def _sheet_xml(content: str) -> str:
    rows = parse_delimited_rows(content)
    xml_rows: list[str] = []
    for row_index, cells in enumerate(rows):
        xml_cells: list[str] = []
        for col_index, cell in enumerate(cells):
            ref = _cell_reference(row_index, col_index)
            xml_cells.append(
                f'<c r="{ref}" t="inlineStr">{_inline_string_xml(cell, force_bold=row_index == 0)}</c>'
            )
        xml_rows.append(f'<row r="{row_index + 1}">{"".join(xml_cells)}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(xml_rows)}</sheetData>"
        "</worksheet>"
    )


def generate_xlsx(title: str, content: str, output_path: Path) -> None:
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    sheet_xml = _sheet_xml(content)

    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", root_rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
