# Markdown and Text Conversion Enhancement

## Goal

Make the public `convert_file_document` matrix truthful for TXT and Markdown
inputs, and improve PDF/DOCX output for common business documents without
adding Pandoc or another runtime dependency.

## Supported Scope

Markdown conversion will support:

- headings levels 1 through 6;
- paragraphs and explicit line breaks;
- nested ordered and unordered lists;
- block quotes;
- fenced code blocks and inline code;
- tables;
- links and standalone images;
- horizontal rules;
- bold, italic, underline, strikethrough, and inline code.

Mathematical formulas, footnotes, generated tables of contents, complex raw
HTML, and pixel-perfect layout are outside this change.

## Architecture

The existing Markdown parser remains the single parsing boundary. Its block
and inline models will be extended only where needed for the supported scope.
All target renderers consume those models rather than independently
interpreting Markdown syntax.

Plain TXT input will use a separate plain-text block parser. This prevents
lines beginning with Markdown punctuation such as `#` or `-` from being
silently converted into headings or lists.

The conversion engine will dispatch according to the source format:

- TXT to MD copies normalized plain text without interpreting Markdown.
- TXT to PDF/DOCX renders plain-text paragraphs and line breaks.
- MD to TXT uses a semantic plain-text renderer.
- MD to PDF/DOCX uses the shared Markdown block and inline models.

## Plain-Text Rendering

Markdown to TXT removes presentation syntax while retaining meaning:

- headings become plain heading text;
- unordered lists use a readable bullet and retain nesting indentation;
- ordered lists retain their source number and nesting indentation;
- tables become tab-separated rows;
- links become `label (URL)`, unless label and URL are identical;
- images become their alternative text followed by the source when useful;
- fenced code retains code contents but drops fences and language markers;
- block quotes retain text with indentation;
- horizontal rules become a stable plain-text separator.

## PDF and DOCX Rendering

Both generators will use equivalent semantics:

- six distinct heading levels with bounded font sizes;
- nested list indentation and stable numbering/bullets;
- visibly separated block quotes;
- monospaced code blocks with preserved whitespace;
- first-row table styling and repeat-header behavior where supported;
- clickable links;
- images at their document position;
- horizontal rules;
- no duplicate document title when the first Markdown heading matches the
  supplied title.

PDF and DOCX do not need pixel-identical output, but content order and
structure must agree.

## Routing and Public Matrix

The router will expose TXT to MD. The public supported-conversions matrix must
be generated from, or tested against, the actual public routes for TXT, MD,
PDF, and DOCX so that declared support cannot drift silently.

Same-format conversions remain outside the advertised matrix.

## Error Handling

Existing structured conversion failures remain unchanged. Missing image
sources and generator dependency failures must return conversion failure
rather than a false success. Unsupported Markdown features degrade to readable
text instead of being dropped.

## Testing

Development follows red-green-refactor:

1. Add failing route tests for TXT to MD.
2. Add failing semantic rendering tests for MD to TXT.
3. Add parser tests for nesting, quotes, links, line breaks, and rules.
4. Add PDF and DOCX integration tests for the supported structures.
5. Verify plain TXT does not get interpreted as Markdown.
6. Run the focused conversion tests, the document-format test module where
   environment dependencies permit, syntax checks, and diff checks.

Success means the advertised TXT/MD conversion routes work, Markdown syntax is
not leaked into TXT output, common document structure survives PDF/DOCX
generation, and existing DOCX extraction behavior remains green.
