@echo off
REM Cria (ou recria) as duas tarefas do Hub no Agendador de Tarefas.
REM NAO precisa de admin: as tarefas rodam sob o usuario que executar este arquivo
REM (mesmo esquema da automacao Talhoes/Limites do GeoMap no servidor Geo).
REM A Base Fazendas (FME) chega as ~06:02; a rodada diaria roda as 07:00.
schtasks /create /sc daily /st 07:00 /tn "Hub Geotech - Rodada diaria" /tr "\"%~dp0rodar_diario.cmd\"" /f
schtasks /create /sc hourly /mo 1 /st 07:30 /tn "Hub Geotech - Sincronizar usuarios" /tr "\"%~dp0sincronizar_usuarios.cmd\"" /f
echo.
echo Tarefas criadas. Para testar agora sem esperar:
echo   schtasks /run /tn "Hub Geotech - Rodada diaria"
echo   schtasks /run /tn "Hub Geotech - Sincronizar usuarios"
