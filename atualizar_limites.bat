@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   Atualizacao de Limites - Operations Center
echo ============================================
echo.

echo [1/3] Formatando shapefile em base\input ...
python format_oc_boundaries.py config.yaml
if errorlevel 1 goto :erro

echo.
echo [2/3] Simulando sincronizacao com o Operations Center (dry-run, nao grava nada ainda) ...
python sync_boundaries_api.py config.yaml
if errorlevel 1 goto :erro

echo.
set /p CONFIRMAR="Conferiu o resumo acima? Gravar de verdade no Operations Center? (S/N): "
if /i not "%CONFIRMAR%"=="S" goto :cancelado

echo.
echo [3/3] Gravando limites no Operations Center ...
python sync_boundaries_api.py config.yaml --live
if errorlevel 1 goto :erro

echo.
echo Concluido com sucesso!
goto :fim

:cancelado
echo.
echo Operacao cancelada. Nada foi gravado no Operations Center.
goto :fim

:erro
echo.
echo ============================================
echo   Ocorreu um erro. Veja a mensagem acima.
echo ============================================

:fim
echo.
pause
