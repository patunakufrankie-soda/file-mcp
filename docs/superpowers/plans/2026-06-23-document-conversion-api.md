# Document Conversion API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated document-to-document HTTP and MCP interface for the three stable conversion classes: `markdown/text -> pdf/docx` and `csv -> xlsx`.

**Architecture:** Keep the existing `export_document` path unchanged for general text export. Add a new conversion entrypoint that validates source and target formats up front, routes to the right existing generator, and rejects unsupported pairs with structured errors. Reuse the current storage, naming, logging, readiness, and CORS infrastructure so the new endpoint behaves like the rest of the service.

**Tech Stack:** Python 3.12, FastMCP, Starlette, ReportLab, python-docx, stdlib `csv`, existing storage helpers, `unittest`.

---

### Task 1: Define the conversion contract and failing API tests

**Files:**
- Modify: `tests/test_export_document_formats.py`
- Modify: `format_export_mcp/server_common.py`

- [ ] **Step 1: Write the failing test**

```python
def test_convert_document_api_accepts_markdown_to_pdf():
    response = request_asgi(
        app,
        "POST",
        "/api/convert_document",
        json={
            "title": "市场分析",
            "source_format": "markdown",
            "target_format": "pdf",
            "content": "# Title\n\n1.**数字化转型加速**：内容",
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["file_name"].endswith(".pdf")


def test_convert_document_api_rejects_unsupported_pair():
    response = request_asgi(
        app,
        "POST",
        "/api/convert_document",
        json={
            "title": "表格",
            "source_format": "csv",
            "target_format": "pdf",
            "content": "a,b\n1,2",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m unittest tests.test_export_document_formats.ExportDocumentFormatTests.test_convert_document_api_accepts_markdown_to_pdf tests.test_export_document_formats.ExportDocumentFormatTests.test_convert_document_api_rejects_unsupported_pair
```

Expected: `404` or `AttributeError` because `/api/convert_document` does not exist yet.

- [ ] **Step 3: Stop here until the route shape is confirmed**

Assume the request body contract for this new endpoint is:

```json
{
  "title": "string",
  "source_format": "markdown | text | csv",
  "target_format": "pdf | docx | xlsx",
  "content": "string"
}
```

This task is complete once the failure is reproduced and the contract is locked in.

### Task 2: Implement the document conversion dispatcher

**Files:**
- Create: `format_export_mcp/tools/document_convert.py`
- Modify: `format_export_mcp/server_common.py`

- [ ] **Step 1: Write the failing unit test for conversion routing**

```python
def test_document_convert_dispatches_markdown_to_pdf():
    result = convert_document(
        title="市场分析",
        source_format="markdown",
        target_format="pdf",
        content="# Title\n\n1.**数字化转型加速**：内容",
    )
    assert result["success"] is True
    assert result["file_name"].endswith(".pdf")


def test_document_convert_dispatches_csv_to_xlsx():
    result = convert_document(
        title="人员表",
        source_format="csv",
        target_format="xlsx",
        content="姓名,部门\n张三,研发",
    )
    assert result["success"] is True
    assert result["file_name"].endswith(".xlsx")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m unittest tests.test_export_document_formats.ExportDocumentFormatTests.test_document_convert_dispatches_markdown_to_pdf tests.test_export_document_formats.ExportDocumentFormatTests.test_document_convert_dispatches_csv_to_xlsx
```

Expected: import or attribute failure because `convert_document` does not exist yet.

- [ ] **Step 3: Add the minimal conversion dispatcher**

Create `format_export_mcp/tools/document_convert.py` with a single public function that:

```python
def convert_document(title: str, source_format: str, target_format: str, content: str) -> dict[str, str]:
    ...
```

Rules:
- `source_format` accepts `markdown`, `md`, `text`, `txt`, `csv`
- `target_format` accepts `pdf`, `docx`, `xlsx`
- allow only these pairs:
  - `markdown`/`md`/`text`/`txt` -> `pdf`
  - `markdown`/`md`/`text`/`txt` -> `docx`
  - `csv` -> `xlsx`
- reject everything else with `ValueError("Unsupported conversion: ...")`
- reuse `build_output_path`, `store_export_file`, and `build_file_url`
- call the existing generators under `pdf_generator`, `docx_generator`, and `xlsx_generator`

- [ ] **Step 4: Wire the new HTTP route and MCP tool**

Add:
- MCP tool name: `convert_document`
- HTTP route: `POST /api/convert_document`

Request parsing:
- `title`: required string
- `source_format`: required string
- `target_format`: required string
- `content`: required string

Response shape:

```json
{
  "success": true,
  "file_name": "市场分析-xxxx.pdf",
  "file_url": "/downloads/市场分析-xxxx.pdf"
}
```

- [ ] **Step 5: Run the new tests and the existing export tests**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m unittest tests.test_export_document_formats
```

Expected: all tests pass.

### Task 3: Update docs and frontend guidance

**Files:**
- Modify: `format_export_mcp/README.md`
- Modify: `docs/frontend-integration.md`
- Modify: `docs/docker-deployment.md`

- [ ] **Step 1: Add the new endpoint contract**

Document that:
- `/api/export_document` remains the general text export endpoint
- `/api/convert_document` is for the three conversion classes only
- no file upload is supported
- unsupported pairs return structured `invalid_request`

- [ ] **Step 2: Add examples**

Examples to include:

```json
{
  "title": "市场分析",
  "source_format": "markdown",
  "target_format": "pdf",
  "content": "# Title\n\n1.**数字化转型加速**：内容"
}
```

```json
{
  "title": "人员表",
  "source_format": "csv",
  "target_format": "xlsx",
  "content": "姓名,部门\n张三,研发"
}
```

- [ ] **Step 3: Run a final smoke test**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m unittest tests.test_export_document_formats
```

Expected: green.
