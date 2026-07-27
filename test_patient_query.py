import time
from datetime import datetime
from pathlib import Path

from pywinauto import Desktop
from pywinauto.keyboard import send_keys


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

QUERY_NAME = "__OBS_test"
FILTER_DATE = "06/23/2026"

TEST_FIELDS = [
    "ID",
    "Visit Date",
    "Age",
]

EXPORT_DIR = Path(r"C:\patient_query_automate\exports")

MAIN_WINDOW_TITLE = "Consultar paciente"
FIELDS_WINDOW_TITLE = "Seleccione campos de resultados de la consulta"

WINDOW_TIMEOUT = 30
SAVE_DIALOG_TIMEOUT = 60
EXPORT_TIMEOUT = 300

CONTROL_DELAY = 0.4
TABLE_CHANGE_DELAY = 0.8

# Ventana principal
QUERY_COMBO_ID = 5
SAVE_QUERY_BUTTON_ID = 3
SELECT_FIELDS_BUTTON_ID = 25
EXPORT_BUTTON_ID = 22

# Primera fila de filtros
FILTER_TABLE_COMBO_ID = 26
FILTER_FIELD_COMBO_ID = 32
FILTER_OPERATOR_COMBO_ID = 38

# Ventana "Seleccionar Campos"
FIELDS_TABLE_COMBO_ID = 4
FIELDS_FIELD_COMBO_ID = 5
FIELDS_ACCEPT_BUTTON_ID = 7
FIELDS_CLEAR_ALL_BUTTON_ID = 8
FIELDS_ADD_BUTTON_ID = 10


# ============================================================================
# UTILIDADES
# ============================================================================

def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def get_main_window_win32():
    window = Desktop(backend="win32").window(
        title=MAIN_WINDOW_TITLE
    )
    window.wait("visible enabled", timeout=WINDOW_TIMEOUT)
    window.set_focus()
    return window


def get_main_window_uia():
    window = Desktop(backend="uia").window(
        title=MAIN_WINDOW_TITLE
    )
    window.wait("visible", timeout=WINDOW_TIMEOUT)
    return window


def get_fields_window():
    window = Desktop(backend="win32").window(
        title=FIELDS_WINDOW_TITLE
    )
    window.wait("visible", timeout=WINDOW_TIMEOUT)
    window.set_focus()
    return window


def select_combo_value(combo, value: str, label: str) -> None:
    items = combo.item_texts()

    if value not in items:
        raise ValueError(
            f"No se encontró {value!r} en {label}. "
            f"Valores disponibles: {items}"
        )

    combo.select(value)
    time.sleep(CONTROL_DELAY)

    current_value = combo.window_text()

    if current_value != value:
        raise RuntimeError(
            f"No se pudo seleccionar {value!r} en {label}. "
            f"Valor actual: {current_value!r}"
        )


def get_value_edits(window):
    """
    Localiza los campos Edit de la columna Valores sin depender
    de auto_id ni de coordenadas absolutas.
    """
    edits = window.descendants(control_type="Edit")

    if not edits:
        return []

    visible_edits = [
        edit
        for edit in edits
        if edit.is_visible()
    ]

    if not visible_edits:
        return []

    max_left = max(
        edit.rectangle().left
        for edit in visible_edits
    )

    value_edits = [
        edit
        for edit in visible_edits
        if abs(edit.rectangle().left - max_left) <= 30
    ]

    return sorted(
        value_edits,
        key=lambda edit: edit.rectangle().top,
    )


# ============================================================================
# SELECCIÓN DE CONSULTA
# ============================================================================

def select_query() -> None:
    window = get_main_window_win32()

    query_combo = window.child_window(
        control_id=QUERY_COMBO_ID,
        class_name="ThunderRT6ComboBox",
    )

    select_combo_value(
        combo=query_combo,
        value=QUERY_NAME,
        label="el desplegable de consultas",
    )

    log(f"Consulta seleccionada: {QUERY_NAME}")


# ============================================================================
# SELECCIÓN DE CAMPOS DE PRUEBA
# ============================================================================

def configure_test_fields() -> None:
    main_window = get_main_window_win32()

    select_fields_button = main_window.child_window(
        control_id=SELECT_FIELDS_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    )

    select_fields_button.wait("enabled", timeout=WINDOW_TIMEOUT)
    select_fields_button.click_input()

    fields_window = get_fields_window()

    table_combo = fields_window.child_window(
        control_id=FIELDS_TABLE_COMBO_ID,
        class_name="ThunderRT6ComboBox",
    )

    field_combo = fields_window.child_window(
        control_id=FIELDS_FIELD_COMBO_ID,
        class_name="ThunderRT6ComboBox",
    )

    clear_button = fields_window.child_window(
        control_id=FIELDS_CLEAR_ALL_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    )

    add_button = fields_window.child_window(
        control_id=FIELDS_ADD_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    )

    accept_button = fields_window.child_window(
        control_id=FIELDS_ACCEPT_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    )

    if clear_button.is_enabled():
        clear_button.click_input()
        time.sleep(CONTROL_DELAY)
        log("Campos seleccionados eliminados")
    else:
        log("La lista de campos ya estaba vacía")

    select_combo_value(
        combo=table_combo,
        value="Demographic",
        label="el desplegable de tablas",
    )

    time.sleep(TABLE_CHANGE_DELAY)

    available_fields = field_combo.item_texts()

    for field_name in TEST_FIELDS:
        if field_name not in available_fields:
            raise ValueError(
                f"No existe el campo {field_name!r} "
                "en la tabla Demographic."
            )

        field_combo.select(field_name)
        time.sleep(CONTROL_DELAY)

        current_field = field_combo.window_text()

        if current_field != field_name:
            raise RuntimeError(
                f"No se pudo seleccionar {field_name!r}. "
                f"Valor actual: {current_field!r}"
            )

        if not add_button.is_enabled():
            raise RuntimeError(
                f"El botón > está deshabilitado para "
                f"{field_name!r}."
            )

        add_button.click_input()
        time.sleep(CONTROL_DELAY)

        log(f"Campo agregado: Demographic > {field_name}")

    if not accept_button.is_enabled():
        raise RuntimeError(
            "El botón Aceptar está deshabilitado."
        )

    accept_button.click_input()

    fields_window.wait_not(
        "visible",
        timeout=WINDOW_TIMEOUT,
    )

    log("Selección de campos aceptada")


# ============================================================================
# CONFIGURACIÓN DEL FILTRO
# ============================================================================

def configure_filter() -> None:
    window_win32 = get_main_window_win32()

    table_combo = window_win32.child_window(
        control_id=FILTER_TABLE_COMBO_ID,
        class_name="ThunderRT6ComboBox",
    )

    field_combo = window_win32.child_window(
        control_id=FILTER_FIELD_COMBO_ID,
        class_name="ThunderRT6ComboBox",
    )

    operator_combo = window_win32.child_window(
        control_id=FILTER_OPERATOR_COMBO_ID,
        class_name="ThunderRT6ComboBox",
    )

    select_combo_value(
        combo=table_combo,
        value="Demographic",
        label="la tabla de la primera fila del filtro",
    )

    time.sleep(TABLE_CHANGE_DELAY)

    select_combo_value(
        combo=field_combo,
        value="Visit Date",
        label="el campo de la primera fila del filtro",
    )

    time.sleep(CONTROL_DELAY)

    select_combo_value(
        combo=operator_combo,
        value="=",
        label="el operador de la primera fila del filtro",
    )

    time.sleep(CONTROL_DELAY)

    log("Tabla, campo y operador del filtro configurados")

    # Se usa la misma estrategia del script que ya funcionaba:
    # localizar dinámicamente los Edit de la columna Valores.
    window_uia = get_main_window_uia()

    value_edits = get_value_edits(window_uia)

    if not value_edits:
        raise RuntimeError(
            "No se encontraron campos visibles en la columna Valores."
        )

    value_edit = value_edits[0]

    log(
        "Campo de valor localizado: "
        f"rectángulo={value_edit.rectangle()}"
    )

    value_edit.set_text(FILTER_DATE)
    time.sleep(1)

    try:
        current_value = value_edit.get_value()
    except Exception:
        current_value = value_edit.window_text()

    log(f"Valor leído en el filtro: {current_value!r}")

    if current_value != FILTER_DATE:
        raise RuntimeError(
            f"La fecha no quedó configurada correctamente. "
            f"Esperada: {FILTER_DATE!r}. "
            f"Actual: {current_value!r}"
        )

    log(
        f"Filtro configurado: "
        f"Demographic > Visit Date = {FILTER_DATE}"
    )


# ============================================================================
# GUARDAR CONSULTA
# ============================================================================

def save_query() -> None:
    window = get_main_window_win32()

    save_button = window.child_window(
        control_id=SAVE_QUERY_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    )

    save_button.wait("enabled", timeout=WINDOW_TIMEOUT)
    save_button.click_input()

    time.sleep(2)

    log("Consulta guardada")


# ============================================================================
# EXPORTACIÓN
# ============================================================================

def wait_for_save_dialog():
    desktop = Desktop(backend="uia")

    save_window = desktop.window(
        title_re=(
            r".*(Guardar resultados de la consulta como"
            r"|Guardar como|Save As).*"
        )
    )

    save_window.wait(
        "visible",
        timeout=SAVE_DIALOG_TIMEOUT,
    )
    save_window.set_focus()

    return save_window


def set_save_dialog_filename(
    save_window,
    full_path: Path,
) -> None:
    save_window.set_focus()
    time.sleep(0.5)

    send_keys("%n")
    time.sleep(0.3)

    send_keys("^a")
    send_keys(
        str(full_path),
        with_spaces=True,
        pause=0.01,
    )


def set_save_dialog_file_type_excel(
    save_window,
) -> None:
    try:
        combo = save_window.child_window(
            title="Save as type:",
            control_type="ComboBox",
        )

        combo.select(
            "Microsoft Excel 97-2003 Worksheet (*.xls)"
        )

        log("Tipo de archivo XLS seleccionado")

    except Exception:
        log(
            "No se pudo seleccionar explícitamente el tipo XLS; "
            "se conserva el valor actual."
        )


def confirm_save_dialog(save_window) -> None:
    try:
        save_button = save_window.child_window(
            title="Save",
            control_type="Button",
        )

        save_button.wait("enabled", timeout=5)
        save_button.click_input()
        return

    except Exception:
        pass

    save_button = save_window.child_window(
        title="Guardar",
        control_type="Button",
    )

    save_button.wait("enabled", timeout=5)
    save_button.click_input()


def wait_for_file(
    file_path: Path,
    timeout: int = EXPORT_TIMEOUT,
) -> None:
    start_time = time.time()
    previous_size = None
    stable_checks = 0

    while time.time() - start_time < timeout:
        if file_path.exists():
            current_size = file_path.stat().st_size

            if (
                current_size > 0
                and previous_size is not None
                and current_size == previous_size
            ):
                stable_checks += 1
            else:
                stable_checks = 0

            previous_size = current_size

            if stable_checks >= 3:
                log(
                    f"Archivo terminado: {file_path} "
                    f"({current_size:,} bytes)"
                )
                return

        time.sleep(1)

    raise TimeoutError(
        f"No terminó el guardado de {file_path}"
    )


def export_test() -> Path:
    window = get_main_window_win32()

    export_button = window.child_window(
        control_id=EXPORT_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    )

    export_button.wait("enabled", timeout=WINDOW_TIMEOUT)

    EXPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = (
        EXPORT_DIR
        / f"{QUERY_NAME}_TEST_{timestamp}.xls"
    )

    log("Iniciando exportación")

    export_button.click_input()

    save_window = wait_for_save_dialog()

    set_save_dialog_filename(
        save_window=save_window,
        full_path=output_path,
    )

    set_save_dialog_file_type_excel(save_window)
    confirm_save_dialog(save_window)

    log(f"Guardado solicitado: {output_path}")

    wait_for_file(output_path)

    return output_path


# ============================================================================
# PROGRAMA PRINCIPAL
# ============================================================================

def main() -> None:
    log("Inicio de prueba")

    select_query()
    configure_test_fields()
    configure_filter()
    save_query()

    output_path = export_test()

    log("PRUEBA COMPLETADA")
    log(f"Archivo: {output_path}")


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        log("Prueba interrumpida manualmente.")

    except Exception as exc:
        log(
            f"ERROR: {type(exc).__name__}: {exc}"
        )
        raise