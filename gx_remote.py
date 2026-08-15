"""Transfiere una exportación GX a mineriaino y ejecuta su cargador remoto."""

from __future__ import annotations

import logging
import os
import posixpath
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import paramiko


DEFAULT_REMOTE_INCOMING_DIR = "/srv/data/obsino/labfp/gx_ino/incoming"
DEFAULT_REMOTE_PROJECT_DIR = "/opt/apps/etl/obsino/INO_Labfp2"
DEFAULT_REMOTE_PYTHON = ".venv/bin/python"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 15
DEFAULT_COMMAND_TIMEOUT_SECONDS = 600
REMOTE_FILE_MODE = 0o640


class GxRemoteError(RuntimeError):
    """Indica un fallo de configuración, transferencia o carga remota GX."""


def phase(phase_name: str) -> dict[str, str]:
    """Añade la fase GX al registro de la ejecución principal."""

    return {"phase": phase_name}


@dataclass(frozen=True)
class GxRemoteConfig:
    """Configuración no interactiva del acceso a mineriaino."""

    host: str
    port: int
    username: str
    private_key_path: Path
    known_hosts_path: Path
    remote_incoming_dir: str = DEFAULT_REMOTE_INCOMING_DIR
    remote_project_dir: str = DEFAULT_REMOTE_PROJECT_DIR
    remote_python: str = DEFAULT_REMOTE_PYTHON
    connect_timeout_seconds: int = DEFAULT_CONNECT_TIMEOUT_SECONDS
    command_timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "GxRemoteConfig":
        """Construye la configuración desde variables de entorno."""

        values = os.environ if environment is None else environment
        required = {
            "GX_SSH_HOST": values.get("GX_SSH_HOST"),
            "GX_SSH_USERNAME": values.get("GX_SSH_USERNAME"),
            "GX_SSH_PRIVATE_KEY": values.get("GX_SSH_PRIVATE_KEY"),
            "GX_SSH_KNOWN_HOSTS": values.get("GX_SSH_KNOWN_HOSTS"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise GxRemoteError(
                "Faltan variables de entorno GX: " + ", ".join(missing)
            )

        try:
            port = int(values.get("GX_SSH_PORT", "22"))
            connect_timeout = int(
                values.get(
                    "GX_SSH_CONNECT_TIMEOUT_SECONDS",
                    str(DEFAULT_CONNECT_TIMEOUT_SECONDS),
                )
            )
            command_timeout = int(
                values.get(
                    "GX_REMOTE_COMMAND_TIMEOUT_SECONDS",
                    str(DEFAULT_COMMAND_TIMEOUT_SECONDS),
                )
            )
        except ValueError as error:
            raise GxRemoteError(
                "Los valores de puerto y timeout GX deben ser enteros."
            ) from error

        if not 1 <= port <= 65535:
            raise GxRemoteError("GX_SSH_PORT debe estar entre 1 y 65535.")
        if connect_timeout <= 0 or command_timeout <= 0:
            raise GxRemoteError("Los timeout GX deben ser mayores que cero.")

        private_key_path = Path(required["GX_SSH_PRIVATE_KEY"])
        known_hosts_path = Path(required["GX_SSH_KNOWN_HOSTS"])
        if not private_key_path.is_file():
            raise GxRemoteError(
                f"No existe la clave privada GX: {private_key_path}"
            )
        if not known_hosts_path.is_file():
            raise GxRemoteError(
                f"No existe el archivo known_hosts GX: {known_hosts_path}"
            )

        return cls(
            host=str(required["GX_SSH_HOST"]),
            port=port,
            username=str(required["GX_SSH_USERNAME"]),
            private_key_path=private_key_path,
            known_hosts_path=known_hosts_path,
            remote_incoming_dir=values.get(
                "GX_REMOTE_INCOMING_DIR",
                DEFAULT_REMOTE_INCOMING_DIR,
            ),
            remote_project_dir=values.get(
                "GX_REMOTE_PROJECT_DIR",
                DEFAULT_REMOTE_PROJECT_DIR,
            ),
            remote_python=values.get(
                "GX_REMOTE_PYTHON",
                DEFAULT_REMOTE_PYTHON,
            ),
            connect_timeout_seconds=connect_timeout,
            command_timeout_seconds=command_timeout,
        )


@dataclass(frozen=True)
class GxRemoteResult:
    """Resultado agregado de la transferencia y ejecución remota."""

    remote_path: str
    stdout: str


def load_gx_remote_config(
    logger: logging.Logger,
    environment: Mapping[str, str] | None = None,
) -> GxRemoteConfig:
    """Carga la configuración SSH dentro de la estrategia general de logging."""

    logger.info(
        "Cargando configuración de transporte GX",
        extra=phase("remote_configuration"),
    )
    try:
        config = GxRemoteConfig.from_environment(environment)
    except Exception:
        logger.exception(
            "Falló la configuración de transporte GX",
            extra=phase("remote_failed"),
        )
        raise

    logger.info(
        "Configuración de transporte GX validada; host=%s; port=%s",
        config.host,
        config.port,
        extra=phase("remote_configuration"),
    )
    return config


def build_remote_command(config: GxRemoteConfig, remote_path: str) -> str:
    """Construye el comando remoto escapando todos los argumentos variables."""

    return (
        f"cd {shlex.quote(config.remote_project_dir)} && "
        f"{shlex.quote(config.remote_python)} "
        "-m src.pipeline_load_gx_excel "
        f"--file {shlex.quote(remote_path)}"
    )


def _remote_exists(sftp: paramiko.SFTPClient, remote_path: str) -> bool:
    try:
        sftp.stat(remote_path)
    except OSError as error:
        if getattr(error, "errno", None) == 2:
            return False
        raise
    return True


def _remove_partial_file(
    sftp: paramiko.SFTPClient,
    partial_path: str,
    logger: logging.Logger,
) -> None:
    try:
        sftp.remove(partial_path)
    except OSError as error:
        if getattr(error, "errno", None) != 2:
            logger.warning(
                "No fue posible eliminar el archivo parcial remoto; file=%s",
                partial_path,
                exc_info=True,
            )


def transfer_and_load_gx(
    local_file: Path,
    config: GxRemoteConfig,
    logger: logging.Logger,
) -> GxRemoteResult:
    """Sube el Excel de forma atómica y ejecuta el cargador en mineriaino."""

    local_path = Path(local_file).resolve()
    if not local_path.is_file():
        raise GxRemoteError(f"No existe el archivo GX: {local_path}")
    if local_path.suffix.lower() not in {".xls", ".xlsx"}:
        raise GxRemoteError(
            f"La exportación GX no tiene extensión Excel: {local_path.name}"
        )

    remote_path = posixpath.join(
        config.remote_incoming_dir.rstrip("/"),
        local_path.name,
    )
    partial_path = posixpath.join(
        config.remote_incoming_dir.rstrip("/"),
        f".{local_path.name}.part",
    )

    client = paramiko.SSHClient()
    client.load_host_keys(str(config.known_hosts_path))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())

    logger.info(
        "Conectando con mineriaino para transferencia GX; host=%s; port=%s",
        config.host,
        config.port,
        extra=phase("remote_connection"),
    )

    try:
        client.connect(
            hostname=config.host,
            port=config.port,
            username=config.username,
            key_filename=str(config.private_key_path),
            look_for_keys=False,
            allow_agent=False,
            timeout=config.connect_timeout_seconds,
            banner_timeout=config.connect_timeout_seconds,
            auth_timeout=config.connect_timeout_seconds,
        )

        with client.open_sftp() as sftp:
            if _remote_exists(sftp, remote_path):
                raise GxRemoteError(
                    f"Ya existe el archivo GX en incoming: {local_path.name}"
                )

            _remove_partial_file(sftp, partial_path, logger)

            logger.info(
                "Iniciando transferencia GX; file=%s; size_bytes=%s",
                local_path.name,
                local_path.stat().st_size,
                extra=phase("remote_upload"),
            )

            try:
                sftp.put(str(local_path), partial_path, confirm=True)
                sftp.chmod(partial_path, REMOTE_FILE_MODE)

                remote_size = sftp.stat(partial_path).st_size
                local_size = local_path.stat().st_size
                if remote_size != local_size:
                    raise GxRemoteError(
                        "El tamaño transferido no coincide con el archivo local: "
                        f"local={local_size}; remote={remote_size}"
                    )

                sftp.posix_rename(partial_path, remote_path)
            except Exception:
                _remove_partial_file(sftp, partial_path, logger)
                raise

        logger.info(
            "Transferencia GX verificada; file=%s; size_bytes=%s",
            local_path.name,
            local_path.stat().st_size,
            extra=phase("remote_upload_verified"),
        )

        command = build_remote_command(config, remote_path)
        logger.info(
            "Iniciando cargador GX remoto; file=%s",
            local_path.name,
            extra=phase("remote_execution"),
        )
        _, stdout_stream, stderr_stream = client.exec_command(
            command,
            timeout=config.command_timeout_seconds,
        )
        stdout = stdout_stream.read().decode("utf-8", errors="replace").strip()
        stderr = stderr_stream.read().decode("utf-8", errors="replace").strip()
        exit_status = stdout_stream.channel.recv_exit_status()

        if exit_status != 0:
            raise GxRemoteError(
                "El cargador GX remoto terminó con error; "
                f"exit_status={exit_status}"
            )

        logger.info(
            "Carga GX remota completada; file=%s; exit_status=0",
            local_path.name,
            extra=phase("remote_completed"),
        )
        return GxRemoteResult(remote_path=remote_path, stdout=stdout)
    except GxRemoteError:
        logger.exception(
            "Falló el transporte o la carga remota GX; file=%s",
            local_path.name,
            extra=phase("remote_failed"),
        )
        raise
    except Exception as error:
        logger.exception(
            "Falló el transporte o la carga remota GX; file=%s",
            local_path.name,
            extra=phase("remote_failed"),
        )
        raise GxRemoteError(
            f"Falló la transferencia o ejecución remota GX: {error}"
        ) from error
    finally:
        client.close()
