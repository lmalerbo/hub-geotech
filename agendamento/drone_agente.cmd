@echo off
REM Agente do modulo Drone: fica rodando e processa a fila do Hub a cada 30 s.
REM O Agendador chama a cada 10 min; se ja estiver rodando, a nova chamada e ignorada.
cd /d "%~dp0.."
if not exist agendamento\logs mkdir agendamento\logs
set PYTHONIOENCODING=utf-8
set PYTHONWARNINGS=ignore
echo ===== %date% %time% agente iniciado ===== >> agendamento\logs\drone_agente.log
python -m drone.agente >> agendamento\logs\drone_agente.log 2>&1
echo codigo de saida: %errorlevel% >> agendamento\logs\drone_agente.log
