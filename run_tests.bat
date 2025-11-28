@echo off
REM Script para ejecutar tests usando SQLite local
REM Esto NO afecta la base de datos de producción en Heroku

echo =========================================
echo  Ejecutando Tests con SQLite Local
echo =========================================
echo.
echo NOTA: Los tests usan una base de datos SQLite temporal.
echo Tu base de datos de produccion en Heroku NO sera afectada.
echo.

REM Guardar el archivo .env original
if exist .env (
    copy /Y .env .env.backup >nul
)

REM Usar la configuración de tests
copy /Y .env.test .env >nul

REM Ejecutar los tests
python manage.py test %*

REM Restaurar el archivo .env original
if exist .env.backup (
    copy /Y .env.backup .env >nul
    del .env.backup
)

echo.
echo =========================================
echo  Tests completados
echo =========================================
