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
from logging_config import setup_logging


EXE_PATH = r"C:\Program Files (x86)\MedGraphics\Breeze\DatabaseQuery.exe"
EXPORT_DIR = Path(r"C:\patient_query_automate\exports")
EXPORT_TIMEOUT_SECONDS = 120


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
    return (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")


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


def login(username, password, logger: logging.LoggerAdapter):
    logger.info("Esperando ventana de inicio de sesión", extra=phase("login"))

    window = wait_for_window("Iniciar sesión", timeout=60)
    window.set_focus()
    edits = window.descendants(control_type="Edit")

    if len(edits) < 2:
        raise RuntimeError("No se encontraron campos de usuario y contraseña.")

    edits[0].set_text(username)
    edits[1].set_text(password)
    window.child_window(title="Aceptar", control_type="Button").click_input()

    logger.info("Credenciales enviadas", extra=phase("login"))


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

    query_combo = window.child_window(auto_id="5", control_type="ComboBox")
    query_combo.set_focus()

    try:
        query_combo.select(query_name)
        time.sleep(1)
        logger.info(
            "Consulta seleccionada mediante UI Automation",
            extra=phase("query_selection"),
        )
        return
    except Exception:
        logger.warning(
            "Falló la selección directa; se intentará selección por escritura",
            exc_info=True,
            extra=phase("query_selection"),
        )

    edits = query_combo.descendants(control_type="Edit")
    if not edits:
        raise RuntimeError("No se encontró el campo interno del combo de consulta.")

    edits[0].set_text(query_name)
    time.sleep(0.5)
    query_combo.type_keys("{ENTER}")
    time.sleep(1)

    logger.info(
        "Consulta seleccionada mediante escritura",
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


def configure_query(extractor_config, logger: logging.LoggerAdapter):
    query_name = extractor_config["query_name"]
    visit_date_from = extractor_config.get("visit_date_from", "yesterday")

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
    value_edits = get_value_edits(window)

    if not value_edits:
        raise RuntimeError("No se encontraron campos de valor para filtros.")

    value_edits[0].set_text(visit_date_from)
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
    set_save_dialog_file_type_excel(save_window, logger)
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


def close_patient_query(logger: logging.LoggerAdapter):
    logger.info("Cerrando Patient Query", extra=phase("cleanup"))
    window = get_query_window()
    window.child_window(title="Salir", control_type="Button").click_input()
    logger.info("Patient Query cerrado", extra=phase("cleanup"))


def safe_close_patient_query(logger: logging.LoggerAdapter):
    try:
        close_patient_query(logger)
    except Exception:
        logger.warning(
            "No fue posible confirmar el cierre de Patient Query",
            exc_info=True,
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
    patient_query_launched = False
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

        launch_patient_query(logger)
        patient_query_launched = True
        login(username, password, logger)
        wait_for_update_to_finish(logger)
        configure_query(extractor_config, logger)
        exported_path, exported_size = export_query(extractor_config, logger)
        completed = True
        return 0
    except Exception:
        logger.exception(
            "La ejecución terminó con error",
            extra=phase("run_failed"),
        )
        return 1
    finally:
        if patient_query_launched:
            safe_close_patient_query(logger)

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
