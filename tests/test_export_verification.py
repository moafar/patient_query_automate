import tempfile
import unittest
import zipfile
from pathlib import Path

from export_verification import ExportVerificationError, wait_for_export_file


class ExportVerificationTests(unittest.TestCase):
    def test_accepts_non_empty_stable_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = Path(temp_dir) / "export.xls"

            with zipfile.ZipFile(export_path, "w") as workbook:
                workbook.writestr(
                    "[Content_Types].xml",
                    '<?xml version="1.0" encoding="UTF-8"?>',
                )
                workbook.writestr(
                    "xl/workbook.xml",
                    '<?xml version="1.0" encoding="UTF-8"?>',
                )

            size = wait_for_export_file(
                export_path,
                timeout=1,
                poll_interval=0.01,
                stable_checks=1,
            )

            self.assertEqual(size, export_path.stat().st_size)
            
    def test_rejects_missing_file_after_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missing.xls"

            with self.assertRaises(ExportVerificationError):
                wait_for_export_file(
                    path,
                    timeout=0.08,
                    poll_interval=0.02,
                    stable_checks=1,
                )

    def test_rejects_empty_file_after_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "empty.xls"
            path.touch()

            with self.assertRaises(ExportVerificationError):
                wait_for_export_file(
                    path,
                    timeout=0.08,
                    poll_interval=0.02,
                    stable_checks=1,
                )


if __name__ == "__main__":
    unittest.main()
