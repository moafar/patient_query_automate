import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


try:
    import dotenv  # noqa: F401
except ModuleNotFoundError:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = MagicMock()
    sys.modules["dotenv"] = dotenv_stub


try:
    import pywinauto  # noqa: F401
except ModuleNotFoundError:
    pywinauto_stub = types.ModuleType("pywinauto")
    pywinauto_stub.Desktop = MagicMock()
    keyboard_stub = types.ModuleType("pywinauto.keyboard")
    keyboard_stub.send_keys = MagicMock()
    sys.modules["pywinauto"] = pywinauto_stub
    sys.modules["pywinauto.keyboard"] = keyboard_stub


from main import deliver_export


class DeliverExportTests(unittest.TestCase):
    @patch("main.transfer_and_load_gx")
    @patch("main.load_gx_remote_config")
    def test_gx_export_is_transferred_and_loaded(
        self,
        load_config,
        transfer_and_load,
    ):
        logger = MagicMock()
        exported_path = Path(r"C:\exports\GX INO_15082026_013000.xls")
        config = MagicMock()
        result = MagicMock(stdout='{"status":"loaded"}')
        load_config.return_value = config
        transfer_and_load.return_value = result

        returned = deliver_export("gx_ino", exported_path, logger)

        self.assertIs(returned, result)
        load_config.assert_called_once_with(logger)
        transfer_and_load.assert_called_once_with(
            exported_path,
            config,
            logger,
        )
        self.assertEqual(
            logger.info.call_args.kwargs["extra"]["phase"],
            "remote_result",
        )

    @patch("main.transfer_and_load_gx")
    @patch("main.load_gx_remote_config")
    def test_other_extractors_are_not_transferred(
        self,
        load_config,
        transfer_and_load,
    ):
        result = deliver_export(
            "observatorio_dlco",
            Path(r"C:\exports\OBSERVATORIO-DLCO.xls"),
            MagicMock(),
        )

        self.assertIsNone(result)
        load_config.assert_not_called()
        transfer_and_load.assert_not_called()

    @patch("main.transfer_and_load_gx")
    @patch("main.load_gx_remote_config")
    def test_remote_failure_is_propagated(
        self,
        load_config,
        transfer_and_load,
    ):
        load_config.return_value = MagicMock()
        transfer_and_load.side_effect = RuntimeError("remote failure")

        with self.assertRaisesRegex(RuntimeError, "remote failure"):
            deliver_export(
                "gx_ino",
                Path(r"C:\exports\GX INO.xls"),
                MagicMock(),
            )


if __name__ == "__main__":
    unittest.main()
