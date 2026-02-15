# ============================================================================
# Script de PowerShell para configurar Task Scheduler automaticamente
# Crea una tarea programada que ejecuta el procesamiento de pedidos cada 5 min
# ============================================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CONFIGURACION AUTOMATICA DE TASK SCHEDULER" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que estamos ejecutando como Administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: Este script requiere privilegios de administrador" -ForegroundColor Red
    Write-Host ""
    Write-Host "Solucion:" -ForegroundColor Yellow
    Write-Host "1. Cierra esta ventana" -ForegroundColor Yellow
    Write-Host "2. Clic derecho en PowerShell" -ForegroundColor Yellow
    Write-Host "3. Selecciona 'Ejecutar como administrador'" -ForegroundColor Yellow
    Write-Host "4. Ejecuta el script de nuevo" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "[OK] Ejecutando como Administrador" -ForegroundColor Green
Write-Host ""

# Configuracion
$TaskName = "ProcesarPedidosEstudios"
$TaskDescription = "Procesa pedidos de estudios desde Gmail cada 5 minutos"
$ScriptPath = "$PSScriptRoot\procesar_pedidos_auto.bat"
$WorkingDirectory = $PSScriptRoot
$IntervalMinutes = 5

# Verificar que el archivo .bat existe
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: No se encontro el archivo:" -ForegroundColor Red
    Write-Host "  $ScriptPath" -ForegroundColor Red
    Write-Host ""
    pause
    exit 1
}

Write-Host "[OK] Archivo encontrado: procesar_pedidos_auto.bat" -ForegroundColor Green
Write-Host ""

# Verificar si la tarea ya existe
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "[!] La tarea '$TaskName' ya existe" -ForegroundColor Yellow
    $response = Read-Host "Deseas reemplazarla? (S/N)"
    
    if ($response -eq 'S' -or $response -eq 's') {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "[OK] Tarea anterior eliminada" -ForegroundColor Green
    } else {
        Write-Host "Operacion cancelada" -ForegroundColor Yellow
        pause
        exit 0
    }
}

Write-Host ""
Write-Host "Creando tarea programada..." -ForegroundColor Cyan
Write-Host ""

try {
    # Crear acción (qué ejecutar)
    $Action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument "/c `"$ScriptPath`"" `
        -WorkingDirectory $WorkingDirectory

    # Crear trigger (cuándo ejecutar)
    # Ejecutar diariamente empezando ahora, repitiendo cada 5 minutos indefinidamente
    $Trigger = New-ScheduledTaskTrigger `
        -Once `
        -At (Get-Date) `
        -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
        -RepetitionDuration ([TimeSpan]::MaxValue)

    # Configuración de la tarea
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

    # Crear principal (con qué usuario)
    # Se ejecuta con el usuario actual
    $Principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType S4U `
        -RunLevel Highest

    # Registrar la tarea
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $TaskDescription `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal | Out-Null

    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  [OK] TAREA CREADA EXITOSAMENTE" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Configuracion:" -ForegroundColor Cyan
    Write-Host "  - Nombre: $TaskName" -ForegroundColor White
    Write-Host "  - Frecuencia: Cada $IntervalMinutes minutos" -ForegroundColor White
    Write-Host "  - Script: procesar_pedidos_auto.bat" -ForegroundColor White
    Write-Host "  - Estado: Activa y ejecutandose" -ForegroundColor White
    Write-Host ""
    
    Write-Host "Para ver los logs:" -ForegroundColor Cyan
    Write-Host "  type logs\procesar_pedidos.log" -ForegroundColor Yellow
    Write-Host ""
    
    Write-Host "Para modificar la tarea:" -ForegroundColor Cyan
    Write-Host "  taskschd.msc" -ForegroundColor Yellow
    Write-Host "  Buscar: '$TaskName'" -ForegroundColor Yellow
    Write-Host ""
    
    # Preguntar si desea ejecutar ahora
    $runNow = Read-Host "Deseas ejecutar una prueba ahora? (S/N)"
    
    if ($runNow -eq 'S' -or $runNow -eq 's') {
        Write-Host ""
        Write-Host "Ejecutando tarea..." -ForegroundColor Cyan
        try {
            Start-ScheduledTask -TaskName $TaskName
            Start-Sleep -Seconds 3
            
            Write-Host "[OK] Tarea iniciada" -ForegroundColor Green
            Write-Host ""
            Write-Host "Revisa el log en unos segundos:" -ForegroundColor Yellow
            Write-Host "  type logs\procesar_pedidos.log" -ForegroundColor Yellow
        } catch {
            Write-Host "[!] No se pudo ejecutar la tarea manualmente" -ForegroundColor Yellow
            Write-Host "La tarea se ejecutara automaticamente cada 5 minutos" -ForegroundColor Yellow
        }
    }
    
} catch {
    Write-Host ""
    Write-Host "ERROR al crear la tarea:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    pause
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Configuracion completada. Presiona cualquier tecla para salir."
Write-Host "============================================================" -ForegroundColor Green
pause
