import argparse
import logging
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

from export_verification import wait_for_export_file
from gx_remote import load_gx_remote_config, transfer_and_load_gx
from logging_config import setup_logging


EXE_PATH = r"C:\Program Files (x86)\MedGraphics\Breeze\DatabaseQuery.exe"
EXPORT_DIR = Path(r"C:\patient_query_automate\exports")
EXPORT_TIMEOUT_SECONDS = 120
GX_EXTRACTOR_NAME = "gx_ino"
LOGIN_CONFIRMATION_ATTEMPTS = 3
LOGIN_CONFIRMATION_TIMEOUT_SECONDS = 5


def phase(phase_name: str) -> dict[str, str]:
    return {"phase": phase_name}


def load_extractors_config(path="config/extractors.yaml"):
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def get_extractor_config(extractor_name):
    config = load_extractors_config()
    extractors = config.get("extractors", {})

    if extractor_name not in extractors:
        available = ", ".join(extractors.keys())
        raise ValueError(
            f"Extractor no encontrado: {extractor_name}. "
            f"Extractores disponibles: {available}"
        )

    return extractors[extractor_name]


def yesterday_str():
    return (datetime.now() - timedelta(days=1)).strftime("%m/%d/%Y")


def timestamp_str():
    return datetime.now().strftime("%d%m%Y_%H%M%S")


def wait_for_window(title: str, timeout: int = 60):
    desktop = Desktop(backend="uia")
    window = desktop.window(title=title)
    window.wait("visible", timeout=timeout)
    return window


def launch_patient_query(logger: logging.LoggerAdapter):
    logger.info("Lanzando Patient Query", extra=phase("launch"))
    process = subprocess.Popen([EXE_PATH])
    logger.info(
        "Patient Query iniciado; pid=%s",
        process.pid,
        extra=phase("launch"),
    )
    return process


def wait_for_window_to_close(window, timeout: int) -> bool:
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        if not window.exists(timeout=0):
            return True
        time.sleep(0.25)

    return not window.exists(timeout=0)


def visible_window_titles() -> list[str]:
    desktop = Desktop(backend="uia")
    return [window.window_text() for window in desktop.windows() if window.window_text()]


def login(username, password, logger: logging.LoggerAdapter):
    logger.info("Esperando ventana de inicio de sesión", extra=phase("login"))

    window = wait_for_window("Iniciar sesión", timeout=60)
    window.set_focus()
    edits = window.descendants(control_type="Edit")

    if len(edits) < 2:
        raise RuntimeError("No se encontraron campos de usuario y contraseña.")

    edits[0].set_text(username)
    edits[1].set_text(password)
    accept_button = window.child_window(title="Aceptar", control_type="Button")

    for attempt in range(1, LOGIN_CONFIRMATION_ATTEMPTS + 1):
        window.set_focus()
        accept_button.click()
        logger.info(
            "Confirmación de inicio de sesión enviada; attempt=%s",
            attempt,
            extra=phase("login"),
        )

        if wait_for_window_to_close(window, LOGIN_CONFIRMATION_TIMEOUT_SECONDS):
            logger.info("Inicio de sesión confirmado", extra=phase("login"))
            return

        if attempt < LOGIN_CONFIRMATION_ATTEMPTS:
            logger.warning(
                "La ventana de inicio de sesión sigue visible; se reintentará; "
                "attempt=%s",
                attempt,
                extra=phase("login"),
            )

    titles = visible_window_titles()
    logger.error(
        "No fue posible confirmar el inicio de sesión; attempts=%s; "
        "visible_windows=%s",
        LOGIN_CONFIRMATION_ATTEMPTS,
        titles,
        extra=phase("login"),
    )
    raise TimeoutError(
        "La ventana 'Iniciar sesión' continuó visible después de "
        f"{LOGIN_CONFIRMATION_ATTEMPTS} intentos."
    )


def wait_for_update_to_finish(logger: logging.LoggerAdapter):
    logger.info(
        "Esperando actualización inicial de la base de datos",
        extra=phase("database_update"),
    )

    desktop = Desktop(backend="uia")
    start = time.monotonic()
    timeout = 600

    while time.monotonic() - start < timeout:
        windows = [w.window_text() for w in desktop.windows() if w.window_text()]

        if "Consultar paciente" in windows:
            elapsed = time.monotonic() - start
            logger.info(
                "Actualización finalizada; duration_seconds=%.2f",
                elapsed,
                extra=phase("database_update"),
            )
            return

        time.sleep(5)

    raise TimeoutError(
        "La ventana 'Consultar paciente' no apareció después de esperar la actualización."
    )


def get_query_window():
    window = wait_for_window("Consultar paciente", timeout=60)
    window.set_focus()
    return window


def select_query(window, query_name, logger: logging.LoggerAdapter):
    logger.info(
        "Seleccionando consulta; query_name=%s",
        query_name,
        extra=phase("query_selection"),
    )

    win32_window = Desktop(backend="win32").window(
        title="Consultar paciente"
    )
    win32_window.wait("visible enabled", timeout=60)

    query_combo = win32_window.child_window(
        control_id=5,
        class_name="ThunderRT6ComboBox",
    )

    available_queries = [
        value.strip()
        for value in query_combo.item_texts()
        if value.strip()
    ]

    if query_name not in available_queries:
        raise RuntimeError(
            f"La consulta {query_name!r} no existe en Patient Query."
        )

    query_combo.select(query_name)
    time.sleep(1)

    selected_query = query_combo.window_text().strip()

    if selected_query != query_name:
        raise RuntimeError(
            f"No se pudo verificar la selección de {query_name!r}; "
            f"valor actual={selected_query!r}."
        )

    logger.info(
        "Consulta seleccionada y verificada mediante Win32",
        extra=phase("query_selection"),
    )


def get_value_edits(window):
    """Localiza los campos Edit de la columna Valores."""
    edits = window.descendants(control_type="Edit")
    if not edits:
        return []

    max_left = max(edit.rectangle().left for edit in edits)
    value_edits = [
        edit
        for edit in edits
        if abs(edit.rectangle().left - max_left) <= 30
    ]
    return sorted(value_edits, key=lambda edit: edit.rectangle().top)


def set_visit_date_operator(operator: str, logger) -> None:
    window = Desktop(backend="win32").window(title="Consultar paciente")

    operator_combo = window.child_window(
        control_id=38,
        class_name="ThunderRT6ComboBox",
    )

    operator_combo.select(operator)

    logger.info(
        "Operador de fecha configurado; operator=%s",
        operator,
        extra={"phase": "query_configuration"},
    )


def configure_query(extractor_config, logger: logging.LoggerAdapter):
    query_name = extractor_config["query_name"]
    visit_date_from = extractor_config.get("visit_date_from", "yesterday")
    visit_date_operator = extractor_config.get("visit_date_operator")

    if visit_date_from == "yesterday":
        visit_date_from = yesterday_str()

    logger.info(
        "Configurando consulta; query_name=%s; visit_date_from=%s",
        query_name,
        visit_date_from,
        extra=phase("query_configuration"),
    )

    window = get_query_window()
    select_query(window, query_name, logger)
    if visit_date_operator:
        set_visit_date_operator(visit_date_operator, logger)
    value_edits = get_value_edits(window)

    if not value_edits:
        raise RuntimeError("No se encontraron campos de valor para filtros.")

    value_edits[0].set_text(visit_date_from)
    value_edits[0].click_input()
    value_edits[0].type_keys("{TAB}")
    time.sleep(0.5)
    window.child_window(title="Guardar", control_type="Button").click_input()
    time.sleep(2)

    logger.info(
        "Consulta guardada correctamente",
        extra=phase("query_configuration"),
    )


def wait_for_save_dialog(timeout=60):
    desktop = Desktop(backend="uia")
    save_window = desktop.window(
        title_re=".*Guardar resultados de la consulta como.*"
    )
    save_window.wait("visible", timeout=timeout)
    save_window.set_focus()
    return save_window


def set_save_dialog_filename(save_window, full_path):
    save_window.set_focus()
    time.sleep(0.5)
    send_keys("%n")
    time.sleep(0.3)
    send_keys("^a")
    send_keys(str(full_path), with_spaces=True, pause=0.01)


def set_save_dialog_file_type_excel(
    save_window,
    logger: logging.LoggerAdapter,
):
    try:
        combo = save_window.child_window(
            title="Save as type:",
            control_type="ComboBox",
        )
        combo.select("Microsoft Excel 97-2003 Worksheet (*.xls)")
        logger.info("Tipo XLS seleccionado", extra=phase("export"))
    except Exception:
        logger.warning(
            "No se pudo confirmar el tipo XLS; se conserva el valor actual",
            exc_info=True,
            extra=phase("export"),
        )


def confirm_save_dialog(save_window):
    save_window.child_window(title="Save", control_type="Button").click_input()


def export_query(extractor_config, logger: logging.LoggerAdapter):
    query_name = extractor_config["query_name"]
    logger.info("Iniciando exportación", extra=phase("export"))

    window = get_query_window()
    window.child_window(title="Exportar", control_type="Button").click_input()
    save_window = wait_for_save_dialog(timeout=60)

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{query_name}_{timestamp_str()}.xls"
    full_path = EXPORT_DIR / filename

    if full_path.exists():
        raise FileExistsError(f"Ya existe el archivo de exportación: {full_path}")

    set_save_dialog_filename(save_window, full_path)
    confirm_save_dialog(save_window)

    logger.info(
        "Exportación solicitada; file=%s",
        full_path,
        extra=phase("export"),
    )

    verification_start = time.monotonic()
    size_bytes = wait_for_export_file(
        full_path,
        timeout=EXPORT_TIMEOUT_SECONDS,
    )
    verification_duration = time.monotonic() - verification_start

    logger.info(
        "Exportación verificada; file=%s; size_bytes=%s; duration_seconds=%.2f",
        full_path,
        size_bytes,
        verification_duration,
        extra=phase("export_verification"),
    )
    return full_path, size_bytes


def deliver_export(
    extractor_name: str,
    exported_path: Path,
    logger: logging.LoggerAdapter,
):
    """Entrega al receptor remoto únicamente las exportaciones GX INO."""

    if extractor_name != GX_EXTRACTOR_NAME:
        return None

    config = load_gx_remote_config(logger)
    result = transfer_and_load_gx(exported_path, config, logger)
    logger.info(
        "Resultado del cargador GX remoto; response=%s",
        result.stdout,
        extra=phase("remote_result"),
    )
    return result


def close_patient_query(logger: logging.LoggerAdapter):
    logger.info("Cerrando Patient Query", extra=phase("cleanup"))
    window = get_query_window()
    window.child_window(title="Salir", control_type="Button").click_input()
    logger.info("Patient Query cerrado", extra=phase("cleanup"))


def safe_close_patient_query(
    logger: logging.LoggerAdapter,
    process: subprocess.Popen | None = None,
):
    try:
        close_patient_query(logger)

        if process is not None:
            process.wait(timeout=10)

        return
    except Exception:
        logger.warning(
            "No fue posible cerrar Patient Query mediante la interfaz",
            exc_info=True,
            extra=phase("cleanup"),
        )

    if process is None or process.poll() is not None:
        return

    logger.warning(
        "Forzando el cierre del proceso; pid=%s",
        process.pid,
        extra=phase("cleanup"),
    )
    process.terminate()

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        logger.warning(
            "El proceso no respondió; aplicando cierre forzado; pid=%s",
            process.pid,
            extra=phase("cleanup"),
        )
        process.kill()
        process.wait(timeout=5)

    logger.info(
        "Proceso de Patient Query cerrado; pid=%s",
        process.pid,
        extra=phase("cleanup"),
    )

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--extractor",
        required=True,
        help="Nombre del extractor definido en config/extractors.yaml",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging_context = setup_logging(args.extractor)
    logger = logging_context.logger
    started_at = time.monotonic()
    patient_query_process = None
    completed = False
    exported_path = None
    exported_size = None

    logger.info(
        "Ejecución iniciada; log_file=%s",
        logging_context.log_path,
        extra=phase("startup"),
    )

    try:
        load_dotenv()
        username = os.getenv("PATIENT_QUERY_USERNAME")
        password = os.getenv("PATIENT_QUERY_PASSWORD")

        if not username or not password:
            raise ValueError("Faltan credenciales en el archivo .env")

        extractor_config = get_extractor_config(args.extractor)
        logger.info(
            "Configuración cargada; query_name=%s; visit_date_from=%s",
            extractor_config.get("query_name"),
            extractor_config.get("visit_date_from", "yesterday"),
            extra=phase("configuration"),
        )

        patient_query_process = launch_patient_query(logger)
        login(username, password, logger)
        wait_for_update_to_finish(logger)
        configure_query(extractor_config, logger)
        exported_path, exported_size = export_query(extractor_config, logger)
        deliver_export(args.extractor, exported_path, logger)
        completed = True
        return 0
    except Exception:
        logger.exception(
            "La ejecución terminó con error",
            extra=phase("run_failed"),
        )
        return 1
    finally:
        if patient_query_process is not None:
            safe_close_patient_query(logger, patient_query_process)

        duration = time.monotonic() - started_at
        if completed:
            logger.info(
                "Ejecución completada; status=success; file=%s; "
                "size_bytes=%s; duration_seconds=%.2f",
                exported_path,
                exported_size,
                duration,
                extra=phase("run_completed"),
            )
        else:
            logger.error(
                "Ejecución finalizada; status=failed; duration_seconds=%.2f",
                duration,
                extra=phase("run_failed"),
            )


if __name__ == "__main__":
    raise SystemExit(main())
