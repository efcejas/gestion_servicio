# Script de actualizacion de paquetes con vulnerabilidades
# Ejecutar: .\fix_vulnerabilities.ps1

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "ACTUALIZANDO PAQUETES VULNERABLES" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$packages = @(
    "Django>=5.1.15",
    "pypdf>=6.6.2",
    "urllib3>=2.6.3",
    "requests>=2.32.4",
    "sqlparse>=0.5.4",
    "cryptography>=44.0.1",
    "fonttools>=4.61.0",
    "brotli>=1.2.0"
)

foreach ($package in $packages) {
    Write-Host "Actualizando: $package" -ForegroundColor Yellow
    try {
        pip install --upgrade $package 2>&1 | Out-Null
        Write-Host "  OK: $package actualizado`n" -ForegroundColor Green
    }
    catch {
        Write-Host "  ERROR: No se pudo actualizar $package`n" -ForegroundColor Red
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "VERIFICANDO VULNERABILIDADES" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Ejecutando safety check...`n" -ForegroundColor Yellow
python -m safety check

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "ACTUALIZACION COMPLETADA" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

Write-Host "`nRevisa el reporte de Safety arriba." -ForegroundColor White
Write-Host "Si aun hay vulnerabilidades, consulta AUDITORIA_SEGURIDAD.md`n" -ForegroundColor White
