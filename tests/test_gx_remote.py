import errno
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    import paramiko  # noqa: F401
except ModuleNotFoundError:
    paramiko_stub = types.ModuleType("paramiko")
    paramiko_stub.SSHClient = object
    paramiko_stub.SFTPClient = object
    paramiko_stub.RejectPolicy = object
    sys.modules["paramiko"] = paramiko_stub


from gx_remote import (
    GxRemoteConfig,
    GxRemoteError,
    build_remote_command,
    transfer_and_load_gx,
)


class FakeChannel:
    def __init__(self, exit_status: int):
        self.exit_status = exit_status

    def recv_exit_status(self):
        return self.exit_status


class FakeStream:
    def __init__(self, payload: bytes, exit_status: int = 0):
        self.payload = payload
        self.channel = FakeChannel(exit_status)

    def read(self):
        return self.payload


class FakeSftp:
    def __init__(self, remote_size: int):
        self.remote_size = remote_size
        self.files = set()
        self.operations = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def stat(self, path):
        if path not in self.files:
            raise OSError(errno.ENOENT, "not found")
        result = MagicMock()
        result.st_size = self.remote_size
        return result

    def put(self, local_path, remote_path, confirm=True):
        self.operations.append(("put", local_path, remote_path, confirm))
        self.files.add(remote_path)

    def chmod(self, remote_path, mode):
        self.operations.append(("chmod", remote_path, mode))

    def posix_rename(self, source, target):
        self.operations.append(("rename", source, target))
        self.files.remove(source)
        self.files.add(target)

    def remove(self, remote_path):
        self.operations.append(("remove", remote_path))
        if remote_path not in self.files:
            raise OSError(errno.ENOENT, "not found")
        self.files.remove(remote_path)


def build_config(root: Path) -> GxRemoteConfig:
    private_key = root / "id_rsa"
    known_hosts = root / "known_hosts"
    private_key.write_text("test", encoding="utf-8")
    known_hosts.write_text("test", encoding="utf-8")
    return GxRemoteConfig(
        host="192.168.32.53",
        port=22,
        username="rom",
        private_key_path=private_key,
        known_hosts_path=known_hosts,
    )


class GxRemoteConfigTests(unittest.TestCase):
    def test_environment_requires_all_access_values(self):
        with self.assertRaisesRegex(GxRemoteError, "GX_SSH_USERNAME"):
            GxRemoteConfig.from_environment({"GX_SSH_HOST": "server"})

    def test_environment_builds_valid_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private_key = root / "id_rsa"
            known_hosts = root / "known_hosts"
            private_key.write_text("test", encoding="utf-8")
            known_hosts.write_text("test", encoding="utf-8")
            config = GxRemoteConfig.from_environment(
                {
                    "GX_SSH_HOST": "192.168.32.53",
                    "GX_SSH_USERNAME": "rom",
                    "GX_SSH_PRIVATE_KEY": str(private_key),
                    "GX_SSH_KNOWN_HOSTS": str(known_hosts),
                }
            )
            self.assertEqual(config.port, 22)
            self.assertEqual(config.username, "rom")

    def test_remote_command_quotes_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            config = build_config(Path(directory))
            command = build_remote_command(
                config,
                "/srv/data/incoming/GX INO.xls",
            )
            self.assertIn("'/srv/data/incoming/GX INO.xls'", command)
            self.assertIn("src.pipeline_load_gx_excel", command)


class GxRemoteTransferTests(unittest.TestCase):
    @patch("gx_remote.paramiko.SSHClient")
    def test_transfer_is_atomic_and_executes_remote_loader(self, client_class):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local_file = root / "GX INO_15082026_061013.xls"
            local_file.write_bytes(b"excel-content")
            config = build_config(root)

            sftp = FakeSftp(remote_size=local_file.stat().st_size)
            client = client_class.return_value
            client.open_sftp.return_value = sftp
            stdout = FakeStream(b"LOAD_OK", exit_status=0)
            stderr = FakeStream(b"")
            client.exec_command.return_value = (MagicMock(), stdout, stderr)

            result = transfer_and_load_gx(
                local_file=local_file,
                config=config,
                logger=MagicMock(),
            )

            self.assertEqual(result.stdout, "LOAD_OK")
            self.assertTrue(result.remote_path.endswith(local_file.name))
            self.assertTrue(any(item[0] == "put" for item in sftp.operations))
            self.assertIn(("chmod", f"{result.remote_path.rsplit('/', 1)[0]}/.{local_file.name}.part", 0o640), sftp.operations)
            self.assertTrue(any(item[0] == "rename" for item in sftp.operations))
            client.load_host_keys.assert_called_once_with(str(config.known_hosts_path))
            client.connect.assert_called_once()
            client.exec_command.assert_called_once()
            client.close.assert_called_once()

    @patch("gx_remote.paramiko.SSHClient")
    def test_remote_loader_failure_is_propagated(self, client_class):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local_file = root / "GX.xls"
            local_file.write_bytes(b"excel-content")
            config = build_config(root)

            client = client_class.return_value
            client.open_sftp.return_value = FakeSftp(
                remote_size=local_file.stat().st_size
            )
            stdout = FakeStream(b"", exit_status=1)
            stderr = FakeStream(b"validation failed")
            client.exec_command.return_value = (MagicMock(), stdout, stderr)

            with self.assertRaisesRegex(GxRemoteError, "validation failed"):
                transfer_and_load_gx(
                    local_file=local_file,
                    config=config,
                    logger=MagicMock(),
                )

            client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
