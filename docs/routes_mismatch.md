# API Route Mismatch Report

**Updated:** February 28, 2026
**Status:** 3 critical issues resolved. Remaining items require frontend work.

## 🔴 Still Needs Fixing — Frontend Bug

### Voice & Audio

| Route                                          | File       | What's missing          |
| ---------------------------------------------- | ---------- | ----------------------- |
| `GET /api/v1/voice/voices`                     | `voice.py` | No voice selector in UI |
| `GET /api/v1/voice/languages`                  | `voice.py` | No language selector    |
| `POST /api/v1/voice/synthesize`                | `voice.py` | TTS not wired up        |
| `POST /api/v1/voice/transcribe`                | `voice.py` | STT not wired up        |
| `GET /api/v1/voice/audio/{user_id}/{filename}` | `voice.py` | No audio playback       |

---

### Files

| Route                                             | File       | What's missing   |
| ------------------------------------------------- | ---------- | ---------------- |
| `GET /api/v1/files/list`                          | `files.py` | No file browser  |
| `GET /api/v1/files/download/{user_id}/{filename}` | `files.py` | No download link |
| `GET /api/v1/files/preview/{user_id}/{filename}`  | `files.py` | No file preview  |
| `POST /api/v1/files/upload`                       | `files.py` | No upload UI     |

---
