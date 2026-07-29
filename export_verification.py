import time
from pathlib import Path


class ExportVerificationError(RuntimeError):
    """Indica que el archivo exportado no pudo validarse."""


def wait_for_export_file(
    path: Path,
    timeout: float = 120.0,
    poll_interval: float = 1.0,
    stable_checks: int = 3,
) -> int:
    if timeout <= 0:
        raise ValueError("timeout debe ser mayor que cero")
    if poll_interval <= 0:
        raise ValueError("poll_interval debe ser mayor que cero")
    if stable_checks < 1:
        raise ValueError("stable_checks debe ser al menos 1")

    deadline = time.monotonic() + timeout
    previous_size: int | None = None
    consecutive_stable_checks = 0

    while time.monotonic() < deadline:
        if path.is_file():
            size = path.stat().st_size

            if size > 0 and size == previous_size:
                consecutive_stable_checks += 1
            else:
                consecutive_stable_checks = 0

            previous_size = size

            if size > 0 and consecutive_stable_checks >= stable_checks:
                try:
                    with path.open("rb") as exported_file:
                        exported_file.read(1)
                except OSError as exc:
                    raise ExportVerificationError(
                        f"El archivo exportado no puede abrirse: {path}"
                    ) from exc

                return size

        time.sleep(poll_interval)

    raise ExportVerificationError(
        f"El archivo exportado no apareció o no se estabilizó dentro de "
        f"{timeout:.0f} segundos: {path}"
    )
