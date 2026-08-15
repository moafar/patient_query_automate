@echo off
cd /d C:\patient_query_automate

if not exist logs mkdir logs

call .venv\Scripts\activate.bat

python main.py --extractor gx_ino
set "exit_code=%ERRORLEVEL%"

echo Ejecucion finalizada: %date% %time%; exit_code=%exit_code%
exit /b %exit_code%