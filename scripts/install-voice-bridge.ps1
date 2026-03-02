# scripts/install-voice-bridge.ps1 - Agentium voice bridge installer (Windows)
# Reads $env:USERPROFILE\.agentium\env.conf written by detect-host.ps1
# NOTE: Called from setup.ps1 which already handles UAC elevation.

$ErrorActionPreference = "Continue"

$CONF_DIR   = Join-Path $env:USERPROFILE ".agentium"
$CONF_FILE  = Join-Path $CONF_DIR "env.conf"
$LOG_FILE   = Join-Path $CONF_DIR "install.log"
$VENV_DIR   = Join-Path $CONF_DIR "voice-venv"
$REPO_ROOT  = Split-Path $PSScriptRoot -Parent
$BRIDGE_DIR = Join-Path $REPO_ROOT "voice-bridge"

New-Item -ItemType Directory -Force -Path $CONF_DIR | Out-Null

function Write-Log($msg) {
    $ts   = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    Add-Content -Path $LOG_FILE -Value $line
    Write-Host $line
}

function Write-Warn($msg) {
    $line = "[WARN] $msg"
    Add-Content -Path $LOG_FILE -Value $line
    Write-Warning $msg
}

function Run-Or-Warn($label, [scriptblock]$block) {
    try {
        $out = & $block 2>&1
        $out | ForEach-Object { Add-Content -Path $LOG_FILE -Value "$_" }
        Write-Log "  OK: $label"
        return $true
    } catch {
        Write-Warn "$label failed: $_"
        return $false
    }
}

# --- Load env.conf -----------------------------------------------------------
if (-not (Test-Path $CONF_FILE)) {
    Write-Warn "env.conf not found -- run detect-host.ps1 first"
    exit 1
}

$conf = @{}
Get-Content $CONF_FILE | ForEach-Object {
    if ($_ -match "^([^#=]+)=(.*)$") {
        $conf[$matches[1].Trim()] = $matches[2].Trim()
    }
}

$OS_FAMILY   = $conf["OS_FAMILY"]
$PKG_MGR     = $conf["PKG_MGR"]
$PYTHON_BIN  = $conf["PYTHON_BIN"]
$BACKEND_URL = $conf["BACKEND_URL"]

Write-Log "=== Agentium Voice Bridge Installer (Windows) ==="
Write-Log "OS_FAMILY=$OS_FAMILY  PKG_MGR=$PKG_MGR  PYTHON_BIN=$PYTHON_BIN"

# --- Step 2.1  System audio --------------------------------------------------
Write-Log "Step 2.1 - Windows audio subsystem"
Write-Log "  OK: PyAudio ships precompiled PortAudio for Windows"

# --- Step 2.2  Python venv ---------------------------------------------------
Write-Log "Step 2.2 - Creating Python venv at $VENV_DIR"

if ($PYTHON_BIN -eq "python3_missing") {
    Write-Warn "Python 3.10+ not found -- skipping venv and pip installs"
} else {
    Run-Or-Warn "create venv" { & $PYTHON_BIN -m venv $VENV_DIR }

    Write-Log "Step 2.3 - Installing Python packages"
    $VENV_PIP = Join-Path $VENV_DIR "Scripts\pip.exe"

    if (-not (Test-Path $VENV_PIP)) {
        Write-Warn "pip not found at $VENV_PIP -- venv creation may have failed"
    } else {
        Run-Or-Warn "pip upgrade"         { & $VENV_PIP install --upgrade pip }
        Run-Or-Warn "install websockets"  { & $VENV_PIP install "websockets>=12.0" }
        Run-Or-Warn "install SpeechRecog" { & $VENV_PIP install "SpeechRecognition>=3.10.4" }
        Run-Or-Warn "install PyAudio"     { & $VENV_PIP install "PyAudio>=0.2.14" }
        Run-Or-Warn "install pyttsx3"     { & $VENV_PIP install "pyttsx3>=2.90" }
        Run-Or-Warn "install python-jose" { & $VENV_PIP install "python-jose[cryptography]>=3.3.0" }
    }

    $VENV_PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"
    $existing = Get-Content $CONF_FILE -Raw -ErrorAction SilentlyContinue
    if ($existing -notmatch "VENV_PYTHON=") {
        Add-Content -Path $CONF_FILE -Value "VENV_PYTHON=$VENV_PYTHON"
    }
}

# --- Step 3  Scheduled task --------------------------------------------------
Write-Log "Step 3 - Registering Windows scheduled task"

$VENV_PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"
$MainPy      = Join-Path $BRIDGE_DIR "main.py"
$LogFile     = Join-Path $CONF_DIR "voice-bridge.log"
$TaskName    = "AgentiumVoiceBridge"

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Warn "venv Python not found at $VENV_PYTHON"
}
if (-not (Test-Path $MainPy)) {
    Write-Warn "main.py not found at $MainPy -- BRIDGE_DIR=$BRIDGE_DIR"
}

# Remove existing task
Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue

$cmdArgs   = "/c `"`"$VENV_PYTHON`" `"$MainPy`"`" >> `"$LogFile`" 2>&1"
$action    = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmdArgs
$trigger   = New-ScheduledTaskTrigger -AtLogon -User "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited
$settings  = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

try {
    Register-ScheduledTask `
        -TaskName  $TaskName `
        -Action    $action `
        -Trigger   $trigger `
        -Principal $principal `
        -Settings  $settings `
        -Force | Out-Null

    Write-Log "  Scheduled task '$TaskName' registered successfully"

    Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $state = (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue).State
    Write-Log "  Task state: $state"
    Write-Log "  Bridge log: $LogFile"

} catch {
    Write-Warn "Scheduled task registration failed: $_"
    Write-Warn "Falling back to Startup folder shortcut..."

    $startupFolder = [Environment]::GetFolderPath("Startup")
    $startupBat    = Join-Path $startupFolder "agentium-voice-bridge.bat"
    $batContent    = "@echo off`r`nstart `"`" /min cmd /c `"`"`"$VENV_PYTHON`"`" `"`"$MainPy`"`" >> `"`"$LogFile`"`" 2>&1`""
    Set-Content -Path $startupBat -Value $batContent -Encoding ASCII
    Write-Log "  Startup bat written to: $startupBat"
    Write-Log "  Bridge will auto-start on next login."
    Write-Log "  To start NOW: double-click $startupBat"
}

Write-Log "=== Installation complete. Check $LOG_FILE for any warnings. ==="