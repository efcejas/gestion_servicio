@echo off
REM Crear tarea programada - Ejecutar como Administrador

schtasks /create /tn "ProcesarPedidosEstudios" /tr "C:\Dev\GitHub\gestion_servicio\procesar_pedidos_auto.bat" /sc minute /mo 5 /ru "%USERNAME%" /rl HIGHEST /f

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo   [OK] TAREA CREADA EXITOSAMENTE
    echo ============================================================
    echo.
    echo Configuracion:
    echo   - Nombre: ProcesarPedidosEstudios
    echo   - Frecuencia: Cada 5 minutos
    echo   - Script: procesar_pedidos_auto.bat
    echo   - Estado: Activa
    echo.
    echo Para ver la tarea: taskschd.msc
    echo Para ver logs: type logs\procesar_pedidos.log
    echo.
    
    REM Preguntar si desea ejecutar ahora
    set /p ejecutar="Deseas ejecutar una prueba ahora? (S/N): "
    if /i "%ejecutar%"=="S" (
        echo.
        echo Ejecutando tarea...
        schtasks /run /tn "ProcesarPedidosEstudios"
        timeout /t 3 /nobreak >nul
        echo [OK] Tarea iniciada
        echo Revisa el log: type logs\procesar_pedidos.log
    )
) else (
    echo.
    echo [ERROR] No se pudo crear la tarea
    echo Asegurate de ejecutar este archivo como Administrador
    echo.
)

pause
