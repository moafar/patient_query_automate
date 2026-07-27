@echo off
cd /d C:\patient_query_automate

if not exist logs mkdir logs

call .venv\Scripts\activate.bat

python main.py --extractor observatorio_dlco >> logs\daily_run.log 2>&1

timeout /t 30 /nobreak >> logs\daily_run.log 2>&1

python main.py --extractor observatorio_espirometria >> logs\daily_run.log 2>&1

timeout /t 30 /nobreak >> logs\daily_run.log 2>&1

python main.py --extractor observatorio_volumenes_pulmonares >> logs\daily_run.log 2>&1

echo Ejecucion finalizada: %date% %time% >> logs\daily_run.log