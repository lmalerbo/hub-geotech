@echo off
REM Agente do modulo Drone: fica rodando e processa a fila do Hub a cada 30 s.
REM O Agendador chama a cada 10 min; se ja estiver rodando, a nova chamada e ignorada.
cd /d "%~dp0.."
if not exist agendamento\logs mkdir agendamento\logs
set PYTHONIOENCODING=utf-8
set PYTHONWARNINGS=ignore
echo ===== %date% %time% agente iniciado ===== >> agendamento\logs\drone_agente.log
python -m drone.agente >> agendamento\logs\drone_agente.log 2>&1
set CODIGO=%errorlevel%
echo codigo de saida: %CODIGO% >> agendamento\logs\drone_agente.log
REM Devolve o codigo ao Agendador: falha aparece como falha, nao como "exito".
exit /b %CODIGO%
