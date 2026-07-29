import logging
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from logging_config import sanitize_filename, setup_logging


class LoggingConfigTests(unittest.TestCase):
    def test_creates_one_timestamped_log_per_execution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context = setup_logging(
                "observatorio_dlco",
                log_dir=Path(temp_dir),
                now=datetime(2026, 7, 29, 0, 6, 5),
            )

            try:
                context.logger.info("mensaje de prueba", extra={"phase": "test"})

                self.assertEqual(
                    context.log_path.name,
                    "observatorio_dlco_20260729_000605.log",
                )
                self.assertTrue(context.log_path.is_file())
                content = context.log_path.read_text(encoding="utf-8")
                self.assertIn("run_id=20260729T000605", content)
                self.assertIn("extractor=observatorio_dlco", content)
                self.assertIn("phase=test", content)
                self.assertIn("mensaje de prueba", content)
            finally:
                handlers = list(context.logger.handlers)
                for handler in handlers:
                    context.logger.removeHandler(handler)
                    handler.close()
                logging.shutdown()

    def test_sanitizes_unsafe_extractor_name(self):
        self.assertEqual(sanitize_filename("observatorio/dlco"), "observatorio_dlco")


if __name__ == "__main__":
    unittest.main()
