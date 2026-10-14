@echo off
REM Rodada diaria do Hub (Base Fazendas, PLANAGRI, Conservacao e regras).
REM Chamado pelo Agendador de Tarefas; a saida vai pra logs\diario.log.
cd /d "%~dp0.."
if not exist agendamento\logs mkdir agendamento\logs
set PYTHONIOENCODING=utf-8
echo. >> agendamento\logs\diario.log
echo ===== %date% %time% ===== >> agendamento\logs\diario.log
python ingestao\rodar_diario.py >> agendamento\logs\diario.log 2>&1
set CODIGO=%errorlevel%
echo codigo de saida: %CODIGO% >> agendamento\logs\diario.log
REM Devolve o codigo ao Agendador: falha aparece como falha, nao como "exito".
exit /b %CODIGO%
