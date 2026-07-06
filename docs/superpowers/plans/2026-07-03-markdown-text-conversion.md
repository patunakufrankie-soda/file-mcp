# Markdown and Text Conversion Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make TXT/Markdown file conversion truthful and semantic, then improve common business-document structure in generated PDF and DOCX files.

**Architecture:** Extend the existing Markdown block/inline model as the shared semantic boundary. Keep TXT parsing separate so plain text is never interpreted as Markdown, and make TXT, PDF, and DOCX renderers consume explicit source semantics.

**Tech Stack:** Python 3.12+, unittest/pytest, ReportLab, python-docx, existing conversion router and generators.

---

## File Structure

- Modify `format_export_mcp/utils/markdown_blocks.py`: shared Markdown and plain-text block models, inline links, and semantic TXT rendering.
- Modify `format_export_mcp/conversion/router.py`: expose the missing TXT to MD route.
- Modify `format_export_mcp/conversion/engines/markdown_engine.py`: dispatch TXT and Markdown sources without conflating their syntax.
- Modify `format_export_mcp/export/generators/pdf_generator.py`: render the expanded block model to PDF.
- Modify `format_export_mcp/export/generators/docx_generator.py`: render the expanded block model to DOCX.
- Modify `format_export_mcp/conversion/conversion_matrix.py`: keep public claims aligned with actual routes.
- Modify `tests/test_export_document_formats.py`: unit and integration regression coverage.

### Task 1: Restore truthful TXT/Markdown conversion

**Files:**
- Modify: `tests/test_export_document_formats.py`
- Modify: `format_export_mcp/conversion/router.py`
- Modify: `format_export_mcp/conversion/engines/markdown_engine.py`
- Modify: `format_export_mcp/utils/markdown_blocks.py`

- [ ] **Step 1: Add failing route and semantic TXT tests**

Add tests that require:

```python
def test_convert_file_document_local_txt_to_md(self) -> None:
    source.write_text("# literal heading\n- literal item", encoding="utf-8")
    result = convert_file_document(str(source), "md")
    assert result["success"]
    assert Path(result["output_path"]).read_text() == source.read_text()

def test_convert_file_document_local_md_to_txt(self) -> None:
    source.write_text("# 标题\n\n- **条目**\n\n| A | B |...", encoding="utf-8")
    result = convert_file_document(str(source), "txt")
    output = Path(result["output_path"]).read_text()
    assert "# " not in output
    assert "**" not in output
    assert "A\tB" in output
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
uv run --extra dev python -m pytest -q tests/test_export_document_formats.py \
  -k 'local_txt_to_md or local_md_to_txt'
```

Expected: TXT to MD fails with no route, and MD to TXT leaks Markdown syntax.

- [ ] **Step 3: Add explicit plain-text parsing and rendering APIs**

In `markdown_blocks.py`, add:

```python
def parse_plain_text_blocks(content: str) -> list[MarkdownBlock]:
    return [
        MarkdownBlock(kind="paragraph", text=part.strip())
        for part in re.split(r"\n\s*\n", content or "")
        if part.strip()
    ]

def render_markdown_as_text(content: str) -> str:
    blocks = parse_markdown_blocks(content)
    # Render headings as text, lists with readable indentation,
    # tables as TSV, code without fences, and inline spans without markup.
```

- [ ] **Step 4: Route TXT to MD and dispatch by source semantics**

Add `md` to the TXT route. In `MarkdownEngine.convert`, copy TXT to MD
directly, call `render_markdown_as_text` for MD to TXT, and pass
`input_format="txt"` to PDF/DOCX generators for TXT sources.

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run the Task 1 command. Expected: both conversions pass without syntax leaks.

### Task 2: Expand the shared Markdown semantic model

**Files:**
- Modify: `tests/test_export_document_formats.py`
- Modify: `format_export_mcp/utils/markdown_blocks.py`

- [ ] **Step 1: Add failing parser tests**

Cover this input:

```markdown
## Heading

- parent
  - child
1. first

> quoted **text**

[OpenAI](https://openai.com)  
next line

---
```

Assert heading level, list kind/number/depth, quote, link target, explicit line
break, and horizontal-rule blocks.

- [ ] **Step 2: Run parser tests and verify RED**

Run:

```bash
uv run --extra dev python -m pytest -q tests/test_export_document_formats.py \
  -k 'markdown_parser or markdown_plain_text'
```

Expected: missing depth, quote, link, line-break, and rule semantics.

- [ ] **Step 3: Extend block and inline models**

Use compatible defaults:

```python
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
```

Parse list indentation before stripping input, collect contiguous blockquote
lines, recognize horizontal rules, retain fenced-code language in `info`, and
recognize `[label](URL)` inline links.

- [ ] **Step 4: Complete semantic plain-text rendering**

Render inline styles as plain text, links as `label (URL)`, tables as TSV,
quotes with indentation, nested lists with two spaces per depth, code without
fences, and rules as `----------------------------------------`.

- [ ] **Step 5: Run parser and TXT tests and verify GREEN**

Run the Task 2 command plus Task 1 tests. Expected: all pass.

### Task 3: Improve PDF and DOCX output

**Files:**
- Modify: `tests/test_export_document_formats.py`
- Modify: `format_export_mcp/export/generators/pdf_generator.py`
- Modify: `format_export_mcp/export/generators/docx_generator.py`
- Modify: `format_export_mcp/conversion/engines/markdown_engine.py`

- [ ] **Step 1: Add failing PDF/DOCX integration tests**

Generate both formats from content containing a matching first heading,
heading level 5, nested lists, quote, link, code, table, and rule. Assert:

```python
assert document_xml.count("业务报告") == 1
assert 'w:pStyle w:val="Heading5"' in document_xml
assert "https://example.com" in relationships_xml
assert "w:pBdr" in document_xml
assert nested_item_has_indentation
```

For PDF, inspect decoded streams and PDF bytes for one title, content order,
link annotation, quote/list text, and rule drawing.

- [ ] **Step 2: Verify the integration tests fail**

Run:

```bash
uv run --extra dev python -m pytest -q tests/test_export_document_formats.py \
  -k 'enhanced_markdown_pdf or enhanced_markdown_docx or plain_txt_is_literal'
```

Expected: duplicate title and missing enhanced structure.

- [ ] **Step 3: Enhance PDF rendering**

Accept `input_format: str = "md"`, select `parse_plain_text_blocks` for TXT,
add heading styles 5 and 6, list indentation, quote style, `HRFlowable`,
line-break rendering, and ReportLab hyperlink markup. Skip the first heading
only when it exactly matches the document title.

- [ ] **Step 4: Enhance DOCX rendering**

Accept `input_format: str = "md"`, use plain-text blocks for TXT, add heading
levels 5 and 6, list indentation via paragraph formatting, quote styling,
OOXML hyperlinks, paragraph bottom borders for rules, repeated table headers,
and title deduplication.

- [ ] **Step 5: Verify PDF/DOCX tests pass**

Run the Task 3 command. Expected: all enhanced generation tests pass.

### Task 4: Align public claims and run regression verification

**Files:**
- Modify: `tests/test_export_document_formats.py`
- Modify: `format_export_mcp/conversion/conversion_matrix.py`

- [ ] **Step 1: Add a matrix-to-router consistency test**

For every pair in `SUPPORTED_CONVERSIONS`, assert that
`ConversionRouter.get_route(source, target, DocumentFeatures())` returns a
route. Also assert no same-format pair is advertised.

- [ ] **Step 2: Run the consistency test and verify its initial result**

Run:

```bash
uv run --extra dev python -m pytest -q tests/test_export_document_formats.py \
  -k 'supported_conversions'
```

Expected before route fixes: TXT to MD exposes the drift. Expected after Task
1: the consistency assertion passes.

- [ ] **Step 3: Update notes to match real engines**

State that DOCX to PDF requires LibreOffice, PDF to DOCX is editable
reconstruction with optional `pdf2docx`, and scanned PDF requires OCR.

- [ ] **Step 4: Run focused and regression verification**

Run:

```bash
uv run --extra dev python -m pytest -q tests/test_export_document_formats.py \
  -k 'txt_to_md or md_to_txt or markdown_parser or enhanced_markdown or docx_to_txt or docx_to_md or supported_conversions'
python3 -m py_compile \
  format_export_mcp/utils/markdown_blocks.py \
  format_export_mcp/conversion/engines/markdown_engine.py \
  format_export_mcp/export/generators/pdf_generator.py \
  format_export_mcp/export/generators/docx_generator.py
git diff --check
```

Expected: focused tests pass, compilation exits zero, and diff check is clean.

- [ ] **Step 5: Review final scope**

Confirm every item in the design specification has either an implementation
and test or is explicitly listed as out of scope. Report unrelated pre-existing
full-suite failures separately rather than describing the whole suite as green.
