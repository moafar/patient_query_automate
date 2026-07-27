from pathlib import Path

from pywinauto import Desktop


WINDOW_TITLE = "Consultar paciente"
OUTPUT_FILE = Path("filtros_win32.txt")


def main():
    desktop = Desktop(backend="win32")

    window = desktop.window(title=WINDOW_TITLE)
    window.wait("visible", timeout=10)
    window.set_focus()

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        file.write(f"Ventana: {window.window_text()}\n")
        file.write(f"Clase: {window.class_name()}\n")
        file.write("=" * 100 + "\n")

        for index, control in enumerate(window.descendants()):
            try:
                control_id = control.control_id()
                rect = control.rectangle()

                # Controles vinculados a las filas de filtros.
                if 26 <= control_id <= 49:
                    file.write(f"\nCONTROL {index}\n")
                    file.write(f"Control ID: {control_id}\n")
                    file.write(f"Texto: {control.window_text()!r}\n")
                    file.write(f"Clase: {control.class_name()!r}\n")
                    file.write(f"Visible: {control.is_visible()}\n")
                    file.write(f"Habilitado: {control.is_enabled()}\n")
                    file.write(f"Rectángulo: {rect}\n")

            except Exception as exc:
                file.write(f"\nError leyendo control {index}: {exc}\n")

    print(f"Resultado guardado en: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()