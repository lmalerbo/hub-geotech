@echo off
REM Regra B da Colheita: agenda (via GeoMap) e acompanha os voos de Linhas de
REM Colheita no Drone MGMT, a cada hora. A saida vai pra logs\voos_colheita.log.
cd /d "%~dp0.."
if not exist agendamento\logs mkdir agendamento\logs
set PYTHONIOENCODING=utf-8
echo. >> agendamento\logs\voos_colheita.log
echo ===== %date% %time% ===== >> agendamento\logs\voos_colheita.log
python ingestao\voos_linhas_colheita.py >> agendamento\logs\voos_colheita.log 2>&1
set CODIGO=%errorlevel%
echo codigo de saida: %CODIGO% >> agendamento\logs\voos_colheita.log
REM Devolve o codigo ao Agendador: falha aparece como falha, nao como "exito".
exit /b %CODIGO%
