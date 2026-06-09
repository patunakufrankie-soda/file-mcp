from __future__ import annotations

from pathlib import Path


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def generate_xls(title: str, content: str, output_path: Path) -> None:
    rows = (content or "").splitlines() or [""]
    row_xml_parts: list[str] = []

    for line in rows:
        cells = line.split(",")
        cell_xml_parts: list[str] = []
        for cell in cells:
            cell_xml_parts.append(
                f"<Cell><Data ss:Type=\"String\">{_escape_xml(cell)}</Data></Cell>"
            )
        row_xml_parts.append(f"<Row>{''.join(cell_xml_parts)}</Row>")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
          xmlns:o="urn:schemas-microsoft-com:office:office"
          xmlns:x="urn:schemas-microsoft-com:office:excel"
          xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
          xmlns:html="http://www.w3.org/TR/REC-html40">
  <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
    <Title>{_escape_xml(title or "Export")}</Title>
  </DocumentProperties>
  <Worksheet ss:Name="Sheet1">
    <Table>
      {''.join(row_xml_parts)}
    </Table>
  </Worksheet>
</Workbook>
"""
    output_path.write_text(xml, encoding="utf-8")

