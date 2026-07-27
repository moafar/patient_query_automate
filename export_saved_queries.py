import csv
import io
import json
import re
import time
from datetime import datetime
from pathlib import Path

import win32clipboard
from pywinauto import Desktop
from pywinauto.keyboard import send_keys


# =============================================================================
# CONFIGURACIÓN
# =============================================================================

MAIN_WINDOW_TITLE = "Consultar paciente"
FIELDS_WINDOW_TITLE = "Seleccione campos de resultados de la consulta"

OUTPUT_FILE = Path("patient_query_saved_queries.json")

WINDOW_TIMEOUT = 30
QUERY_CHANGE_DELAY = 1.0
FIELDS_WINDOW_DELAY = 0.8
CLIPBOARD_DELAY = 0.8

# Ventana principal
QUERY_COMBO_ID = 5
SELECT_FIELDS_BUTTON_ID = 25

# Ventana "Seleccione campos..."
FIELDS_CANCEL_BUTTON_ID = 6

# Clase del panel de campos seleccionados
SELECTED_FIELDS_GRID_CLASS = "MSFlexGridWndClass"


# =============================================================================
# REGISTRO
# =============================================================================

def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


# =============================================================================
# PORTAPAPELES
# =============================================================================

def clear_clipboard() -> None:
    win32clipboard.OpenClipboard()

    try:
        win32clipboard.EmptyClipboard()
    finally:
        win32clipboard.CloseClipboard()


def read_clipboard_text() -> str:
    win32clipboard.OpenClipboard()

    try:
        if win32clipboard.IsClipboardFormatAvailable(
            win32clipboard.CF_UNICODETEXT
        ):
            return win32clipboard.GetClipboardData(
                win32clipboard.CF_UNICODETEXT
            )

        if win32clipboard.IsClipboardFormatAvailable(
            win32clipboard.CF_TEXT
        ):
            value = win32clipboard.GetClipboardData(
                win32clipboard.CF_TEXT
            )

            if isinstance(value, bytes):
                return value.decode(
                    "cp1252",
                    errors="replace",
                )

            return str(value)

        return ""

    finally:
        win32clipboard.CloseClipboard()


# =============================================================================
# VENTANAS
# =============================================================================

def get_main_window():
    window = Desktop(
        backend="win32"
    ).window(
        title=MAIN_WINDOW_TITLE
    )

    window.wait(
        "visible enabled",
        timeout=WINDOW_TIMEOUT,
    )

    window.set_focus()

    return window


def get_fields_window():
    window = Desktop(
        backend="win32"
    ).window(
        title=FIELDS_WINDOW_TITLE
    )

    window.wait(
        "visible",
        timeout=WINDOW_TIMEOUT,
    )

    window.set_focus()

    return window


# =============================================================================
# CONSULTAS
# =============================================================================

def get_query_combo():
    main_window = get_main_window()

    return main_window.child_window(
        control_id=QUERY_COMBO_ID,
        class_name="ThunderRT6ComboBox",
    )


def get_saved_query_names() -> list[str]:
    query_combo = get_query_combo()
    query_names = query_combo.item_texts()

    cleaned_names = []

    for query_name in query_names:
        query_name = query_name.strip()

        if query_name and query_name not in cleaned_names:
            cleaned_names.append(query_name)

    if not cleaned_names:
        raise RuntimeError(
            "No se encontraron consultas guardadas."
        )

    return cleaned_names


def select_query(query_name: str) -> None:
    query_combo = get_query_combo()
    available_queries = query_combo.item_texts()

    if query_name not in available_queries:
        raise ValueError(
            f"No se encontró la consulta {query_name!r}."
        )

    query_combo.select(query_name)
    time.sleep(QUERY_CHANGE_DELAY)

    selected_query = query_combo.window_text()

    if selected_query != query_name:
        raise RuntimeError(
            f"No se pudo seleccionar la consulta "
            f"{query_name!r}. "
            f"Valor actual: {selected_query!r}"
        )


# =============================================================================
# VENTANA DE CAMPOS
# =============================================================================

def open_selected_fields_window() -> None:
    main_window = get_main_window()

    button = main_window.child_window(
        control_id=SELECT_FIELDS_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    )

    button.wait(
        "enabled",
        timeout=WINDOW_TIMEOUT,
    )

    button.click_input()

    fields_window = get_fields_window()

    fields_window.wait(
        "visible",
        timeout=WINDOW_TIMEOUT,
    )

    time.sleep(FIELDS_WINDOW_DELAY)


def close_selected_fields_window() -> None:
    fields_window = get_fields_window()

    cancel_button = fields_window.child_window(
        control_id=FIELDS_CANCEL_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    )

    cancel_button.wait(
        "enabled",
        timeout=WINDOW_TIMEOUT,
    )

    cancel_button.click_input()

    fields_window.wait_not(
        "visible",
        timeout=WINDOW_TIMEOUT,
    )


# =============================================================================
# EXTRACCIÓN DEL GRID
# =============================================================================

def normalize_clipboard_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.strip()

    return text


def copy_selected_fields_grid() -> str:
    """
    Intenta copiar todo el contenido del MSFlexGrid.

    La tabla no expone sus celdas directamente mediante UIA,
    por lo que se utiliza la selección y copia al portapapeles.
    """
    fields_window = get_fields_window()

    grid = fields_window.child_window(
        class_name=SELECTED_FIELDS_GRID_CLASS,
    )

    grid.wait(
        "visible enabled",
        timeout=WINDOW_TIMEOUT,
    )

    clear_clipboard()

    grid.set_focus()
    grid.click_input()

    time.sleep(0.3)

    # Intento principal: seleccionar y copiar toda la cuadrícula.
    send_keys("^a")
    time.sleep(0.2)
    send_keys("^c")

    time.sleep(CLIPBOARD_DELAY)

    text = normalize_clipboard_text(
        read_clipboard_text()
    )

    if text:
        return text

    # Segundo intento: posicionar en el inicio antes de copiar.
    clear_clipboard()

    grid.set_focus()
    grid.click_input()

    send_keys("^{HOME}")
    time.sleep(0.2)
    send_keys("^a")
    time.sleep(0.2)
    send_keys("^c")

    time.sleep(CLIPBOARD_DELAY)

    text = normalize_clipboard_text(
        read_clipboard_text()
    )

    if not text:
        raise RuntimeError(
            "No se pudo copiar el contenido del panel "
            "'Campos seleccionados'."
        )

    return text


# =============================================================================
# INTERPRETACIÓN DEL CONTENIDO
# =============================================================================

def split_row(line: str) -> list[str]:
    """
    Divide una fila copiada desde el grid.

    Normalmente MSFlexGrid copia las columnas separadas por tabuladores.
    Se conserva una alternativa para varios espacios consecutivos.
    """
    if "\t" in line:
        return [
            value.strip()
            for value in line.split("\t")
        ]

    return [
        value.strip()
        for value in re.split(r"\s{2,}", line.strip())
    ]


def parse_selected_fields(
    clipboard_text: str,
) -> tuple[list[dict], list[str]]:
    lines = [
        line
        for line in clipboard_text.splitlines()
        if line.strip()
    ]

    if not lines:
        return [], []

    parsed_rows = [
        split_row(line)
        for line in lines
    ]

    possible_headers = {
        "nombre de la tabla",
        "nombre de la tab",
        "table name",
    }

    first_value = (
        parsed_rows[0][0].strip().lower()
        if parsed_rows[0]
        else ""
    )

    if first_value in possible_headers:
        parsed_rows = parsed_rows[1:]

    fields = []

    for position, row in enumerate(
        parsed_rows,
        start=1,
    ):
        padded_row = row + ["", "", ""]

        table_name = padded_row[0].strip()
        field_name = padded_row[1].strip()
        units = padded_row[2].strip()

        # Evita filas completamente vacías.
        if not any(
            [table_name, field_name, units]
        ):
            continue

        fields.append(
            {
                "position": position,
                "table": table_name,
                "field": field_name,
                "units": units,
                "raw_columns": row,
            }
        )

    return fields, lines


# =============================================================================
# JSON
# =============================================================================

def save_json(data: dict) -> None:
    """
    Sobrescribe siempre el archivo anterior.

    Se ejecuta después de cada consulta para conservar un punto
    de recuperación si el proceso se interrumpe.
    """
    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


# =============================================================================
# PROGRAMA PRINCIPAL
# =============================================================================

def main() -> None:
    log("Inicio de exploración de consultas guardadas")

    main_window = get_main_window()
    query_combo = get_query_combo()

    original_query = query_combo.window_text()
    query_names = get_saved_query_names()

    log(
        f"Consultas encontradas: {len(query_names)}"
    )

    output_data = {
        "source": "Patient Query",
        "captured_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "query_count": len(query_names),
        "queries": [],
        "errors": [],
    }

    # Borra el JSON anterior desde el inicio.
    save_json(output_data)

    try:
        for query_number, query_name in enumerate(
            query_names,
            start=1,
        ):
            log(
                f"Consulta {query_number}/"
                f"{len(query_names)}: {query_name}"
            )

            fields_window_open = False

            try:
                select_query(query_name)

                open_selected_fields_window()
                fields_window_open = True

                clipboard_text = (
                    copy_selected_fields_grid()
                )

                fields, raw_lines = (
                    parse_selected_fields(
                        clipboard_text
                    )
                )

                output_data["queries"].append(
                    {
                        "query_name": query_name,
                        "selected_field_count": len(fields),
                        "selected_fields": fields,
                        "raw_grid_text": clipboard_text,
                        "raw_grid_lines": raw_lines,
                    }
                )

                log(
                    f"Campos recuperados: {len(fields)}"
                )

            except Exception as exc:
                error = {
                    "query_name": query_name,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }

                output_data["errors"].append(
                    error
                )

                log(
                    f"ERROR en {query_name!r}: "
                    f"{type(exc).__name__}: {exc}"
                )

            finally:
                if fields_window_open:
                    try:
                        close_selected_fields_window()
                    except Exception as close_exc:
                        log(
                            "No se pudo cerrar la ventana "
                            f"con Cancelar: {close_exc}"
                        )

                # Guarda un punto de recuperación.
                save_json(output_data)

        output_data["completed_at"] = (
            datetime.now().isoformat(
                timespec="seconds"
            )
        )

        output_data["successful_query_count"] = len(
            output_data["queries"]
        )

        output_data["error_count"] = len(
            output_data["errors"]
        )

        save_json(output_data)

    finally:
        # Restaurar la consulta que estaba seleccionada al iniciar.
        if (
            original_query
            and original_query in query_names
        ):
            try:
                select_query(original_query)

                log(
                    "Consulta original restaurada: "
                    f"{original_query}"
                )

            except Exception as exc:
                log(
                    "No se pudo restaurar la consulta "
                    f"original: {exc}"
                )

    log("Exploración terminada")
    log(
        f"JSON generado: {OUTPUT_FILE.resolve()}"
    )


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        log("Proceso interrumpido manualmente.")

    except Exception as exc:
        log(
            f"ERROR GENERAL: "
            f"{type(exc).__name__}: {exc}"
        )

        raise