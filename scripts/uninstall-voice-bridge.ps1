# scripts/uninstall-voice-bridge.ps1
# Stops and removes the Agentium voice bridge. Non-destructive to Docker stack.
# Automatically requests UAC elevation if needed.

$ErrorActionPreference = "Continue"

# --- Self-elevation ----------------------------------------------------------
function Test-IsAdmin {
    ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Write-Host "Agentium uninstaller needs administrator access." -ForegroundColor Yellow
    Write-Host "A UAC prompt will appear -- please click Yes to continue." -ForegroundColor Yellow

    $scriptPath = $MyInvocation.MyCommand.Path
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName        = "powershell.exe"
    $psi.Arguments       = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
    $psi.Verb            = "runas"
    $psi.UseShellExecute = $true

    try {
        $proc = [System.Diagnostics.Process]::Start($psi)
        $proc.WaitForExit()
        exit $proc.ExitCode
    } catch {
        Write-Host "UAC elevation cancelled. Uninstall aborted." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

$CONF_DIR  = Join-Path $env:USERPROFILE ".agentium"
$TaskName  = "AgentiumVoiceBridge"

function Write-Log($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" }

Write-Log "=== Agentium Voice Bridge Uninstaller ==="

# --- Stop and remove scheduled task ------------------------------------------
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    if ($task.State -eq "Running") {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Write-Log "Task stopped."
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Log "Scheduled task '$TaskName' removed."
} else {
    Write-Log "Scheduled task '$TaskName' not found -- skipping."
}

# --- Remove Startup folder files ---------------------------------------------
$startupFolder = [Environment]::GetFolderPath("Startup")

$startupBat = Join-Path $startupFolder "agentium-voice-bridge.bat"
if (Test-Path $startupBat) {
    Remove-Item $startupBat -Force
    Write-Log "Removed: $startupBat"
}

$startupStub = Join-Path $startupFolder "agentium-voice-startup.cmd"
if (Test-Path $startupStub) {
    Remove-Item $startupStub -Force
    Write-Log "Removed: $startupStub"
}

Write-Log "Venv and conf files left in $CONF_DIR (remove manually if desired)"
Write-Log "=== Uninstall complete ==="

if ($Host.Name -eq "ConsoleHost") {
    Read-Host "Press Enter to close"
}