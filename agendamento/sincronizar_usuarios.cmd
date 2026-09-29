@echo off
REM Sincroniza contas e senhas do GeoMap com o Hub (a cada hora).
REM Chamado pelo Agendador de Tarefas; a saida vai pra logs\usuarios.log.
cd /d "%~dp0.."
if not exist agendamento\logs mkdir agendamento\logs
set PYTHONIOENCODING=utf-8
echo. >> agendamento\logs\usuarios.log
echo ===== %date% %time% ===== >> agendamento\logs\usuarios.log
python ingestao\sincronizar_usuarios.py >> agendamento\logs\usuarios.log 2>&1
echo codigo de saida: %errorlevel% >> agendamento\logs\usuarios.log
