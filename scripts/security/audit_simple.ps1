# Script simple de auditoria de seguridad (sin caracteres especiales)
# Ejecutar: .\audit_simple.ps1

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "AUDITORIA DE SEGURIDAD" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"

# 1. Safety Check
Write-Host "[1/3] Escaneando vulnerabilidades con Safety..." -ForegroundColor Yellow
try {
    $safetyOutput = python -m safety check 2>&1
    if ($safetyOutput -match "No known security vulnerabilities") {
        Write-Host "  OK: Sin vulnerabilidades conocidas`n" -ForegroundColor Green
    }
    else {
        Write-Host "  WARNING: Se encontraron vulnerabilidades" -ForegroundColor Red
        Write-Host "  Ejecuta: python -m safety check (para ver detalles)`n" -ForegroundColor Gray
    }
}
catch {
    Write-Host "  ERROR: No se pudo ejecutar Safety`n" -ForegroundColor Red
}

# 2. Bandit Check  
Write-Host "[2/3] Analizando codigo con Bandit..." -ForegroundColor Yellow
try {
    $banditOutput = python -m bandit -r accounts/ consultorios/ pedidos_estudios/ -ll 2>&1
    
    if ($banditOutput -match "No issues identified") {
        Write-Host "  OK: No se encontraron problemas de seguridad`n" -ForegroundColor Green
    }
    elseif ($banditOutput -match "Total issues") {
        Write-Host "  WARNING: Se encontraron problemas potenciales" -ForegroundColor Yellow
        Write-Host "  Ejecuta: python -m bandit -r . -ll (para ver detalles)`n" -ForegroundColor Gray
    }
}
catch {
    Write-Host "  ERROR: No se pudo ejecutar Bandit`n" -ForegroundColor Red
}

# 3. Django Check
Write-Host "[3/3] Verificando configuracion de Django..." -ForegroundColor Yellow
try {
    $djangoOutput = python manage.py check --deploy 2>&1
    
    if ($djangoOutput -match "System check identified no issues") {
        Write-Host "  OK: Sin problemas de configuracion`n" -ForegroundColor Green
    }
    else {
        $errorCount = ([regex]::Matches($djangoOutput, "ERRORS:")).Count
        $warningCount = ([regex]::Matches($djangoOutput, "System check identified (\d+) issue")).Count
        
        if ($errorCount -gt 0) {
            Write-Host "  ERROR: Se encontraron errores de configuracion" -ForegroundColor Red
        }
        else {
            Write-Host "  WARNING: Se encontraron advertencias (normal en desarrollo)" -ForegroundColor Yellow
        }
        Write-Host "  Ejecuta: python manage.py check --deploy (para ver detalles)`n" -ForegroundColor Gray
    }
}
catch {
    Write-Host "  ERROR: No se pudo ejecutar Django check`n" -ForegroundColor Red
}

# Resumen
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "RESUMEN" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Fecha: $timestamp" -ForegroundColor White
Write-Host "`nPara ver detalles completos, ejecuta:" -ForegroundColor Yellow
Write-Host "  python -m safety check" -ForegroundColor Gray
Write-Host "  python -m bandit -r . -ll" -ForegroundColor Gray
Write-Host "  python manage.py check --deploy" -ForegroundColor Gray

Write-Host "`nDocumentacion:" -ForegroundColor Yellow
Write-Host "  - Guia completa: AUDITORIA_SEGURIDAD.md" -ForegroundColor Gray
Write-Host "  - Referencia rapida: SEGURIDAD_CHEATSHEET.md" -ForegroundColor Gray
Write-Host "  - Mejoras implementables: MEJORAS_SEGURIDAD_IMPLEMENTABLES.md" -ForegroundColor Gray

Write-Host "`nAuditoria completada!`n" -ForegroundColor Green
