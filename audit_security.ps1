# ========================================
# 🔒 SCRIPT DE AUDITORÍA DE SEGURIDAD
# ========================================
# Ejecuta todas las herramientas de seguridad y genera reportes

param(
    [switch]$Full = $false,  # Ejecutar auditoría completa (más lenta)
    [switch]$Quick = $false  # Solo checks rápidos
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🔒 AUDITORÍA DE SEGURIDAD" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Crear directorio para reportes
$reportsDir = "security_reports"
if (-not (Test-Path $reportsDir)) {
    New-Item -ItemType Directory -Path $reportsDir | Out-Null
    Write-Host "✅ Directorio de reportes creado: $reportsDir`n" -ForegroundColor Green
}

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$summaryFile = "$reportsDir\summary_$timestamp.txt"

# Función para log
function Write-Log {
    param($Message, $Color = "White")
    Write-Host $Message -ForegroundColor $Color
    Add-Content -Path $summaryFile -Value $Message
}

Write-Log "`n🔍 INICIANDO AUDITORÍA DE SEGURIDAD - $timestamp`n" "Cyan"
Write-Log "Proyecto: gestion_servicio" "Gray"
Write-Log "============================================`n" "Gray"

# ========================================
# 1. VERIFICAR HERRAMIENTAS INSTALADAS
# ========================================

Write-Host "`n[1/6] Verificando herramientas instaladas..." -ForegroundColor Yellow

$tools = @{
    "safety" = "safety --version"
    "bandit" = "bandit --version"
}

$allInstalled = $true
foreach ($tool in $tools.Keys) {
    try {
        $null = Invoke-Expression $tools[$tool] 2>&1
        Write-Host "  ✅ $tool instalado" -ForegroundColor Green
    }
    catch {
        Write-Host "  ❌ $tool NO instalado" -ForegroundColor Red
        $allInstalled = $false
    }
}

if (-not $allInstalled) {
    Write-Host "`n⚠️  Instala las herramientas faltantes con:" -ForegroundColor Yellow
    Write-Host "   pip install -r requirements-security.txt`n" -ForegroundColor White
    exit 1
}

# ========================================
# 2. SAFETY - AUDITORÍA DE DEPENDENCIAS
# ========================================

Write-Host "`n[2/6] 🔍 Escaneando vulnerabilidades en dependencias (Safety)..." -ForegroundColor Yellow

try {
    $safetyOutput = safety check 2>&1
    $safetyJson = "$reportsDir\safety_report_$timestamp.json"
    
    safety check --json | Out-File -FilePath $safetyJson -Encoding utf8
    
    if ($safetyOutput -match "No known security vulnerabilities") {
        Write-Log "  ✅ Safety: Sin vulnerabilidades conocidas" "Green"
    }
    else {
        Write-Log "  ⚠️  Safety: Se encontraron vulnerabilidades" "Red"
        Write-Log "     Reporte: $safetyJson" "Gray"
        $safetyOutput | ForEach-Object { Write-Log "     $_" "Red" }
    }
}
catch {
    Write-Log "  ❌ Error ejecutando Safety: $_" "Red"
}

# ========================================
# 3. BANDIT - ANÁLISIS ESTÁTICO
# ========================================

Write-Host "`n[3/6] 🔍 Análisis estático de código (Bandit)..." -ForegroundColor Yellow

try {
    $banditJson = "$reportsDir\bandit_report_$timestamp.json"
    
    # Ejecutar bandit (solo severidad media y alta, excluir tests y migraciones)
    $banditOutput = bandit -r . -ll --exclude ./*/tests.py,./*/migrations/*,./gestion_env/*,./node_modules/* -f json 2>&1
    
    $banditOutput | Out-File -FilePath $banditJson -Encoding utf8
    
    # Parsear resultados
    $banditText = bandit -r . -ll --exclude ./*/tests.py,./*/migrations/*,./gestion_env/*,./node_modules/* 2>&1
    
    if ($banditText -match "No issues identified") {
        Write-Log "  ✅ Bandit: No se encontraron problemas de seguridad" "Green"
    }
    elseif ($banditText -match "Total issues") {
        # Extraer número de issues
        if ($banditText -match "Total issues \(.*?\):\s*(\d+)") {
            $issueCount = $matches[1]
            if ($issueCount -eq "0") {
                Write-Log "  ✅ Bandit: No se encontraron problemas de seguridad" "Green"
            }
            else {
                Write-Log "  ⚠️  Bandit: Se encontraron $issueCount problemas" "Yellow"
                Write-Log "     Reporte: $banditJson" "Gray"
                
                # Mostrar resumen de severidades
                $highCount = ([regex]::Matches($banditText, "Severity: High")).Count
                $mediumCount = ([regex]::Matches($banditText, "Severity: Medium")).Count
                
                if ($highCount -gt 0) {
                    Write-Log "     - Alta: $highCount" "Red"
                }
                if ($mediumCount -gt 0) {
                    Write-Log "     - Media: $mediumCount" "Yellow"
                }
            }
        }
    }
}
catch {
    Write-Log "  ❌ Error ejecutando Bandit: $_" "Red"
}

# ========================================
# 4. DJANGO SECURITY CHECK
# ========================================

Write-Host "`n[4/6] 🔍 Verificaciones de Django (manage.py check)..." -ForegroundColor Yellow

try {
    $djangoOutput = python manage.py check --deploy 2>&1
    
    if ($djangoOutput -match "System check identified no issues") {
        Write-Log "  ✅ Django: Sin problemas de configuración" "Green"
    }
    else {
        # Contar warnings
        $warningCount = ([regex]::Matches($djangoOutput, "WARNINGS:")).Count
        $errorCount = ([regex]::Matches($djangoOutput, "ERRORS:")).Count
        
        if ($errorCount -gt 0) {
            Write-Log "  ❌ Django: Se encontraron ERRORES" "Red"
        }
        elseif ($warningCount -gt 0) {
            Write-Log "  ⚠️  Django: Se encontraron ADVERTENCIAS" "Yellow"
        }
        
        # Guardar output
        $djangoFile = "$reportsDir\django_check_$timestamp.txt"
        $djangoOutput | Out-File -FilePath $djangoFile -Encoding utf8
        Write-Log "     Reporte: $djangoFile" "Gray"
        
        # Mostrar top 5 warnings
        $warnings = $djangoOutput -split "`n" | Where-Object { $_ -match "^\?\:" } | Select-Object -First 5
        foreach ($warning in $warnings) {
            Write-Log "     $warning" "Yellow"
        }
    }
}
catch {
    Write-Log "  ❌ Error ejecutando Django check: $_" "Red"
}

# ========================================
# 5. DETECT-SECRETS
# ========================================

if ($Full) {
    Write-Host "`n[5/6] 🔍 Buscando secretos hardcodeados (Detect-Secrets)..." -ForegroundColor Yellow
    
    try {
        # Verificar si está instalado
        $dsVersion = detect-secrets --version 2>&1
        
        $secretsOutput = detect-secrets scan 2>&1
        $secretsFile = "$reportsDir\secrets_scan_$timestamp.json"
        $secretsOutput | Out-File -FilePath $secretsFile -Encoding utf8
        
        # Contar secretos potenciales
        if ($secretsOutput -match '"results":\s*\{\}') {
            Write-Log "  ✅ Detect-Secrets: No se encontraron secretos" "Green"
        }
        else {
            Write-Log "  ⚠️  Detect-Secrets: Posibles secretos encontrados" "Yellow"
            Write-Log "     Reporte: $secretsFile" "Gray"
            Write-Log "     NOTA: Puede haber falsos positivos" "Gray"
        }
    }
    catch {
        Write-Log "  ⚠️  Detect-Secrets no instalado (opcional)" "Yellow"
    }
}
else {
    Write-Host "`n[5/6] ⏭️  Detect-Secrets omitido (usa --Full para incluirlo)" -ForegroundColor Gray
}

# ========================================
# 6. VERIFICACIONES PERSONALIZADAS
# ========================================

Write-Host "`n[6/6] 🔍 Verificaciones personalizadas..." -ForegroundColor Yellow

# 6.1 Verificar archivos sensibles
Write-Log "`n  Verificando archivos sensibles en repositorio:" "White"

$sensitiveFiles = @(
    "credentials.json",
    "token.json",
    ".env",
    "secrets.py",
    "settings_local.py"
)

foreach ($file in $sensitiveFiles) {
    if (Test-Path $file) {
        # Verificar si está en .gitignore
        $gitignoreContent = Get-Content .gitignore -Raw -ErrorAction SilentlyContinue
        if ($gitignoreContent -and $gitignoreContent -match [regex]::Escape($file)) {
            Write-Log "    ✅ $file existe pero está en .gitignore" "Green"
        }
        else {
            Write-Log "    ⚠️  $file existe y NO está en .gitignore" "Red"
        }
    }
}

# 6.2 Verificar settings.py
Write-Log "`n  Analizando configuración de Django:" "White"

$settingsFile = "gestion_estudios\settings.py"
if (Test-Path $settingsFile) {
    $settingsContent = Get-Content $settingsFile -Raw
    
    # Check DEBUG hardcoded
    if ($settingsContent -match "DEBUG\s*=\s*True" -and $settingsContent -notmatch "config\('DEBUG") {
        Write-Log "    ⚠️  DEBUG=True hardcodeado (debería ser variable de entorno)" "Yellow"
    }
    else {
        Write-Log "    ✅ DEBUG configurado correctamente" "Green"
    }
    
    # Check SECRET_KEY
    if ($settingsContent -match "SECRET_KEY\s*=\s*['`"][a-zA-Z0-9]{30,}['`"]") {
        Write-Log "    ⚠️  SECRET_KEY hardcodeada en settings.py" "Red"
    }
    else {
        Write-Log "    ✅ SECRET_KEY usando variable de entorno" "Green"
    }
    
    # Check ALLOWED_HOSTS
    if ($settingsContent -match "ALLOWED_HOSTS\s*=\s*\['\*'\]") {
        Write-Log "    ⚠️  ALLOWED_HOSTS acepta cualquier host" "Red"
    }
    else {
        Write-Log "    ✅ ALLOWED_HOSTS configurado" "Green"
    }
}

# 6.3 Verificar dependencias desactualizadas
Write-Log "`n  Verificando dependencias desactualizadas:" "White"
try {
    $outdated = pip list --outdated 2>&1
    if ($outdated -match "Package\s+Version") {
        $outdatedCount = ($outdated -split "`n" | Where-Object { $_ -match "^\S+\s+" }).Count - 1
        if ($outdatedCount -gt 0) {
            Write-Log "    ⚠️  $outdatedCount paquetes desactualizados" "Yellow"
            Write-Log "    Ejecuta: pip list --outdated" "Gray"
        }
        else {
            Write-Log "    ✅ Todas las dependencias actualizadas" "Green"
        }
    }
}
catch {
    Write-Log "    ⚠️  No se pudo verificar dependencias" "Yellow"
}

# ========================================
# RESUMEN FINAL
# ========================================

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "📊 RESUMEN DE AUDITORÍA" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Log "`n========================================" "Cyan"
Write-Log "📊 RESUMEN FINAL" "Cyan"
Write-Log "========================================`n" "Cyan"

Write-Log "Fecha: $timestamp" "White"
Write-Log "Reportes guardados en: $reportsDir`n" "White"

Write-Log "Proximos pasos:" "Yellow"
Write-Log "1. Revisa los reportes detallados en $reportsDir" "White"
Write-Log "2. Lee AUDITORIA_SEGURIDAD.md para entender cada problema" "White"
Write-Log "3. Prioriza: Errores > Warnings Alta > Warnings Media" "White"
Write-Log "4. Ejecuta esta auditoria antes de cada deploy`n" "White"

Write-Host "`n✅ Auditoria completada. Revisa: $summaryFile`n" -ForegroundColor Green

# Abrir resumen si esta en Windows
if ($env:OS -match "Windows") {
    Write-Host "Quieres abrir el resumen? (S/N): " -NoNewline -ForegroundColor Yellow
    $response = Read-Host
    if ($response -eq "S" -or $response -eq "s") {
        Start-Process notepad $summaryFile
    }
}
