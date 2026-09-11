param([string]$TaskName = 'PortalNexy Forward Paper')
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$ConfigPath = Join-Path $ProjectRoot 'trading_backend\.env.forward'
if (!(Test-Path -LiteralPath $PythonPath) -or !(Test-Path -LiteralPath $ConfigPath)) {
    throw 'Create .venv and trading_backend/.env.forward before registering the service.'
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw 'A task with this name already exists. Inspect it before making changes.'
}
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument '-m trading_backend.forward.service' -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 20 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description 'PortalNexy paper-only forward experiment. Requires paper Gateway login; strategy start is explicit.'
Write-Output 'Registered but not started. Start from Task Scheduler after read-only preflight. User must remain logged in; browser may close.'
