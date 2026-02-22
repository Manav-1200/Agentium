# Channel Verification Workflow

This document outlines the steps required to verify the integration and synchronization of external communication channels within the Agentium system, specifically ensuring alignment with the Unified Inbox architecture.

## Background Summary

The codebase has been refactored to support a Unified Inbox model:
- Incoming messages from all 11 external adapters (WhatsApp, Slack, Telegram, Email, etc.) are received via Webhooks in `backend/api/routes/webhooks.py`.
- Messages are processed by `ChannelManager.receive_message()` which normalizes them and saves them as `ExternalMessage` records.
- Crucially, `receive_message()` also translates them into the canonical `ChatMessage` format, appending them to a unified `Conversation` and firing a WebSocket broadcast to update the frontend Inbox in real-time.
- For outbound messages, the new `backend/api/routes/inbox.py` endpoint `POST /api/v1/inbox/conversations/{conversation_id}/reply` allows administrators to reply directly from the frontend Unified Inbox UI (`frontend/src/pages/InboxPage.tsx`), routing the message back out through `ChannelManager.send_response()`.

Automated testing using `pytest` was attempted but blocked due to the local Docker database (`agentium-postgres`) being unavailable in the development environment. 

## Verification Steps (Pending Execution)

When the development environment is fully operational (Database & Redis are online), complete the following steps to finalize channel verification:

### 1. Database & Environment Prep
1. Ensure the Docker containers are running (`docker-compose up -d`).
2. Verify PostgreSQL is accepting connections on `localhost:5432`.
3. Load test environment variables containing mock/staging tokens for the specific channels being tested.

### 2. Automated Script Testing
Run the verification script to ensure the core logic flow works end-to-end without needing real external APIs immediately:
```bash
# Ensure you are using the correct Python environment
export PYTHONPATH="/path/to/Agentium"
source backend/venv/bin/activate
python backend/scripts/verify_channels.py
```
*Note: This script mocks the adapters but verifies the actual database persistence and routing logic across the `ChannelManager`, `ExternalMessage`, and `ChatMessage` models.*

### 3. Manual E2E Verification (The "Real" Test)
For each priority channel currently configured (e.g., WhatsApp Web Bridge, Slack):

#### Inbound Synchronization
1. Send a message from the external client (e.g., your personal WhatsApp) to the connected Agentium bot/number.
2. Observe the backend logs: verify the webhook fires and no exceptions occur in `ChannelManager`.
3. Open the Agentium frontend dashboard.
4. Navigate to the **Unified Inbox** sidebar menu.
5. **Verify:** The message appears immediately via WebSocket, correctly attributed to the specific channel.

#### Outbound Routing
1. Select the conversation in the Unified Inbox.
2. Type a response and click **Send**.
3. Observe the backend logs: verify `ChannelManager.send_response()` successfully hands off to the respective adapter.
4. **Verify:** The message arrives on your external client device.

### 4. Edge Cases to Verify
- **Rate Limiting / Circuit Breaker:** Rapidly send 10+ messages to trigger rate limits; verify the circuit breaker toggles appropriately without crashing the service.
- **Rich Media Translation:** Send an image/file attachment; verify the adapter correctly transforms the payload into a standard `RichMediaContent` object.
- **Persistent Connectivity:** Stop and restart the backend container; ensure the channels (especially WebSocket-based ones like WhatsApp Web Bridge) automatically reconnect on boot.

# Channel Integration Verification & Alignment Task

## 1. Planning & Discovery
- [ ] Identify all supported channels in the backend
- [ ] Identify all channel configurations in the frontend
- [ ] Review [ChannelManager](file:///home/ashmin/Agentium/backend/services/channel_manager.py#779-1441) and specific channel adapters

## 2. Backend Verification
- [ ] Audit [models/entities/channels.py](file:///home/ashmin/Agentium/backend/models/entities/channels.py) and schema
- [ ] Audit [api/routes/channels.py](file:///home/ashmin/Agentium/backend/api/routes/channels.py) (CRUD, status, etc.)
- [ ] Audit [Webhook](file:///home/ashmin/Agentium/frontend/src/pages/ChannelsPage.tsx#475-479) and event receiving logic for each channel
- [x] Verify message normalization (unified format)
- [x] Verify message persistence without duplication
- [x] Check event broadcasting logic and loop prevention

## 3. Frontend Verification
- [ ] Verify channel display components (list, connection status)
- [ ] Verify connection/authentication flows per channel
- [x] Verify conversation sync UI and unified inbox
- [ ] Verify error handling and disconnected states

## 4. Full Flow Testing
- [ ] Setup and test Web channel (if applicable in another place? wait, Web is a channel too, user mentioned Web. Let's check Web bridge vs Web frontend)
- [ ] Setup and test WhatsApp channel (Cloud API & Web Bridge)
- [ ] Setup and test Slack channel
- [ ] Setup and test Telegram channel
- [ ] Setup and test Email (SMTP/IMAP) channel
- [ ] Setup and test Discord channel
- [ ] Setup and test Signal channel
- [ ] Setup and test Google Chat channel
- [ ] Setup and test Teams channel
- [ ] Setup and test Zalo channel
- [ ] Setup and test Matrix channel
- [ ] Setup and test iMessage channel
- [ ] Test cross-channel synchronization and persistence
- [ ] Test disconnect/reconnect flows

## 5. Reporting & Refactoring
- [ ] Draft verification report
- [ ] Implement refactors for any deviations (no breaking changes)
- [ ] Finalize testing of refactored code

