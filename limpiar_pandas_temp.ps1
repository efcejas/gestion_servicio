# Script para limpiar archivos temporales corruptos de pandas
# Ejecutar si ves: "WARNING: Ignoring invalid distribution ~andas"

Write-Host "Limpiando archivos temporales de pandas..." -ForegroundColor Yellow

$env_path = "C:\Dev\GitHub\gestion_servicio\gestion_env\Lib\site-packages"

$folders_to_remove = @(
    "$env_path\~-ndas.libs",
    "$env_path\~andas.libs",
    "$env_path\pandas\~libs"
)

foreach ($folder in $folders_to_remove) {
    if (Test-Path $folder) {
        try {
            Remove-Item -Path $folder -Recurse -Force -ErrorAction Stop
            Write-Host "OK Eliminado: $folder" -ForegroundColor Green
        }
        catch {
            Write-Host "WARNING No se pudo eliminar: $folder" -ForegroundColor Yellow
            Write-Host "  Intenta manualmente con: Remove-Item '$folder' -Recurse -Force" -ForegroundColor Gray
        }
    }
}

Write-Host "`nLimpieza completada" -ForegroundColor Green
Write-Host "Ejecuta 'pip list' para verificar que ya no aparece el warning" -ForegroundColor Cyan
