# Patient Query Automate

Automatización de la extracción de datos desde **Patient Query de Breeze** mediante la interfaz gráfica de Windows.

El proyecto utiliza Python y `pywinauto` para:

1. Abrir Patient Query.
2. Iniciar sesión.
3. Esperar la actualización inicial de la base de datos.
4. Seleccionar una consulta configurada.
5. Aplicar un filtro de fecha sobre `Visit Date`.
6. Guardar los cambios de la consulta.
7. Exportar los resultados en formato Excel `.xls`.
8. Cerrar Patient Query al finalizar.

## Requisitos

* Windows Server o Windows de 64 bits.
* Patient Query de Breeze instalado.
* Python 3.12 o compatible.
* Acceso interactivo al escritorio de Windows.
* Sesión de usuario abierta durante la ejecución.

La automatización controla elementos visibles de la interfaz. Por tanto, no está diseñada para ejecutarse con la sesión de Windows cerrada o desconectada de forma que la interfaz deje de estar disponible.

## Aplicación automatizada

Ruta utilizada actualmente:

```text
C:\Program Files (x86)\MedGraphics\Breeze\DatabaseQuery.exe
```

## Estructura del proyecto

```text
patient_query_automate/
├── config/
│   └── extractors.yaml
├── exports/
├── .env
├── .gitignore
├── main.py
├── requirements.txt
└── README.md
```

## Instalación

Crear el entorno virtual:

```powershell
python -m venv .venv
```

Activarlo:

```powershell
.\.venv\Scripts\Activate.ps1
```

Instalar las dependencias:

```powershell
python -m pip install -r requirements.txt
```

## Dependencias

El archivo `requirements.txt` contiene:

```text
pywinauto
python-dotenv
pyyaml
pandas
openpyxl
xlrd
```

`xlrd` se utiliza para leer posteriormente los archivos Excel antiguos con extensión `.xls`.

## Credenciales

Las credenciales se almacenan en un archivo `.env` ubicado en la raíz del proyecto:

```env
PATIENT_QUERY_USERNAME=admin
PATIENT_QUERY_PASSWORD=CONTRASEÑA
```

El archivo `.env` está excluido del repositorio mediante `.gitignore`.

No se deben guardar credenciales directamente en `main.py`, `extractors.yaml` ni en archivos versionados.

## Configuración de extractores

Los extractores se definen en:

```text
config/extractors.yaml
```

Configuración actual:

```yaml
extractors:
  observatorio_dlco:
    query_name: "OBSERVATORIO-DLCO"
    visit_date_from: "12/06/2026"

  observatorio_espirometria:
    query_name: "OBSERVATORIO-ESPIROMETRIA"
    visit_date_from: "12/06/2026"

  observatorio_volumenes_pulmonares:
    query_name: "OBSERVATORIO-VOLUMENES PULMONARES"
    visit_date_from: "12/06/2026"
```

Durante las pruebas se utiliza una fecha fija.

Para calcular automáticamente la fecha del día anterior:

```yaml
visit_date_from: "yesterday"
```

## Extractores disponibles

### OBSERVATORIO-DLCO

```powershell
python main.py --extractor observatorio_dlco
```

### OBSERVATORIO-ESPIROMETRIA

```powershell
python main.py --extractor observatorio_espirometria
```

### OBSERVATORIO-VOLUMENES PULMONARES

```powershell
python main.py --extractor observatorio_volumenes_pulmonares
```

## Archivos exportados

Los archivos se guardan en:

```text
exports/
```

El nombre sigue este patrón:

```text
CONSULTA_DDMMYYYY_HHMM.xls
```

Ejemplos:

```text
OBSERVATORIO-DLCO_15062026_0924.xls
OBSERVATORIO-ESPIROMETRIA_15062026_0940.xls
OBSERVATORIO-VOLUMENES PULMONARES_15062026_0955.xls
```

La exportación se realiza como:

```text
Microsoft Excel 97-2003 Worksheet (*.xls)
```

Se prefiere XLS frente a CSV porque las consultas pueden contener textos clínicos, nombres, comas y saltos de línea que podrían alterar la estructura del archivo CSV.

## Flujo de ejecución

El programa realiza estas operaciones:

```text
Lanzar Patient Query
        ↓
Esperar ventana "Iniciar sesión"
        ↓
Introducir usuario y contraseña
        ↓
Esperar actualización de la base de datos
        ↓
Esperar ventana "Consultar paciente"
        ↓
Seleccionar consulta
        ↓
Definir Visit Date >= fecha configurada
        ↓
Pulsar "Guardar"
        ↓
Esperar 2 segundos
        ↓
Pulsar "Exportar"
        ↓
Definir nombre y tipo XLS
        ↓
Pulsar "Save"
        ↓
Pulsar "Salir"
```

## Consideraciones técnicas

La aplicación se automatiza con:

```python
Desktop(backend="uia")
```

Patient Query expone parcialmente sus controles mediante Windows UI Automation. Algunos controles son sensibles al estado de la interfaz, por lo que el programa combina:

* selección por controles UIA;
* identificación por título;
* identificación por posición;
* escritura mediante teclado;
* tiempos de espera entre acciones.

La ventana de actualización inicial puede tardar aproximadamente cinco minutos.

El tiempo máximo de espera configurado actualmente es de diez minutos.

## Incorporar un nuevo extractor

Agregar una entrada en `config/extractors.yaml`:

```yaml
extractors:
  nuevo_extractor:
    query_name: "NOMBRE-EXACTO-DE-LA-CONSULTA"
    visit_date_from: "yesterday"
```

Después ejecutar:

```powershell
python main.py --extractor nuevo_extractor
```

El valor de `query_name` debe coincidir exactamente con el nombre mostrado en Patient Query.

## Lectura del archivo exportado con pandas

Para archivos `.xls`:

```python
import pandas as pd

df = pd.read_excel(
    "exports/OBSERVATORIO-DLCO_15062026_0924.xls",
    dtype=str,
)
```

Se recomienda cargar inicialmente todas las columnas como texto para evitar conversiones automáticas no deseadas.

## Seguridad

No versionar:

* `.env`;
* `.venv`;
* archivos exportados;
* credenciales;
* archivos temporales de inspección;
* datos clínicos.

Antes de publicar el repositorio, verificar:

```powershell
git status
```

El archivo `.gitignore` debe excluir al menos:

```gitignore
.venv/
.env
exports/
__pycache__/
*.py[cod]
.vscode/
control_identifiers_*.txt
login_test.py
test_select_query.py
```

## Estado actual

Los siguientes extractores han sido probados correctamente:

* `observatorio_dlco`
* `observatorio_espirometria`
* `observatorio_volumenes_pulmonares`

El flujo completo abre Patient Query, configura la consulta, exporta el archivo XLS y cierra la aplicación.
