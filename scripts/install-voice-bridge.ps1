# scripts/install-voice-bridge.ps1 - Agentium voice bridge installer (Windows)
# Reads $env:USERPROFILE\.agentium\env.conf written by detect-host.ps1
# NOTE: Called from setup.ps1 which already handles UAC elevation.
# Usage: install-voice-bridge.ps1 [-RepoRoot <path>]

param(
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Continue"

$CONF_DIR  = Join-Path $env:USERPROFILE ".agentium"
$CONF_FILE = Join-Path $CONF_DIR "env.conf"
$LOG_FILE  = Join-Path $CONF_DIR "install.log"
$VENV_DIR  = Join-Path $CONF_DIR "voice-venv"

New-Item -ItemType Directory -Force -Path $CONF_DIR | Out-Null
"" | Set-Content $LOG_FILE

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

$PYTHON_BIN  = $conf["PYTHON_BIN"]
$BACKEND_URL = $conf["BACKEND_URL"]

# FIX: Resolve REPO_ROOT from (in priority order):
#  1. -RepoRoot parameter passed from setup.ps1
#  2. REPO_ROOT key written to env.conf by detect-host.ps1
#  3. PSScriptRoot relative path (only correct if not running from TEMP)
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = $conf["REPO_ROOT"]
}
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $candidate = Split-Path $PSScriptRoot -Parent
    # Sanity check: PSScriptRoot should contain a voice-bridge folder
    if (Test-Path (Join-Path $candidate "voice-bridge\main.py")) {
        $RepoRoot = $candidate
    }
}
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    Write-Warn "Cannot determine REPO_ROOT -- will attempt to find main.py in common locations"
}

$BRIDGE_DIR = if ($RepoRoot) { Join-Path $RepoRoot "voice-bridge" } else { "" }
$MainPy     = if ($BRIDGE_DIR) { Join-Path $BRIDGE_DIR "main.py" } else { "" }

Write-Log "=== Agentium Voice Bridge Installer (Windows) ==="
Write-Log "REPO_ROOT=$RepoRoot"
Write-Log "BRIDGE_DIR=$BRIDGE_DIR"
Write-Log "PYTHON_BIN=$PYTHON_BIN"
Write-Log "BACKEND_URL=$BACKEND_URL"

# Validate main.py exists early so we surface the error clearly
if ($MainPy -and -not (Test-Path $MainPy)) {
    Write-Warn "main.py not found at $MainPy"
    Write-Warn "Searched REPO_ROOT=$RepoRoot"
    Write-Warn "If your repo is in a different location, set REPO_ROOT in $CONF_FILE"
} else {
    Write-Log "  main.py found at $MainPy"
}

# --- Step 2.1  System audio --------------------------------------------------
Write-Log "Step 2.1 - Windows audio (PyAudio ships PortAudio precompiled)"

# --- Step 2.2  Python venv ---------------------------------------------------
Write-Log "Step 2.2 - Creating Python venv at $VENV_DIR"

if ($PYTHON_BIN -eq "python3_missing" -or [string]::IsNullOrWhiteSpace($PYTHON_BIN)) {
    Write-Warn "Python 3.10+ not found -- skipping venv and pip installs"
    Write-Warn "Install Python from https://www.python.org/downloads/ then re-run setup.ps1"
} else {
    Run-Or-Warn "create venv" { & $PYTHON_BIN -m venv $VENV_DIR }

    Write-Log "Step 2.3 - Installing Python packages"
    $VENV_PIP    = Join-Path $VENV_DIR "Scripts\pip.exe"
    $VENV_PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"

    if (-not (Test-Path $VENV_PIP)) {
        Write-Warn "pip not found at $VENV_PIP -- venv creation may have failed"
    } else {
        Run-Or-Warn "pip upgrade"          { & $VENV_PIP install --upgrade pip --quiet }
        Run-Or-Warn "install websockets"   { & $VENV_PIP install "websockets>=12.0" --quiet }
        Run-Or-Warn "install SpeechRecog"  { & $VENV_PIP install "SpeechRecognition>=3.10.4" --quiet }
        Run-Or-Warn "install python-jose"  { & $VENV_PIP install "python-jose[cryptography]>=3.3.0" --quiet }
        Run-Or-Warn "install pyttsx3"      { & $VENV_PIP install "pyttsx3>=2.90" --quiet }

        # FIX: PyAudio has no official wheel for Python 3.12+ on Windows.
        # Try the official wheel first; fall back to pipwin which fetches unofficial builds.
        Write-Log "  Installing PyAudio (trying official wheel first)..."
        $pyaudioOk = $false
        try {
            $out = & $VENV_PIP install "PyAudio>=0.2.14" --quiet 2>&1
            $out | ForEach-Object { Add-Content -Path $LOG_FILE -Value "$_" }
            if ($LASTEXITCODE -eq 0) {
                Write-Log "  OK: install PyAudio (official)"
                $pyaudioOk = $true
            }
        } catch { }

        if (-not $pyaudioOk) {
            Write-Warn "Official PyAudio wheel failed -- trying pipwin fallback"
            try {
                & $VENV_PIP install pipwin --quiet 2>&1 | Out-Null
                & $VENV_PYTHON -m pipwin install pyaudio 2>&1 | ForEach-Object {
                    Add-Content -Path $LOG_FILE -Value "$_"
                }
                if ($LASTEXITCODE -eq 0) {
                    Write-Log "  OK: install PyAudio (via pipwin)"
                    $pyaudioOk = $true
                }
            } catch { }
        }

        if (-not $pyaudioOk) {
            Write-Warn "PyAudio install failed -- microphone capture will be disabled"
            Write-Warn "Manual fix: download the wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio"
            Write-Warn "Then run: $VENV_PIP install <downloaded-whl-file>"
        }
    }

    # Write venv python path back to env.conf
    $existing = Get-Content $CONF_FILE -Raw -ErrorAction SilentlyContinue
    if ($existing -notmatch "VENV_PYTHON=") {
        Add-Content -Path $CONF_FILE -Value "VENV_PYTHON=$VENV_PYTHON"
    }
    if ($existing -notmatch "REPO_ROOT=") {
        Add-Content -Path $CONF_FILE -Value "REPO_ROOT=$RepoRoot"
    }
}

# --- Step 3  Scheduled task --------------------------------------------------
Write-Log "Step 3 - Registering Windows scheduled task"

$VENV_PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"
$LogFile     = Join-Path $CONF_DIR "voice-bridge.log"
$TaskName    = "AgentiumVoiceBridge"

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Warn "venv Python not found at $VENV_PYTHON -- task will be registered but may fail to run"
}
if (-not $MainPy -or -not (Test-Path $MainPy)) {
    Write-Warn "main.py not found -- task will be registered but will fail until main.py is present"
    if (-not $MainPy) { $MainPy = "C:\MISSING\voice-bridge\main.py" }
}

# Remove existing task cleanly
Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue

# FIX: Use Start-Process approach instead of cmd.exe with nested quotes.
# Write a small launcher .bat that is trivially quotable in the task XML.
$LauncherBat = Join-Path $CONF_DIR "start-voice-bridge.bat"
$batLines = @(
    "@echo off",
    ":: Auto-generated by Agentium installer",
    "set LOGFILE=$LogFile",
    "`"$VENV_PYTHON`" `"$MainPy`" >> `"%LOGFILE%`" 2>&1"
)
$batLines | Set-Content -Path $LauncherBat -Encoding ASCII
Write-Log "  Launcher bat written: $LauncherBat"

# Scheduled task runs the bat file directly -- no nested quoting needed
$action    = New-ScheduledTaskAction -Execute $LauncherBat
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
    Write-Log "  Launcher: $LauncherBat"
    Write-Log "  Bridge log: $LogFile"

    # Start it immediately
    Write-Log "  Starting bridge now..."
    Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    $state = (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue).State
    Write-Log "  Task state: $state"

    if ($state -ne "Running") {
        Write-Warn "Task is not Running (state=$state) -- attempting direct launch"
        # Direct fallback: start the bridge in a hidden window right now
        Start-Process -FilePath $LauncherBat -WindowStyle Hidden -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        Write-Log "  Direct launch attempted. Check: netstat -ano | findstr :9999"
    }

} catch {
    Write-Warn "Scheduled task registration failed: $_"
    Write-Warn "Falling back to Startup folder shortcut..."

    $startupFolder = [Environment]::GetFolderPath("Startup")
    $startupBat    = Join-Path $startupFolder "agentium-voice-bridge.bat"
    Copy-Item $LauncherBat $startupBat -Force
    Write-Log "  Startup bat written: $startupBat"
    Write-Log "  Bridge will auto-start on next login."
    Write-Log "  To start NOW, run: $LauncherBat"

    # Also start directly right now
    Start-Process -FilePath $LauncherBat -WindowStyle Hidden -ErrorAction SilentlyContinue
    Write-Log "  Direct launch attempted. Check: netstat -ano | findstr :9999"
}

Write-Log "=== Installation complete. Check $LOG_FILE for details. ==="