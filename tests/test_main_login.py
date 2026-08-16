import sys
import types
import unittest
from unittest.mock import MagicMock, call, patch


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


import main


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.window = MagicMock()
        self.username_edit = MagicMock()
        self.password_edit = MagicMock()
        self.accept_button = MagicMock()
        self.window.descendants.return_value = [
            self.username_edit,
            self.password_edit,
        ]
        self.window.child_window.return_value = self.accept_button

    @patch("main.wait_for_window_to_close", return_value=True)
    @patch("main.wait_for_window")
    def test_login_invokes_button_and_confirms_window_closed(
        self,
        wait_for_window,
        wait_for_close,
    ):
        wait_for_window.return_value = self.window

        main.login("observatorio.ino", "secret", self.logger)

        self.username_edit.set_text.assert_called_once_with("observatorio.ino")
        self.password_edit.set_text.assert_called_once_with("secret")
        self.accept_button.click.assert_called_once_with()
        self.accept_button.click_input.assert_not_called()
        wait_for_close.assert_called_once_with(
            self.window,
            main.LOGIN_CONFIRMATION_TIMEOUT_SECONDS,
        )
        self.assertIn(
            call("Inicio de sesión confirmado", extra={"phase": "login"}),
            self.logger.info.call_args_list,
        )

    @patch("main.wait_for_window_to_close", side_effect=[False, True])
    @patch("main.wait_for_window")
    def test_login_retries_when_window_remains_visible(
        self,
        wait_for_window,
        wait_for_close,
    ):
        wait_for_window.return_value = self.window

        main.login("observatorio.ino", "secret", self.logger)

        self.assertEqual(self.accept_button.click.call_count, 2)
        self.assertEqual(wait_for_close.call_count, 2)
        self.logger.warning.assert_called_once()

    @patch("main.visible_window_titles", return_value=["Iniciar sesión", "Updates"])
    @patch("main.wait_for_window_to_close", return_value=False)
    @patch("main.wait_for_window")
    def test_login_raises_clear_error_after_all_attempts(
        self,
        wait_for_window,
        wait_for_close,
        visible_titles,
    ):
        wait_for_window.return_value = self.window

        with self.assertRaisesRegex(
            TimeoutError,
            "continuó visible después de 3 intentos",
        ):
            main.login("observatorio.ino", "secret", self.logger)

        self.assertEqual(
            self.accept_button.click.call_count,
            main.LOGIN_CONFIRMATION_ATTEMPTS,
        )
        self.assertEqual(
            wait_for_close.call_count,
            main.LOGIN_CONFIRMATION_ATTEMPTS,
        )
        visible_titles.assert_called_once_with()
        self.logger.error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
