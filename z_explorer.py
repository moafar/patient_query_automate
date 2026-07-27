import time
from datetime import datetime
from pathlib import Path

from pywinauto import Desktop


WINDOW_TITLE = "Seleccione campos de resultados de la consulta"

TABLE_COMBO_ID = 4
FIELD_COMBO_ID = 5
ADD_BUTTON_ID = 10

TABLE_CHANGE_DELAY = 0.4
FIELD_CHANGE_DELAY = 0.08
AFTER_ADD_DELAY = 0.08

LOG_FILE = Path("agregar_todos_los_campos.log")


def write_log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"

    print(line)

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def get_window():
    desktop = Desktop(backend="win32")

    window = desktop.window(title=WINDOW_TITLE)
    window.wait("visible", timeout=10)
    window.set_focus()

    return window


def main():
    # Borra el registro de la ejecución anterior.
    LOG_FILE.write_text("", encoding="utf-8")

    window = get_window()

    table_combo = window.child_window(
        control_id=TABLE_COMBO_ID,
        class_name="ThunderRT6ComboBox",
    )

    field_combo = window.child_window(
        control_id=FIELD_COMBO_ID,
        class_name="ThunderRT6ComboBox",
    )

    add_button = window.child_window(
        control_id=ADD_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    )

    table_names = table_combo.item_texts()

    if not table_names:
        raise RuntimeError(
            "No se encontraron conjuntos en el desplegable superior."
        )

    write_log(f"Conjuntos encontrados: {len(table_names)}")

    total_fields = 0
    total_added = 0
    total_skipped = 0
    total_errors = 0

    for table_number, table_name in enumerate(table_names, start=1):
        write_log(
            f"CONJUNTO {table_number}/{len(table_names)}: {table_name}"
        )

        try:
            table_combo.select(table_name)
            time.sleep(TABLE_CHANGE_DELAY)

            selected_table = table_combo.window_text()

            if selected_table != table_name:
                raise RuntimeError(
                    f"Se esperaba {table_name!r}, "
                    f"pero quedó seleccionado {selected_table!r}."
                )

            field_names = field_combo.item_texts()

        except Exception as exc:
            total_errors += 1
            write_log(
                f"ERROR leyendo el conjunto {table_name!r}: {exc}"
            )
            continue

        write_log(
            f"Variables encontradas en {table_name}: {len(field_names)}"
        )

        total_fields += len(field_names)

        for field_number, field_name in enumerate(field_names, start=1):
            prefix = (
                f"{table_number}/{len(table_names)} | "
                f"{field_number}/{len(field_names)}"
            )

            try:
                field_combo.select(field_name)
                time.sleep(FIELD_CHANGE_DELAY)

                selected_field = field_combo.window_text()

                if selected_field != field_name:
                    raise RuntimeError(
                        f"Se esperaba {field_name!r}, "
                        f"pero quedó seleccionado {selected_field!r}."
                    )

                if not add_button.is_enabled():
                    total_skipped += 1
                    write_log(
                        f"{prefix} OMITIDA: "
                        f"{table_name} > {field_name}"
                    )
                    continue

                add_button.click()
                time.sleep(AFTER_ADD_DELAY)

                total_added += 1
                write_log(
                    f"{prefix} AGREGADA: "
                    f"{table_name} > {field_name}"
                )

            except Exception as exc:
                total_errors += 1
                write_log(
                    f"{prefix} ERROR: "
                    f"{table_name} > {field_name}: {exc}"
                )

    write_log("=" * 80)
    write_log("PROCESO TERMINADO")
    write_log(f"Conjuntos procesados: {len(table_names)}")
    write_log(f"Variables recorridas: {total_fields}")
    write_log(f"Variables agregadas: {total_added}")
    write_log(f"Variables omitidas: {total_skipped}")
    write_log(f"Errores: {total_errors}")
    write_log(f"Registro: {LOG_FILE.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        write_log("Proceso interrumpido manualmente.")