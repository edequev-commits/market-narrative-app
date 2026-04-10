@echo off
cd /d C:\Trading\market_narrative_app

if exist data\cnbc_extracted.json del data\cnbc_extracted.json
if exist data\final_regime_prompt.txt del data\final_regime_prompt.txt
if exist data\market_regime.txt del data\market_regime.txt

git pull --rebase origin main
git push origin main
pause