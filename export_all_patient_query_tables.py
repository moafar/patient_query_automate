import re
import time
from datetime import datetime
from pathlib import Path

from pywinauto import Desktop
from pywinauto.keyboard import send_keys


# =============================================================================
# CONFIGURACIÓN
# =============================================================================

QUERY_NAME = "__OBS_test"

# Patient Query interpreta esta fecha como MM/DD/YYYY.
FILTER_DATE = "06/01/2026"

EXPORT_DIR = Path(r"C:\patient_query_automate\exports")

MAIN_WINDOW_TITLE = "Consultar paciente"
FIELDS_WINDOW_TITLE = "Seleccione campos de resultados de la consulta"

WINDOW_TIMEOUT = 30
SAVE_DIALOG_TIMEOUT = 60
EXPORT_TIMEOUT = 600

CONTROL_DELAY = 0.35
TABLE_CHANGE_DELAY = 0.8
SAVE_QUERY_DELAY = 2
EXPORT_START_DELAY = 1

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
FIELDS_CANCEL_BUTTON_ID = 6
FIELDS_ACCEPT_BUTTON_ID = 7
FIELDS_CLEAR_ALL_BUTTON_ID = 8
FIELDS_ADD_BUTTON_ID = 10

EXCLUDED_FIELDS = {
    ("Demographic", "Ideal Body Weight With Units"),
    ("Demographic", "Requested On"),
    ("Demographic", "SSN"),
    ("Demographic", "Strap RAW Test"),
    ("Demographic", "Strap TGV Test"),
    ("Demographic", "SVC Test"),
    ("Demographic", "Syringe Flag"),

    ("GX AT", "IC (L)"),
}


# =============================================================================
# REGISTRO
# =============================================================================

def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def timestamp_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sanitize_filename(value: str) -> str:
    """
    Elimina caracteres no permitidos en nombres de archivo de Windows.
    """
    value = re.sub(r'[<>:"/\\|?*]', "_", value)
    value = value.strip().rstrip(".")

    return value or "sin_nombre"


# =============================================================================
# VENTANAS
# =============================================================================

def get_main_window_win32():
    window = Desktop(backend="win32").window(
        title=MAIN_WINDOW_TITLE
    )

    window.wait(
        "visible enabled",
        timeout=WINDOW_TIMEOUT,
    )

    window.set_focus()

    return window


def get_main_window_uia():
    window = Desktop(backend="uia").window(
        title=MAIN_WINDOW_TITLE
    )

    window.wait(
        "visible",
        timeout=WINDOW_TIMEOUT,
    )

    return window


def get_fields_window():
    window = Desktop(backend="win32").window(
        title=FIELDS_WINDOW_TITLE
    )

    window.wait(
        "visible",
        timeout=WINDOW_TIMEOUT,
    )

    window.set_focus()

    return window


# =============================================================================
# UTILIDADES DE CONTROLES
# =============================================================================

def select_combo_value(
    combo,
    value: str,
    label: str,
) -> None:
    """
    Selecciona un valor de un ComboBox y verifica el resultado.
    """
    available_values = combo.item_texts()

    if value not in available_values:
        raise ValueError(
            f"No se encontró {value!r} en {label}. "
            f"Valores disponibles: {available_values}"
        )

    combo.select(value)
    time.sleep(CONTROL_DELAY)

    selected_value = combo.window_text()

    if selected_value != value:
        raise RuntimeError(
            f"No se pudo seleccionar {value!r} en {label}. "
            f"Valor actual: {selected_value!r}"
        )


def get_value_edits(window):
    """
    Localiza los controles Edit de la columna Valores.

    La estrategia es la misma que funcionó en el script de prueba:
    seleccionar los campos Edit visibles situados más a la derecha.
    """
    edits = window.descendants(
        control_type="Edit"
    )

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


# =============================================================================
# CONSULTA
# =============================================================================

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


def save_query_changes() -> None:
    window = get_main_window_win32()

    save_button = window.child_window(
        control_id=SAVE_QUERY_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    )

    save_button.wait(
        "enabled",
        timeout=WINDOW_TIMEOUT,
    )

    save_button.click_input()

    time.sleep(SAVE_QUERY_DELAY)

    log("Cambios de la consulta guardados")


# =============================================================================
# VENTANA DE SELECCIÓN DE CAMPOS
# =============================================================================

def open_select_fields() -> None:
    main_window = get_main_window_win32()

    button = main_window.child_window(
        control_id=SELECT_FIELDS_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    )

    button.wait(
        "enabled",
        timeout=WINDOW_TIMEOUT,
    )

    button.click_input()

    get_fields_window()

    log("Ventana de selección de campos abierta")


def get_fields_controls():
    window = get_fields_window()

    return {
        "window": window,
        "table_combo": window.child_window(
            control_id=FIELDS_TABLE_COMBO_ID,
            class_name="ThunderRT6ComboBox",
        ),
        "field_combo": window.child_window(
            control_id=FIELDS_FIELD_COMBO_ID,
            class_name="ThunderRT6ComboBox",
        ),
        "cancel_button": window.child_window(
            control_id=FIELDS_CANCEL_BUTTON_ID,
            class_name="ThunderRT6CommandButton",
        ),
        "accept_button": window.child_window(
            control_id=FIELDS_ACCEPT_BUTTON_ID,
            class_name="ThunderRT6CommandButton",
        ),
        "clear_all_button": window.child_window(
            control_id=FIELDS_CLEAR_ALL_BUTTON_ID,
            class_name="ThunderRT6CommandButton",
        ),
        "add_button": window.child_window(
            control_id=FIELDS_ADD_BUTTON_ID,
            class_name="ThunderRT6CommandButton",
        ),
    }


def clear_selected_fields() -> None:
    controls = get_fields_controls()
    clear_button = controls["clear_all_button"]

    if clear_button.is_enabled():
        clear_button.click_input()
        time.sleep(CONTROL_DELAY)

        log("Lista de campos seleccionados limpiada")
    else:
        log("La lista de campos seleccionados ya estaba vacía")


def get_all_table_names() -> list[str]:
    controls = get_fields_controls()

    table_names = controls["table_combo"].item_texts()

    if not table_names:
        raise RuntimeError(
            "No se encontraron tablas en el desplegable superior."
        )

    return table_names


def select_fields_table(
    table_name: str,
) -> list[str]:
    controls = get_fields_controls()

    table_combo = controls["table_combo"]
    field_combo = controls["field_combo"]

    select_combo_value(
        combo=table_combo,
        value=table_name,
        label="el desplegable de tablas",
    )

    time.sleep(TABLE_CHANGE_DELAY)

    selected_table = table_combo.window_text()

    if selected_table != table_name:
        raise RuntimeError(
            f"No se pudo seleccionar la tabla {table_name!r}. "
            f"Valor actual: {selected_table!r}"
        )

    field_names = field_combo.item_texts()

    if not field_names:
        raise RuntimeError(
            f"No se encontraron campos para la tabla {table_name!r}."
        )

    return field_names


def add_field(
    table_name: str,
    field_name: str,
) -> None:
    controls = get_fields_controls()

    table_combo = controls["table_combo"]
    field_combo = controls["field_combo"]
    add_button = controls["add_button"]

    if table_combo.window_text() != table_name:
        select_combo_value(
            combo=table_combo,
            value=table_name,
            label="el desplegable de tablas",
        )

        time.sleep(TABLE_CHANGE_DELAY)

    available_fields = field_combo.item_texts()

    if field_name not in available_fields:
        raise ValueError(
            f"El campo {field_name!r} no existe "
            f"en la tabla {table_name!r}."
        )

    field_combo.select(field_name)
    time.sleep(CONTROL_DELAY)

    selected_field = field_combo.window_text()

    if selected_field != field_name:
        raise RuntimeError(
            f"No se pudo seleccionar "
            f"{table_name} > {field_name}. "
            f"Valor actual: {selected_field!r}"
        )

    if not add_button.is_enabled():
        raise RuntimeError(
            f"El botón > está deshabilitado para "
            f"{table_name} > {field_name}."
        )

    add_button.click_input()
    time.sleep(CONTROL_DELAY)


def add_all_fields_from_table(
    table_name: str,
) -> int:
    field_names = select_fields_table(table_name)

    included_fields = [
        field_name
        for field_name in field_names
        if (table_name, field_name) not in EXCLUDED_FIELDS
    ]

    excluded_count = len(field_names) - len(included_fields)

    log(
        f"Agregando {len(included_fields)} campos "
        f"de la tabla {table_name!r}"
    )

    if excluded_count:
        log(
            f"Campos excluidos de {table_name}: "
            f"{excluded_count}"
        )

    for position, field_name in enumerate(
        included_fields,
        start=1,
    ):
        log(
            f"{table_name}: campo "
            f"{position}/{len(included_fields)}: "
            f"{field_name}"
        )

        add_field(
            table_name=table_name,
            field_name=field_name,
        )

    return len(included_fields)


def accept_selected_fields() -> None:
    controls = get_fields_controls()

    fields_window = controls["window"]
    accept_button = controls["accept_button"]

    if not accept_button.is_enabled():
        raise RuntimeError(
            "El botón Aceptar está deshabilitado. "
            "Puede que no haya campos seleccionados."
        )

    accept_button.click_input()

    fields_window.wait_not(
        "visible",
        timeout=WINDOW_TIMEOUT,
    )

    log("Selección de campos aceptada")


def cancel_fields_window() -> None:
    controls = get_fields_controls()

    fields_window = controls["window"]
    cancel_button = controls["cancel_button"]

    cancel_button.click_input()

    fields_window.wait_not(
        "visible",
        timeout=WINDOW_TIMEOUT,
    )

    log("Ventana de selección de campos cerrada")


# =============================================================================
# FILTRO
# =============================================================================

def configure_first_filter() -> None:
    """
    Configura la primera fila del filtro:

    Demographic > Visit Date = 06/23/2026
    """
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
        value=">=",
        label="el operador de la primera fila del filtro",
    )

    time.sleep(CONTROL_DELAY)

    log(
        "Tabla, campo y operador del filtro configurados"
    )

    # El campo de fecha se localiza dinámicamente mediante UIA.
    window_uia = get_main_window_uia()

    value_edits = get_value_edits(
        window_uia
    )

    if not value_edits:
        raise RuntimeError(
            "No se encontraron campos visibles "
            "en la columna Valores."
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

    log(
        f"Valor leído en el filtro: "
        f"{current_value!r}"
    )

    if current_value != FILTER_DATE:
        raise RuntimeError(
            "La fecha no quedó configurada correctamente. "
            f"Esperada: {FILTER_DATE!r}. "
            f"Actual: {current_value!r}"
        )

    log(
        "Filtro configurado: "
        f"Demographic > Visit Date = {FILTER_DATE}"
    )


# =============================================================================
# DIÁLOGO DE GUARDADO
# =============================================================================

def wait_for_save_dialog():
    desktop = Desktop(backend="uia")

    save_window = desktop.window(
        title_re=(
            r".*(Guardar resultados de la consulta como"
            r"|Guardar como"
            r"|Save As).*"
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

    # Alt+N enfoca File name / Nombre de archivo.
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
    """
    Intenta seleccionar XLS explícitamente.

    Si no encuentra el control, conserva el tipo actual.
    La extensión .xls ya ha funcionado correctamente en la prueba.
    """
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
            "No se pudo seleccionar explícitamente "
            "el tipo XLS; se conserva el valor actual."
        )


def confirm_save_dialog(
    save_window,
) -> None:
    try:
        save_button = save_window.child_window(
            title="Save",
            control_type="Button",
        )

        save_button.wait(
            "enabled",
            timeout=5,
        )

        save_button.click_input()

        return

    except Exception:
        pass

    save_button = save_window.child_window(
        title="Guardar",
        control_type="Button",
    )

    save_button.wait(
        "enabled",
        timeout=5,
    )

    save_button.click_input()


def handle_overwrite_dialog() -> None:
    """
    Confirma sobrescritura si apareciera un diálogo.
    """
    desktop = Desktop(backend="uia")

    possible_titles = [
        "Confirm Save As",
        "Confirmar Guardar como",
        "Confirmar guardado",
    ]

    for title in possible_titles:
        try:
            dialog = desktop.window(
                title=title
            )

            dialog.wait(
                "visible",
                timeout=2,
            )

            for button_title in [
                "Yes",
                "Sí",
                "Si",
            ]:
                try:
                    button = dialog.child_window(
                        title=button_title,
                        control_type="Button",
                    )

                    button.click_input()

                    log(
                        "Sobrescritura de archivo confirmada"
                    )

                    return

                except Exception:
                    continue

        except Exception:
            continue


# =============================================================================
# ESPERA DEL ARCHIVO
# =============================================================================

def wait_for_file_to_finish(
    file_path: Path,
    timeout: int = EXPORT_TIMEOUT,
    stable_checks_required: int = 3,
) -> None:
    """
    Espera hasta que el archivo exista y su tamaño permanezca estable.
    """
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

            if stable_checks >= stable_checks_required:
                log(
                    f"Archivo terminado: {file_path} "
                    f"({current_size:,} bytes)"
                )

                return

        time.sleep(1)

    raise TimeoutError(
        "El archivo no terminó de guardarse "
        f"dentro de {timeout} segundos: {file_path}"
    )


# =============================================================================
# EXPORTACIÓN
# =============================================================================

def export_current_query(
    table_name: str,
) -> Path:
    main_window = get_main_window_win32()

    export_button = main_window.child_window(
        control_id=EXPORT_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    )

    export_button.wait(
        "enabled",
        timeout=WINDOW_TIMEOUT,
    )

    EXPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_table_name = sanitize_filename(
        table_name
    )

    filename = (
        f"{QUERY_NAME}_"
        f"{safe_table_name}_"
        f"{timestamp_str()}.xls"
    )

    full_path = EXPORT_DIR / filename

    log(
        f"Iniciando exportación de {table_name}"
    )

    export_button.click_input()
    time.sleep(EXPORT_START_DELAY)

    save_window = wait_for_save_dialog()

    set_save_dialog_filename(
        save_window=save_window,
        full_path=full_path,
    )

    set_save_dialog_file_type_excel(
        save_window
    )

    confirm_save_dialog(
        save_window
    )

    time.sleep(1)

    handle_overwrite_dialog()

    log(
        f"Guardado solicitado: {full_path}"
    )

    wait_for_file_to_finish(
        full_path
    )

    return full_path


# =============================================================================
# PROCESAMIENTO DE TABLAS
# =============================================================================

def process_demographic() -> Path:
    """
    Exporta todos los campos de Demographic.
    """
    log("=" * 80)
    log("Procesando tabla inicial: Demographic")

    open_select_fields()
    clear_selected_fields()

    add_all_fields_from_table(
        "Demographic"
    )

    accept_selected_fields()

    configure_first_filter()
    save_query_changes()

    return export_current_query(
        "Demographic"
    )


def process_additional_table(
    table_name: str,
) -> Path:
    """
    Exporta:

    Demographic > ID
    Demographic > Visit Date
    todos los campos de la tabla indicada
    """
    log("=" * 80)
    log(f"Procesando tabla: {table_name}")

    open_select_fields()
    clear_selected_fields()

    log(
        "Agregando identificadores de Demographic"
    )

    add_field(
        table_name="Demographic",
        field_name="ID",
    )

    add_field(
        table_name="Demographic",
        field_name="Visit Date",
    )

    add_all_fields_from_table(
        table_name
    )

    accept_selected_fields()

    configure_first_filter()
    save_query_changes()

    return export_current_query(
        table_name
    )


# =============================================================================
# PROGRAMA PRINCIPAL
# =============================================================================

def main() -> None:
    log("Inicio del proceso")
    log(f"Consulta: {QUERY_NAME}")
    log(f"Fecha del filtro: {FILTER_DATE}")
    log(f"Directorio de exportación: {EXPORT_DIR}")

    select_query()

    # Abrir una vez para obtener el catálogo de tablas.
    open_select_fields()

    table_names = get_all_table_names()

    if "Demographic" not in table_names:
        raise RuntimeError(
            "No se encontró la tabla 'Demographic'."
        )

    cancel_fields_window()

    log(
        f"Tablas encontradas: {len(table_names)}"
    )

    exported_files: list[Path] = []

    # Primera exportación.
    demographic_file = process_demographic()

    exported_files.append(
        demographic_file
    )

    # Resto de tablas.
    remaining_tables = [
        table_name
        for table_name in table_names
        if table_name != "Demographic"
    ]

    total_remaining = len(
        remaining_tables
    )

    for position, table_name in enumerate(
        remaining_tables,
        start=1,
    ):
        log(
            f"Tabla adicional "
            f"{position}/{total_remaining}: "
            f"{table_name}"
        )

        exported_file = process_additional_table(
            table_name
        )

        exported_files.append(
            exported_file
        )

    log("=" * 80)
    log("PROCESO COMPLETADO")
    log(
        f"Archivos exportados: "
        f"{len(exported_files)}"
    )

    for file_path in exported_files:
        log(str(file_path))


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        log(
            "Proceso interrumpido manualmente."
        )

    except Exception as exc:
        log(
            f"ERROR: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        raise