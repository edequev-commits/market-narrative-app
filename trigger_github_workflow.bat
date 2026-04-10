@echo off
cd /d C:\Trading\market_narrative_app
powershell -ExecutionPolicy Bypass -File "C:\Trading\market_narrative_app\trigger_github_workflow.ps1"
pause