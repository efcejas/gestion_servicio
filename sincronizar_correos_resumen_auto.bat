@echo off
REM ============================================================================
REM Script para sincronizar correos resumidos automáticamente
REM Se ejecuta por Task Scheduler cada 15 minutos
REM ============================================================================

cd /d "%~dp0"

if not exist logs mkdir logs

call gestion_env\Scripts\activate.bat

python manage.py sincronizar_correos_resumen --max-emails=20
set EXIT_CODE=%ERRORLEVEL%

echo [%date% %time%] Sync correo resumen - Exit Code: %EXIT_CODE% >> logs\sincronizar_correos_resumen.log

exit /b %EXIT_CODE%
