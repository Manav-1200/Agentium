# setup.ps1 - Windows entry point for Agentium Voice Bridge
# Usage: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
# Automatically requests UAC elevation if needed.

$ErrorActionPreference = "Stop"

# --- Resolve repo root BEFORE elevation (PSScriptRoot is valid here) ---------
# We pass it as an argument to the elevated process so it survives the re-launch.
$RepoRoot = Split-Path $PSScriptRoot -Parent

function Test-IsAdmin {
    ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Write-Host "Agentium needs administrator access to register the startup task." -ForegroundColor Yellow
    Write-Host "A UAC prompt will appear -- please click Yes to continue." -ForegroundColor Yellow
    Write-Host ""

    $scriptPath = $MyInvocation.MyCommand.Path

    # FIX: pass -RepoRoot explicitly so the elevated copy knows where the repo is
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName        = "powershell.exe"
    $psi.Arguments       = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -RepoRoot `"$RepoRoot`""
    $psi.Verb            = "runas"
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
# Accept -RepoRoot param (passed by the non-admin re-launch above)
param(
    [string]$RepoRoot = ""
)

# If not passed (user ran directly as admin), derive it normally
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path $PSScriptRoot -Parent
}

Write-Host "=== Agentium Voice Bridge Windows Installer ===" -ForegroundColor Cyan
Write-Host "Running as Administrator: YES"          -ForegroundColor Green
Write-Host "Repo root: $RepoRoot"
Write-Host ""

# Phase 1: OS detection
Write-Host "[setup.ps1] Running OS detection..." -ForegroundColor Yellow
$detectScript = Join-Path $RepoRoot "scripts\detect-host.ps1"
if (Test-Path $detectScript) {
    & $detectScript -RepoRoot $RepoRoot
} else {
    Write-Error "detect-host.ps1 not found at $detectScript"
    exit 1
}

# Phase 2+3: deps + service registration
Write-Host "[setup.ps1] Running dependency installer..." -ForegroundColor Yellow
$installScript = Join-Path $RepoRoot "scripts\install-voice-bridge.ps1"
if (Test-Path $installScript) {
    & $installScript -RepoRoot $RepoRoot
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
    Write-Host "  Task state: $state" -ForegroundColor $(if ($state -eq "Running") { "Green" } else { "Yellow" })
    if ($state -ne "Running") {
        Write-Host "  Starting task now..." -ForegroundColor Yellow
        Start-ScheduledTask -TaskName "AgentiumVoiceBridge" -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
        $state = (Get-ScheduledTask -TaskName "AgentiumVoiceBridge").State
        Write-Host "  Task state after start: $state" -ForegroundColor $(if ($state -eq "Running") { "Green" } else { "Red" })
    }
} else {
    Write-Warning "AgentiumVoiceBridge task not found -- check install.log"
}

Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host "  Check task  : Get-ScheduledTask -TaskName AgentiumVoiceBridge"
Write-Host "  Start bridge: Start-ScheduledTask -TaskName AgentiumVoiceBridge"
Write-Host "  View logs   : Get-Content `"$env:USERPROFILE\.agentium\voice-bridge.log`" -Tail 50"
Write-Host "  Check port  : netstat -ano | findstr :9999"
Write-Host ""

if ($Host.Name -eq "ConsoleHost") {
    Read-Host "Press Enter to close"
}