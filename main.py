import argparse
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pywinauto import Desktop

from pywinauto.keyboard import send_keys


EXE_PATH = r"C:\Program Files (x86)\MedGraphics\Breeze\DatabaseQuery.exe"
EXPORT_DIR = Path(r"C:\patient_query_automate\exports")


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
    return datetime.now().strftime("%d%m%Y_%H%M")


def wait_for_window(title: str, timeout: int = 60):
    desktop = Desktop(backend="uia")
    window = desktop.window(title=title)
    window.wait("visible", timeout=timeout)
    return window


def launch_patient_query():
    print("Lanzando Patient Query...")
    subprocess.Popen([EXE_PATH])


def login(username, password):
    print("Esperando ventana de login...")

    window = wait_for_window("Iniciar sesión", timeout=60)
    window.set_focus()

    edits = window.descendants(control_type="Edit")

    if len(edits) < 2:
        raise RuntimeError("No se encontraron campos de usuario y contraseña.")

    edits[0].set_text(username)
    edits[1].set_text(password)

    window.child_window(title="Aceptar", control_type="Button").click_input()

    print("Login enviado")


def wait_for_update_to_finish():
    print("Esperando actualización de base de datos...")

    desktop = Desktop(backend="uia")
    start = time.time()
    timeout = 600

    while time.time() - start < timeout:
        windows = [w.window_text() for w in desktop.windows() if w.window_text()]

        if "Consultar paciente" in windows:
            print("Actualización finalizada")
            return

        time.sleep(5)

    raise TimeoutError(
        "La ventana 'Consultar paciente' no apareció después de esperar la actualización."
    )


def get_query_window():
    window = wait_for_window("Consultar paciente", timeout=60)
    window.set_focus()
    return window


def select_query(window, query_name):
    print(f"Seleccionando consulta: {query_name}")

    query_combo = window.child_window(auto_id="5", control_type="ComboBox")
    query_combo.set_focus()

    # Método 1: selección directa por UIA
    try:
        query_combo.select(query_name)
        time.sleep(1)
        return
    except Exception as exc:
        print(f"Selección directa falló: {exc}")
        print("Intentando selección por escritura...")

    # Método 2: escritura en el Edit interno del combo
    edits = query_combo.descendants(control_type="Edit")

    if not edits:
        raise RuntimeError("No se encontró el campo interno del combo de consulta.")

    edits[0].set_text(query_name)
    time.sleep(0.5)

    # Confirmar selección
    query_combo.type_keys("{ENTER}")
    time.sleep(1)


def get_value_edits(window):
    """
    Devuelve los campos Edit de la columna Valores.

    Se excluye el Edit interno del combo superior de Consulta
    usando posición horizontal. En esta ventana, los campos
    de Valores están a la derecha, con left > 1000.
    """
    value_edits = [
        edit for edit in window.descendants(control_type="Edit")
        if edit.rectangle().left > 1000
    ]

    value_edits = sorted(
        value_edits,
        key=lambda edit: (edit.rectangle().top, edit.rectangle().left)
    )

    return value_edits


def configure_query(extractor_config):
    query_name = extractor_config["query_name"]
    visit_date_from = extractor_config.get("visit_date_from", "yesterday")

    if visit_date_from == "yesterday":
        visit_date_from = yesterday_str()

    print("Configurando consulta...")

    window = get_query_window()

    select_query(window, query_name)

    value_edits = get_value_edits(window)

    if not value_edits:
        raise RuntimeError("No se encontraron campos de valor para filtros.")

    value_edits[0].set_text(visit_date_from)

    print(f"Consulta seleccionada: {query_name}")
    print(f"Visit Date >= {visit_date_from}")

    print("Guardando cambios de la consulta...")
    window.child_window(title="Guardar", control_type="Button").click_input()

    time.sleep(2)


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

    # Enfocar el campo "File name"
    send_keys("%n")
    time.sleep(0.3)

    # Reemplazar el contenido
    send_keys("^a")
    send_keys(str(full_path), with_spaces=True, pause=0.01)


def set_save_dialog_file_type_excel(save_window):
    try:
        combo = save_window.child_window(
            title="Save as type:",
            control_type="ComboBox"
        )
        combo.select("Microsoft Excel 97-2003 Worksheet (*.xls)")
    except Exception:
        print("No se pudo seleccionar el tipo XLS; se conserva el valor actual.")


def confirm_save_dialog(save_window):
    save_window.child_window(title="Save", control_type="Button").click_input()


def export_query(extractor_config):
    query_name = extractor_config["query_name"]

    print("Ejecutando exportación...")

    window = get_query_window()
    window.child_window(title="Exportar", control_type="Button").click_input()

    print("Esperando ventana de guardado...")

    save_window = wait_for_save_dialog(timeout=60)

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{query_name}_{timestamp_str()}.xls"
    full_path = EXPORT_DIR / filename

    set_save_dialog_filename(save_window, full_path)
    set_save_dialog_file_type_excel(save_window)
    confirm_save_dialog(save_window)

    print(f"Exportación solicitada: {full_path}")


def close_patient_query():
    print("Cerrando Patient Query...")

    window = get_query_window()
    window.child_window(title="Salir", control_type="Button").click_input()

    print("Patient Query cerrado")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--extractor",
        required=True,
        help="Nombre del extractor definido en config/extractors.yaml",
    )

    args = parser.parse_args()

    load_dotenv()

    username = os.getenv("PATIENT_QUERY_USERNAME")
    password = os.getenv("PATIENT_QUERY_PASSWORD")

    if not username or not password:
        raise ValueError("Faltan credenciales en el archivo .env")

    extractor_config = get_extractor_config(args.extractor)

    launch_patient_query()
    login(username, password)
    wait_for_update_to_finish()
    configure_query(extractor_config)
    export_query(extractor_config)
    close_patient_query()


if __name__ == "__main__":
    main()