@echo off
cd /d C:\patient_query_automate

if not exist logs mkdir logs
taskkill /F /IM MusNotification.exe >nul 2>&1
taskkill /F /IM MusNotificationUx.exe >nul 2>&1

call .venv\Scripts\activate.bat

python main.py --extractor gx_ino
set "exit_code=%ERRORLEVEL%"

echo Ejecucion finalizada: %date% %time%; exit_code=%exit_code%
exit /b %exit_code%