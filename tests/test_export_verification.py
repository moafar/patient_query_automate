import tempfile
import threading
import time
import unittest
from pathlib import Path

from export_verification import ExportVerificationError, wait_for_export_file


class ExportVerificationTests(unittest.TestCase):
    def test_accepts_non_empty_stable_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "export.xls"

            def write_file():
                time.sleep(0.03)
                path.write_bytes(b"valid-content")

            writer = threading.Thread(target=write_file)
            writer.start()
            size = wait_for_export_file(
                path,
                timeout=1,
                poll_interval=0.02,
                stable_checks=2,
            )
            writer.join()

            self.assertEqual(size, len(b"valid-content"))

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
