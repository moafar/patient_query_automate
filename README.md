# Patient Query Automate

Automatización de la extracción de datos desde **Patient Query de Breeze** mediante la interfaz gráfica de Windows.

El proyecto utiliza Python y `pywinauto` para abrir Patient Query, iniciar sesión, seleccionar una consulta configurada, aplicar un filtro de fecha, exportar los resultados en formato `.xls` y cerrar la aplicación.

## Requisitos

- Windows Server o Windows de 64 bits.
- Patient Query de Breeze instalado.
- Python 3.12 o compatible.
- Acceso interactivo al escritorio de Windows.
- Sesión de usuario abierta durante la ejecución.

La automatización controla elementos visibles de la interfaz. No está diseñada para ejecutarse con una sesión de Windows cerrada o desconectada de forma que la interfaz deje de estar disponible.

## Estructura principal

```text
patient_query_automate/
├── config/
│   └── extractors.yaml
├── exports/
├── logs/
├── tests/
│   ├── test_export_verification.py
│   └── test_logging_config.py
├── .env
├── .gitignore
├── export_verification.py
├── logging_config.py
├── main.py
├── requirements.txt
└── README.md
```

Las carpetas `exports/` y `logs/` se crean automáticamente y están excluidas del repositorio.

## Instalación

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Credenciales

Las credenciales se almacenan en un archivo `.env` en la raíz:

```env
PATIENT_QUERY_USERNAME=admin
PATIENT_QUERY_PASSWORD=CONTRASEÑA
```

El archivo `.env` no se versiona. Los valores de las credenciales no se escriben en los logs.

## Configuración de extractores

Los extractores se definen en:

```text
config/extractors.yaml
```

Ejemplo:

```yaml
extractors:
  observatorio_dlco:
    query_name: "OBSERVATORIO-DLCO"
    visit_date_from: "yesterday"
```

`query_name` debe coincidir exactamente con el nombre mostrado en Patient Query. El valor `yesterday` se sustituye por la fecha del día anterior al ejecutar el proceso.

## Ejecución

```powershell
python main.py --extractor observatorio_dlco
```

Otros extractores disponibles:

```powershell
python main.py --extractor observatorio_espirometria
python main.py --extractor observatorio_volumenes_pulmonares
```

## Archivos exportados

Los archivos se guardan en:

```text
C:\patient_query_automate\exports\
```

Patrón:

```text
CONSULTA_DDMMYYYY_HHMMSS.xls
```

La exportación se realiza como Microsoft Excel 97-2003 Worksheet (`.xls`).

## Logging por ejecución

Los registros se guardan en una carpeta específica:

```text
C:\patient_query_automate\logs\
```

Cada ejecución genera un archivo independiente con el extractor y el timestamp:

```text
{extractor}_YYYYMMDD_HHMMSS.log
```

Ejemplo:

```text
observatorio_dlco_20260729_000605.log
```

Si dos ejecuciones comienzan en el mismo segundo, la segunda utiliza un sufijo correlativo para no compartir ni sobrescribir el archivo:

```text
observatorio_dlco_20260729_000605_01.log
```

### Formato

Cada línea incluye:

```text
timestamp | nivel | run_id | extractor | phase | mensaje
```

Ejemplo:

```text
2026-07-29 00:06:05 | INFO | run_id=20260729T000605 | extractor=observatorio_dlco | phase=startup | Ejecución iniciada
```

Los mensajes `INFO` y superiores se muestran en consola y se guardan en el archivo. El archivo también admite eventos `DEBUG`.

### Eventos registrados

El ciclo registra:

1. inicio de la ejecución y ruta del log;
2. carga de configuración;
3. lanzamiento de Patient Query;
4. envío de credenciales sin mostrar sus valores;
5. duración de la actualización inicial;
6. selección y guardado de la consulta;
7. solicitud de exportación;
8. verificación del archivo exportado;
9. intento de cierre de Patient Query;
10. resultado global `success` o `failed`.

Las excepciones se registran con traceback.

## Verificación de la exportación

El proceso no declara éxito inmediatamente después de pulsar `Save`. Espera hasta confirmar que el archivo:

- existe;
- tiene tamaño mayor que cero;
- mantiene un tamaño estable durante varias comprobaciones;
- puede abrirse para lectura binaria.

El evento final exitoso incluye la ruta, el tamaño del archivo y la duración total.

## Manejo de errores y cierre

El flujo principal está protegido por manejo global de excepciones. Patient Query se intenta cerrar desde un bloque `finally`, incluso si falla una fase intermedia.

Códigos de salida:

- `0`: ejecución completada y exportación verificada;
- `1`: ejecución fallida.

Esto permite que el Programador de tareas de Windows identifique el resultado de la ejecución.

## Pruebas

Las pruebas no requieren abrir Patient Query:

```powershell
python -m unittest discover -s tests -v
```

Cubren:

- creación y nombre del archivo de log;
- inclusión de `run_id`, extractor y fase;
- sanitización del nombre del extractor;
- aceptación de un archivo exportado estable;
- rechazo de archivos inexistentes o vacíos.

## Seguridad

No se deben registrar ni versionar datos clínicos, filas exportadas, credenciales, archivos `.env` ni archivos generados durante las ejecuciones.
