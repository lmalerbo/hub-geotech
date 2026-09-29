@echo off
REM Traz a situacao dos voos do Drone MGMT (tag da Falha Soca na Colheita), a cada hora.
REM Chamado pelo Agendador de Tarefas; a saida vai pra logs\voos.log.
cd /d "%~dp0.."
if not exist agendamento\logs mkdir agendamento\logs
set PYTHONIOENCODING=utf-8
echo. >> agendamento\logs\voos.log
echo ===== %date% %time% ===== >> agendamento\logs\voos.log
python ingestao\sincronizar_usuarios.py >> agendamento\logs\voos.log 2>&1
echo codigo de saida: %errorlevel% >> agendamento\logs\voos.log
