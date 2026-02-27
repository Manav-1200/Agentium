#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Agentium Entrypoint — starts Xvfb then the app
# Xvfb failure is non-fatal: app still starts,
# but desktop tools will be unavailable.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set -e

DISPLAY_NUM="${DISPLAY:-:99}"
RESOLUTION="${XVFB_RESOLUTION:-1920x1080x24}"
DISPLAY_NUM_CLEAN="${DISPLAY_NUM#:}"

# ── 1. Set up Xauthority ────────────────────────
export XAUTHORITY="${HOME}/.Xauthority"
touch "${XAUTHORITY}" 2>/dev/null || true

# Generate a random auth cookie so Xlib stops complaining
if command -v xauth >/dev/null 2>&1; then
    COOKIE=$(mcookie 2>/dev/null || openssl rand -hex 16 2>/dev/null || echo "deadbeefdeadbeefdeadbeefdeadbeef")
    xauth add "${DISPLAY_NUM}" . "${COOKIE}" 2>/dev/null || true
fi

# ── 2. Start Xvfb (virtual display) ────────────
start_xvfb() {
    echo "🖥️  Starting Xvfb on display ${DISPLAY_NUM} (${RESOLUTION})..."

    # Clean up stale lock files from unclean restarts
    rm -f "/tmp/.X${DISPLAY_NUM_CLEAN}-lock" 2>/dev/null || true

    # -auth uses our Xauthority file for proper auth
    Xvfb "${DISPLAY_NUM}" -screen 0 "${RESOLUTION}" -auth "${XAUTHORITY}" +extension GLX +render -noreset &
    XVFB_PID=$!

    # Wait up to 5 seconds for Xvfb to be ready
    for i in $(seq 1 10); do
        if xdpyinfo -display "${DISPLAY_NUM}" >/dev/null 2>&1; then
            echo "✅ Xvfb is ready (PID: ${XVFB_PID})"
            export DISPLAY="${DISPLAY_NUM}"
            return 0
        fi
        sleep 0.5
    done

    echo "⚠️  Xvfb did not start in time — desktop tools will be unavailable"
    kill "${XVFB_PID}" 2>/dev/null || true
    return 1
}

if command -v Xvfb >/dev/null 2>&1; then
    start_xvfb || true   # non-fatal: app still starts if Xvfb fails
else
    echo "⚠️  Xvfb not found — desktop tools will be unavailable"
fi

# ── 3. Verify Chromium for nodriver ────────────
CHROME_BIN="${CHROME_BIN:-/usr/bin/chromium}"
if command -v "${CHROME_BIN}" >/dev/null 2>&1; then
    CHROME_VERSION=$("${CHROME_BIN}" --version 2>/dev/null || echo "unknown")
    echo "✅ Chromium found for nodriver: ${CHROME_VERSION} (${CHROME_BIN})"
else
    echo "⚠️  Chromium not found at ${CHROME_BIN} — nodriver/stealth browser will be unavailable"
fi

# ── 4. Run DB migrations ────────────────────────
echo "🔄 Running DB init..."
python scripts/init_db.py

# ── 5. Hand off to CMD (uvicorn / celery / etc.) ─
echo "🚀 Starting: $*"
exec "$@"