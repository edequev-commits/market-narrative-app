@echo off
cd /d C:\Trading\market_narrative_app

call venv\Scripts\activate

echo Generando informacion...
python app.py

echo Proceso terminado.
pause