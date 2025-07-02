@echo off
echo ========================================
echo 🚀 DESARROLLO FLUIDO TAILWIND + DJANGO
echo ========================================
echo.
echo ✅ Este script iniciará:
echo   1. Tailwind CSS en modo watch (detecta cambios automáticamente)
echo   2. Servidor Django
echo.
echo 🌐 URLs disponibles:
echo   - http://127.0.0.1:8000/simple-tailwind-test/
echo   - http://127.0.0.1:8000/flowbite-test/
echo   - http://127.0.0.1:8000/debug-tailwind/
echo.
echo 💡 FLUJO DE TRABAJO:
echo   1. Edita templates HTML o CSS
echo   2. Guarda con Ctrl+S
echo   3. Recarga el navegador con F5
echo   ✨ ¡Los cambios aparecen al instante!
echo.
echo ========================================

cd /d "%~dp0"

REM Activar entorno virtual si existe
if exist gestion_env\Scripts\activate.bat (
    call gestion_env\Scripts\activate
)

echo 🔧 Compilando CSS inicial...
cd theme\static_src
call npm run build-prod
cd ..\..

echo 📁 Copiando archivos estáticos...
python manage.py collectstatic --noinput --clear

echo � Iniciando Tailwind Watch en segundo plano...
start "Tailwind CSS Watch" cmd /k "cd /d %cd%\theme\static_src && npm run tailwind-watch"

REM Dar tiempo para que Tailwind se inicie
timeout /t 3 /nobreak >nul

echo 🌐 Iniciando servidor Django...
echo.
echo ========================================
echo � ¡LISTO! Abre: http://127.0.0.1:8000/simple-tailwind-test/
echo ========================================
echo.

python manage.py runserver

pause
