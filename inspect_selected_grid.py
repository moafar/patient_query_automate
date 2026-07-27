from pathlib import Path

from pywinauto import Desktop


MAIN_WINDOW_TITLE = "Consultar paciente"
FIELDS_WINDOW_TITLE = "Seleccione campos de resultados de la consulta"

OUTPUT_FILE = Path("selected_grid_descendants.txt")

SELECT_FIELDS_BUTTON_ID = 25
CANCEL_BUTTON_ID = 6
GRID_CLASS = "MSFlexGridWndClass"


def safe(callable_obj, default="NO DISPONIBLE"):
    try:
        return callable_obj()
    except Exception as exc:
        return f"{default}: {type(exc).__name__}: {exc}"


def main():
    desktop_win32 = Desktop(backend="win32")

    main_window = desktop_win32.window(
        title=MAIN_WINDOW_TITLE
    )
    main_window.wait("visible enabled", timeout=20)
    main_window.set_focus()

    main_window.child_window(
        control_id=SELECT_FIELDS_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    ).click_input()

    fields_window_win32 = desktop_win32.window(
        title=FIELDS_WINDOW_TITLE
    )
    fields_window_win32.wait("visible", timeout=20)

    grid_win32 = fields_window_win32.child_window(
        class_name=GRID_CLASS
    )
    grid_win32.wait("visible", timeout=20)

    grid_rect = grid_win32.rectangle()

    desktop_uia = Desktop(backend="uia")

    main_window_uia = desktop_uia.window(
        title=MAIN_WINDOW_TITLE
    )
    main_window_uia.wait("visible", timeout=20)

    grid_uia = None

    for control in main_window_uia.descendants():
        try:
            rect = control.rectangle()
            info = control.element_info

            if (
                info.class_name == GRID_CLASS
                and abs(rect.left - grid_rect.left) <= 5
                and abs(rect.top - grid_rect.top) <= 5
                and abs(rect.right - grid_rect.right) <= 5
                and abs(rect.bottom - grid_rect.bottom) <= 5
            ):
                grid_uia = control
                break
        except Exception:
            continue

    if grid_uia is None:
        raise RuntimeError(
            "No se encontró el grid mediante UI Automation."
        )

    descendants = grid_uia.descendants()

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        file.write("DESCENDIENTES UIA DEL GRID\n")
        file.write("=" * 100 + "\n")
        file.write(f"Total: {len(descendants)}\n\n")

        for index, control in enumerate(descendants, start=1):
            info = control.element_info

            file.write("-" * 100 + "\n")
            file.write(f"CONTROL {index}\n")
            file.write(f"Nombre: {safe(control.window_text)!r}\n")
            file.write(f"Tipo: {info.control_type!r}\n")
            file.write(f"Clase: {info.class_name!r}\n")
            file.write(f"Auto ID: {info.automation_id!r}\n")
            file.write(f"Rectángulo: {safe(control.rectangle)}\n")
            file.write(f"Visible: {safe(control.is_visible)}\n")
            file.write(f"Habilitado: {safe(control.is_enabled)}\n")
            file.write(
                f"Descendientes: "
                f"{safe(lambda: len(control.descendants()))}\n"
            )

            file.write(
                f"Textos: {safe(control.texts)!r}\n"
            )

            try:
                file.write(
                    f"Valor UIA: "
                    f"{control.iface_value.CurrentValue!r}\n"
                )
            except Exception as exc:
                file.write(
                    f"Valor UIA: no disponible: {exc}\n"
                )

            try:
                file.write(
                    f"Nombre accesible: "
                    f"{control.element_info.name!r}\n"
                )
            except Exception as exc:
                file.write(
                    f"Nombre accesible: no disponible: {exc}\n"
                )

    fields_window_win32.child_window(
        control_id=CANCEL_BUTTON_ID,
        class_name="ThunderRT6CommandButton",
    ).click_input()

    print(
        f"Resultado guardado en: {OUTPUT_FILE.resolve()}"
    )


if __name__ == "__main__":
    main()