# setup.ps1 - Windows entry point for Agentium Voice Bridge
# Usage: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
# Automatically requests UAC elevation if needed.

$ErrorActionPreference = "Stop"

# --- Self-elevation: re-launch as Administrator if not already ---------------
function Test-IsAdmin {
    ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Write-Host "Agentium needs administrator access to register the startup task." -ForegroundColor Yellow
    Write-Host "A UAC prompt will appear -- please click Yes to continue." -ForegroundColor Yellow
    Write-Host ""

    $scriptPath = $MyInvocation.MyCommand.Path
    if (-not $scriptPath) {
        $scriptPath = Join-Path $env:TEMP "agentium-setup-elevated.ps1"
        Copy-Item $PSCommandPath $scriptPath -Force
    }

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "powershell.exe"
    $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
    $psi.Verb = "runas"
    $psi.UseShellExecute = $true

    try {
        $proc = [System.Diagnostics.Process]::Start($psi)
        $proc.WaitForExit()
        exit $proc.ExitCode
    } catch {
        Write-Host ""
        Write-Host "UAC elevation was cancelled or denied." -ForegroundColor Red
        Write-Host "To install manually, right-click PowerShell, choose Run as Administrator, then run:" -ForegroundColor Yellow
        Write-Host "  powershell -ExecutionPolicy Bypass -File `"$scriptPath`"" -ForegroundColor Cyan
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# --- Now running as Administrator --------------------------------------------
$REPO_ROOT = Split-Path $PSScriptRoot -Parent

Write-Host "=== Agentium Voice Bridge Windows Installer ===" -ForegroundColor Cyan
Write-Host "Running as Administrator: YES" -ForegroundColor Green
Write-Host "Repo root: $REPO_ROOT"
Write-Host ""

# Phase 1: OS detection
Write-Host "[setup.ps1] Running OS detection..." -ForegroundColor Yellow
$detectScript = Join-Path $REPO_ROOT "scripts\detect-host.ps1"
if (Test-Path $detectScript) {
    & $detectScript
} else {
    Write-Error "detect-host.ps1 not found at $detectScript"
    exit 1
}

# Phase 2+3: deps + service registration
Write-Host "[setup.ps1] Running dependency installer..." -ForegroundColor Yellow
$installScript = Join-Path $REPO_ROOT "scripts\install-voice-bridge.ps1"
if (Test-Path $installScript) {
    & $installScript
} else {
    Write-Error "install-voice-bridge.ps1 not found at $installScript"
    exit 1
}

Write-Host ""
Write-Host "=== Voice bridge installation complete ===" -ForegroundColor Green
Write-Host "Log: $env:USERPROFILE\.agentium\install.log"
Write-Host ""

# Verify the scheduled task
Write-Host "[setup.ps1] Verifying scheduled task..." -ForegroundColor Yellow
$task = Get-ScheduledTask -TaskName "AgentiumVoiceBridge" -ErrorAction SilentlyContinue
if ($task) {
    $state = $task.State
    if ($state -eq "Running") {
        Write-Host "  Task state: $state" -ForegroundColor Green
    } else {
        Write-Host "  Task state: $state" -ForegroundColor Yellow
    }
    if ($state -ne "Running") {
        Write-Host "  Starting task now..." -ForegroundColor Yellow
        Start-ScheduledTask -TaskName "AgentiumVoiceBridge" -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        $state = (Get-ScheduledTask -TaskName "AgentiumVoiceBridge").State
        if ($state -eq "Running") {
            Write-Host "  Task state after start: $state" -ForegroundColor Green
        } else {
            Write-Host "  Task state after start: $state" -ForegroundColor Red
        }
    }
} else {
    Write-Warning "AgentiumVoiceBridge task not found -- check install.log"
}

Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host "  Check status : Get-ScheduledTask -TaskName AgentiumVoiceBridge"
Write-Host "  Start bridge : Start-ScheduledTask -TaskName AgentiumVoiceBridge"
Write-Host "  View logs    : Get-Content `"$env:USERPROFILE\.agentium\voice-bridge.log`" -Tail 50"
Write-Host ""

if ($Host.Name -eq "ConsoleHost") {
    Read-Host "Press Enter to close"
}