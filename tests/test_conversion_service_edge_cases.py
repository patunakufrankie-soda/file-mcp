from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from format_export_mcp.conversion.services.conversion_service import ConversionService


class ConversionServiceEdgeCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_reports_missing_pdf_input_as_failure(self) -> None:
        service = ConversionService()
        missing_pdf = Path(self._tmpdir.name) / "missing.pdf"
        output_path = Path(self._tmpdir.name) / "missing.txt"

        result = service.convert(missing_pdf, "txt", output_path=output_path)

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)
        self.assertIn("failed", result.error_message.lower())
        self.assertFalse(output_path.exists())

    def test_reports_unsupported_conversion_route(self) -> None:
        service = ConversionService()
        source_path = Path(self._tmpdir.name) / "sample.jpg"
        source_path.write_bytes(b"not really an image")

        result = service.convert(source_path, "pdf")

        self.assertFalse(result.success)
        self.assertEqual(
            result.error_message,
            "No conversion route for jpg -> pdf",
        )


if __name__ == "__main__":
    unittest.main()
