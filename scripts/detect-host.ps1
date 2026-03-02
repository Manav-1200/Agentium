# scripts/detect-host.ps1 - Agentium OS probe for Windows
# Writes $env:USERPROFILE\.agentium\env.conf

$ErrorActionPreference = "Stop"

$CONF_DIR = Join-Path $env:USERPROFILE ".agentium"
$CONF_FILE = Join-Path $CONF_DIR "env.conf"
$LOG_FILE = Join-Path $CONF_DIR "detect.log"

New-Item -ItemType Directory -Force -Path $CONF_DIR | Out-Null
"" | Set-Content $CONF_FILE
"" | Set-Content $LOG_FILE

$WARN_COUNT = 0

function Write-Log($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    Add-Content -Path $LOG_FILE -Value $line
    Write-Host $line
}

function Write-Warn($msg) {
    $line = "[WARN] $msg"
    Add-Content -Path $LOG_FILE -Value $line
    Write-Warning $line
    $script:WARN_COUNT++
}

function Write-Conf($key, $val) {
    Add-Content -Path $CONF_FILE -Value "$key=$val"
}

function Write-SafeConf($key, $val, $fallback) {
    if ([string]::IsNullOrWhiteSpace($val)) {
        Write-Warn "Could not detect $key - using fallback: $fallback"
        Write-Conf $key $fallback
    } else {
        Write-Conf $key $val
    }
}

Write-Log "=== Agentium OS Detection Started ==="

# Step 1.1 - OS family
Write-Log "Step 1.1 - Detecting OS family"
$OS_FAMILY = "windows"
Write-Conf "OS_FAMILY" $OS_FAMILY
Write-Log "  OS_FAMILY=$OS_FAMILY"

# Step 1.2 - Windows version
Write-Log "Step 1.2 - Detecting Windows version"
try {
    $WIN_VERSION = (Get-ComputerInfo).OsName
} catch {
    $WIN_VERSION = "Windows (unknown version)"
}
Write-Conf "WIN_VERSION" $WIN_VERSION
Write-Log "  WIN_VERSION=$WIN_VERSION"

# Step 1.3 - Package manager
Write-Log "Step 1.3 - Selecting package manager"
$PKG_MGR = "pip"
if (Get-Command winget -ErrorAction SilentlyContinue) {
    $PKG_MGR = "winget"
} elseif (Get-Command choco -ErrorAction SilentlyContinue) {
    $PKG_MGR = "choco"
}
Write-Conf "PKG_MGR" $PKG_MGR
Write-Log "  PKG_MGR=$PKG_MGR"

# Step 1.4 - Python
Write-Log "Step 1.4 - Locating Python 3.10 or newer"
$PYTHON_BIN = $null
$candidates = @("python3.12", "python3.11", "python3.10", "python3", "python")
foreach ($candidate in $candidates) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) {
        try {
            $verCheck = & $cmd.Source -c "import sys; print(sys.version_info >= (3,10))" 2>$null
            if ($verCheck -eq "True") {
                $PYTHON_BIN = $cmd.Source
                break
            }
        } catch { continue }
    }
}

if (-not $PYTHON_BIN) {
    Write-Warn "No Python 3.10+ found - voice bridge venv will not be created"
    Write-Conf "PYTHON_BIN" "python3_missing"
} else {
    $verStr = & $PYTHON_BIN --version 2>&1
    Write-Conf "PYTHON_BIN" $PYTHON_BIN
    Write-Log "  PYTHON_BIN=$PYTHON_BIN ($verStr)"
}

# Step 1.5 - Microphone
Write-Log "Step 1.5 - Checking microphone"
$HAS_MIC = "true"
Write-Conf "HAS_MIC" $HAS_MIC
Write-Log "  HAS_MIC=$HAS_MIC (runtime detection via PyAudio)"

# Step 1.6 - Docker gateway
Write-Log "Step 1.6 - Detecting Docker gateway"
$DOCKER_GW = "172.17.0.1"
try {
    $dockerInfo = docker network inspect bridge --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}' 2>$null
    if ($dockerInfo) {
        $DOCKER_GW = $dockerInfo
    }
} catch { }
$BACKEND_URL = "http://${DOCKER_GW}:8000"
Write-Conf "BACKEND_URL" $BACKEND_URL
Write-Log "  BACKEND_URL=$BACKEND_URL"

# Step 1.7 - Service manager
Write-Log "Step 1.7 - Detecting service manager"
$SVC_MGR = "task_scheduler"
Write-Conf "SVC_MGR" $SVC_MGR
Write-Log "  SVC_MGR=$SVC_MGR"

# Step 1.8 - WS port and wake word
Write-Conf "WS_PORT" "9999"
Write-Conf "WAKE_WORD" "agentium"

Write-Log "=== Detection complete - $WARN_COUNT warning(s) - written to $CONF_FILE ==="