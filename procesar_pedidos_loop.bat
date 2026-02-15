@echo off
REM ============================================================================
REM Script de monitoreo continuo - Loop infinito
REM Ejecuta el procesamiento cada 5 minutos indefinidamente
REM Presiona Ctrl+C para detener
REM ============================================================================

echo ============================================================
echo   PROCESAMIENTO AUTOMATICO DE PEDIDOS - MODO CONTINUO
echo ============================================================
echo.
echo Procesando cada 5 minutos...
echo Presiona Ctrl+C para detener
echo.
echo ============================================================

cd /d "%~dp0"

:loop
    echo.
    echo [%date% %time%] Iniciando procesamiento...
    
    call gestion_env\Scripts\activate.bat
    python manage.py procesar_pedidos_auto --max-emails=10
    call gestion_env\Scripts\deactivate.bat
    
    echo [%date% %time%] Completado. Esperando 5 minutos...
    
    REM Esperar 5 minutos (300 segundos)
    timeout /t 300 /nobreak
    
goto loop
