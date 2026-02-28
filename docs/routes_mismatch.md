# API Route Mismatch Report

**Updated:** February 28, 2026
**Status:** 3 critical issues resolved. Remaining items require frontend work.

---

## Summary

| Category               | Count   |
| ---------------------- | ------- |
| ✅ Fixed               | 3       |
| 🔴 Needs frontend fix  | 1       |
| ⚠️ Missing frontend UI | 8 areas |

---

## 🔴 Still Needs Fixing — Frontend Bug

### Query strings appended directly to URL paths

```
GET /api/v1/preferences/admin/history/{preferenceId}${query}
GET /api/v1/preferences/agent/get/${key}${query}
GET /api/v1/preferences/agent/list${query}
```

- **File:** `services/preferences.ts`
- **Issue:** `${query}` is string-interpolated directly onto the path. Works accidentally when query is `?key=value` but will corrupt the URL if query is empty or malformed.
- **Fix:** Use `URLSearchParams` to append params properly:

```ts
const url = new URL(`/api/v1/preferences/agent/list`, window.location.origin);
if (agentId) url.searchParams.set("agent_id", agentId);
const response = await api.get(url.pathname + url.search);
```

---

## ⚠️ Backend Features With No Frontend UI

These backend routes are fully implemented but have no frontend caller. Each area represents an incomplete or missing UI feature.

### Governance & Voting

| Route                                         | File        | What's missing                                                                    |
| --------------------------------------------- | ----------- | --------------------------------------------------------------------------------- |
| `GET /api/v1/voting/amendments`               | `voting.py` | Amendments list — frontend only POSTs                                             |
| `GET /api/v1/voting/amendments/{id}`          | `voting.py` | Amendment detail view                                                             |
| `POST /api/v1/voting/amendments/{id}/vote`    | `voting.py` | Vote action on amendment                                                          |
| `GET /api/v1/voting/deliberations`            | `voting.py` | Deliberations list                                                                |
| `GET /api/v1/voting/deliberations/{id}`       | `voting.py` | Deliberation detail view                                                          |
| `POST /api/v1/voting/deliberations/{id}/vote` | `voting.py` | Vote action on deliberation                                                       |
| `GET /api/v1/constitution`                    | `main.py`   | `ConstitutionPage` POSTs amendments but never loads the current constitution text |
| `GET /api/v1/governance/idle/status`          | `main.py`   | Idle governance status panel                                                      |
| `POST /api/v1/governance/idle/pause`          | `main.py`   | Pause/resume idle governance controls                                             |
| `POST /api/v1/governance/idle/resume`         | `main.py`   | Pause/resume idle governance controls                                             |

---

### Monitoring & Violations

| Route                                              | File                   | What's missing                           |
| -------------------------------------------------- | ---------------------- | ---------------------------------------- |
| `GET /api/v1/monitoring/violations`                | `monitoring_routes.py` | Violations are reported but never listed |
| `PATCH /api/v1/monitoring/violations/{id}/resolve` | `monitoring_routes.py` | No resolve action in UI                  |
| `GET /api/v1/monitoring/dashboard/{monitor_id}`    | `monitoring_routes.py` | No per-monitor dashboard view            |

---

### Tasks

| Route                                        | File       | What's missing                                            |
| -------------------------------------------- | ---------- | --------------------------------------------------------- |
| `GET /api/v1/tasks/active`                   | `main.py`  | Frontend fetches all tasks, never the active-only subset  |
| `GET /api/v1/tasks/{id}/allowed-transitions` | `tasks.py` | UI likely hardcodes valid states instead of fetching them |
| `PATCH /api/v1/tasks/{id}`                   | `tasks.py` | No inline task edit in frontend                           |

---

### Agent Lifecycle

These were remapped from the broken `/terminate` endpoint (now fixed), but the full lifecycle management UI is still missing:

| Route                                               | File                  | What's missing          |
| --------------------------------------------------- | --------------------- | ----------------------- |
| `POST /api/v1/agents/lifecycle/promote`             | `lifecycle_routes.py` | No promote-to-lead UI   |
| `POST /api/v1/agents/lifecycle/bulk/liquidate-idle` | `lifecycle_routes.py` | No bulk liquidation UI  |
| `GET /api/v1/agents/lifecycle/capacity`             | `lifecycle_routes.py` | No capacity panel       |
| `GET /api/v1/agents/lifecycle/stats/lifecycle`      | `lifecycle_routes.py` | No lifecycle stats view |

---

### A/B Testing

The entire A/B testing feature has a backend but no frontend. `ABTestingPage.tsx` exists but only calls `GET /models/configs` (already fixed):

| Route                                             | File            | What's missing           |
| ------------------------------------------------- | --------------- | ------------------------ |
| `GET /api/v1/ab-testing/experiments`              | `ab_testing.py` | No experiments list      |
| `GET /api/v1/ab-testing/experiments/{id}`         | `ab_testing.py` | No experiment detail     |
| `POST /api/v1/ab-testing/experiments`             | `ab_testing.py` | No create experiment     |
| `POST /api/v1/ab-testing/experiments/{id}/cancel` | `ab_testing.py` | No cancel action         |
| `POST /api/v1/ab-testing/quick-test`              | `ab_testing.py` | No quick-test flow       |
| `GET /api/v1/ab-testing/recommendations`          | `ab_testing.py` | No recommendations panel |

---

### Tool Creation & Marketplace

The entire marketplace, versioning, and sunset workflow exists in the backend with zero frontend coverage:

| Route group                                      | File               | What's missing                                    |
| ------------------------------------------------ | ------------------ | ------------------------------------------------- |
| `GET /marketplace` + all `POST /marketplace/...` | `tool_creation.py` | Marketplace page, publish, import, rate, yank     |
| `GET /{tool}/versions/changelog`                 | `tool_creation.py` | Changelog view                                    |
| `GET /{tool}/versions/diff`                      | `tool_creation.py` | Version diff view                                 |
| `POST /{tool}/versions/propose-update`           | `tool_creation.py` | Propose version update                            |
| `POST /{tool}/versions/approve-update`           | `tool_creation.py` | Approve version update                            |
| `POST /{tool}/versions/rollback`                 | `tool_creation.py` | Rollback to prior version                         |
| All sunset routes                                | `tool_creation.py` | Schedule, execute, restore sunset workflow        |
| `GET /analytics/...` routes                      | `tool_creation.py` | Analytics report, error view, per-agent analytics |

---

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

## ✅ Fixed (removed from active tracking)

| Issue                                                                  | Resolution                                                                                                                            |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /models/configs` missing `/api/v1/` prefix in `ABTestingPage.tsx` | Fixed — prefix added                                                                                                                  |
| `POST /api/v1/agents/lifecycle/{id}/terminate` — endpoint didn't exist | Fixed — remapped to `POST /liquidate` in `agents.ts` with correct request body                                                        |
| `GET /api/v1/skills/{id}/full` — endpoint missing in backend           | Fixed — `GET /{skill_id}/full` added to `skills.py`; `POST /{skill_id}/deprecate` also added as it was called by frontend but missing |

---

_Intentionally excluded: sovereign routes, host_access routes, webhook receivers, and health/status endpoints — these are internal or externally-triggered and do not require frontend callers._
