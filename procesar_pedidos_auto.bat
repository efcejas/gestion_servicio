@echo off
REM ============================================================================
REM Script para procesamiento automático de pedidos de estudios
REM Se ejecuta cada X minutos via Windows Task Scheduler
REM ============================================================================

cd /d "%~dp0"

REM Activar entorno virtual
call gestion_env\Scripts\activate.bat

REM Ejecutar procesamiento automático (marca emails como leídos)
python manage.py procesar_pedidos_auto --max-emails=10
set EXIT_CODE=%ERRORLEVEL%

REM Log de ejecución
echo [%date% %time%] Procesamiento completado - Exit Code: %EXIT_CODE% >> logs\procesar_pedidos.log

REM Retornar el código de salida del comando Python
exit /b %EXIT_CODE%
