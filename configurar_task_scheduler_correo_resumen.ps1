# ============================================================================
# Script de PowerShell para configurar Task Scheduler del resumen de correos
# Crea una tarea programada que ejecuta la sincronización cada 15 min
# ============================================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CONFIGURACION TASK SCHEDULER - RESUMEN CORREOS" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: Este script requiere privilegios de administrador" -ForegroundColor Red
    Write-Host "Ejecuta PowerShell como administrador y vuelve a correrlo." -ForegroundColor Yellow
    pause
    exit 1
}

$TaskName = "SincronizarResumenCorreos"
$TaskDescription = "Sincroniza correos institucionales para el dashboard cada 15 minutos"
$ScriptPath = "$PSScriptRoot\sincronizar_correos_resumen_auto.bat"
$WorkingDirectory = $PSScriptRoot
$IntervalMinutes = 15

if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: No se encontro el archivo $ScriptPath" -ForegroundColor Red
    pause
    exit 1
}

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[OK] Tarea anterior eliminada" -ForegroundColor Green
}

try {
    $Action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument "/c `"$ScriptPath`"" `
        -WorkingDirectory $WorkingDirectory

    $Trigger = New-ScheduledTaskTrigger `
        -Once `
        -At (Get-Date) `
        -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
        -RepetitionDuration ([TimeSpan]::MaxValue)

    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

    $Principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType S4U `
        -RunLevel Highest

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $TaskDescription `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal | Out-Null

    Write-Host "" 
    Write-Host "[OK] Tarea creada: $TaskName" -ForegroundColor Green
    Write-Host "Frecuencia: cada $IntervalMinutes minutos" -ForegroundColor White
    Write-Host "Log: logs\sincronizar_correos_resumen.log" -ForegroundColor White
    Write-Host ""

    $runNow = Read-Host "Deseas ejecutar una prueba ahora? (S/N)"
    if ($runNow -eq 'S' -or $runNow -eq 's') {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "[OK] Tarea ejecutada" -ForegroundColor Green
    }
}
catch {
    Write-Host "ERROR al crear la tarea:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "Configuracion completada." -ForegroundColor Green
pause
