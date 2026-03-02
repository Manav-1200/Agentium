@echo off
:: Agentium Voice Bridge — auto-start on Windows login
:: Placed in Startup folder by docker-compose voice-autoinstall service.
:: Runs bootstrap silently in background; UAC prompt shown only on first install.
start "" /min cmd /c "%USERPROFILE%\.agentium\bootstrap-voice.cmd"