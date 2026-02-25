# 🏛️ Agentium

> Your Personal AI Agent Nation — Sovereign, Constitutional, and Fully Self-Governing.

[![Status](https://img.shields.io/badge/status-active--development-brightgreen)](https://github.com/AshminDhungana/Agentium)
[![Version](https://img.shields.io/badge/version-0.7.0--alpha-blue)](https://github.com/AshminDhungana/Agentium)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://www.docker.com/)

**Agentium** transforms AI task execution into a structured digital democracy. Unlike monolithic AI assistants, Agentium operates as a self-governing ecosystem where AI agents function like a parliamentary system — complete with a **Head of Council** (Executive), **Council Members** (Legislature), **Lead Agents** (Directors), **Task Agents** (Executors), and **Critic Agents** (Independent Judiciary) — all bound by a **Constitution** and managed through democratic voting.

Built for those who believe AI should be **transparent, accountable, and sovereign**, Agentium runs entirely on your infrastructure with local-first architecture.

## ![Image](./docs/dashboard.png)

---

## ✨ What Makes Agentium Unique?

### 🏛️ Democratic AI Governance

Tasks aren't just executed; they're deliberated. The Council votes on constitutional amendments, resource allocation, and major system changes. Every decision is logged, auditable, and reversible.

### ⚖️ Constitutional Framework

A living document stored in dual storage that all agents access before acting. Agents literally ask _"Is this constitutional?"_ before every action. Amendments require democratic approval with a 60% quorum.

### 🧠 Collective Intelligence (Knowledge Library)

- **Dual-Storage Architecture**: PostgreSQL for structured data, ChromaDB for semantic knowledge
- **Shared Memory**: Task agents share learnings; Council curates institutional knowledge
- **RAG-Powered**: World knowledge retrieved via semantic search using `all-MiniLM-L6-v2` embeddings
- **Revision-Aware**: No knowledge is stored blindly — all entries are deduplication-checked and revision-aware

### 🔐 Brains vs. Hands (Remote Code Execution)

A sandboxed Docker executor separates reasoning from execution. Raw data **never** enters agent context. Agents reason about data shape and schema only — PII and working sets stay inside the execution layer.

### 🔌 Constitutional MCP Tool Governance

MCP servers are integrated through the Constitution, not around it. Every tool invocation is audited. Tools are tiered: Pre-Approved (Council vote to use), Restricted (Head approval per use), or Forbidden (constitutionally banned).

### 💬 Unified Multimodal Inbox

One user. One conversation. All channels. Text, image, video, audio, and files are normalized into a single canonical conversation state. Channels are transport layers only — the conversation is sovereign and channel-agnostic.

### 🏗️ Hierarchical Agent IDs

Rigorous identification system:

- **Head**: `0xxxx` (00001–09999) — The Sovereign's direct representative
- **Council**: `1xxxx` (10001–19999) — Democratic deliberation layer
- **Lead**: `2xxxx` (20001–29999) — Department coordination
- **Task**: `3xxxx` (30001–69999) — Execution workers
- **Code Critic**: `7xxxx` (70001–79999) — Code validation (syntax, security, logic)
- **Output Critic**: `8xxxx` (80001–89999) — Output validation (user intent alignment)
- **Plan Critic**: `9xxxx` (90001–99999) — Plan validation (DAG soundness)

> Critics operate **outside** the democratic chain. They have veto authority with checks and balances implimented but no voting rights. Rejected tasks retry within the same team (max 5 retries) before escalating to Council.

### 🔄 Self-Governing Lifecycle

Agents auto-spawn when load increases, auto-terminate when tasks complete, and can be liquidated by Council vote if they violate the Constitution or remain idle >7 days.

---

## 🏗️ Architecture

### Full Governance Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AGENTIUM GOVERNANCE STACK                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 💬 Interface Layer                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  Web Dashboard (React+Vite)      │  WhatsApp    Telegram    Discord         │
│  ├─ Agent Tree Visualization     │  Slack       Signal      Google Chat     │
│  ├─ Voting Interface             │  Teams       Matrix      iMessage        │
│  ├─ Critic Review Dashboard      │  Zalo        API                         │
│  ├─ Constitution Editor          │                                          │
│  ├─ Checkpoint Timeline          │                                          │
│  └─ MCP Tool Registry            │                                          │
└───────────────────────────────────┴──────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ ⚡ Control Layer                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  FastAPI Gateway    │  WebSocket Hub    │  Redis Message Bus                │
│  ├─ Agent Orchestrator                  │  Hierarchical Routing             │
│  ├─ Constitutional Guard (2-tier)       │  3x→2x→1x→0x Routing             │
│  ├─ Context Ray Tracer                  │  Persistent Queues                │
│  ├─ Voting Service                      │  Time-Travel Recovery             │
│  ├─ Unified Inbox / Channel Manager     │                                   │
│  └─ Checkpoint Service                  │                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
┌───────────────────────────────┐           ┌───────────────────────────────┐
│ 🏛️ Governance Layer           │           │ 💾 Storage Layer               │
├───────────────────────────────┤           ├───────────────────────────────┤
│ 👑 Head (0xxxx)               │           │ PostgreSQL (Structured Truth)  │
│ ├─ Veto Power                 │           │ ├─ Agent Entities              │
│ ├─ Emergency Override         │           │ ├─ Voting Records              │
│ ├─ Genesis Protocol           │           │ ├─ Audit Logs                  │
│ └─ Final Approval             │           │ ├─ Constitution Versions       │
│                               │           │ ├─ Checkpoint States           │
│ ⚖️ Council (1xxxx)             │           │ ├─ MCP Tool Registry           │
│ ├─ Propose Amendments         │           │ └─ Conversation / Message      │
│ ├─ Vote on Tasks              │           │                                │
│ ├─ Knowledge Moderation       │           │ ChromaDB (Vector Meaning)      │
│ ├─ Agent Liquidation          │           │ ├─ Constitution (embeddings)   │
│ └─ Strategic Decisions        │           │ ├─ Task Learnings (RAG)        │
│                               │           │ ├─ Best Practices              │
│ 🎯 Lead (2xxxx)               │           │ └─ Staged Knowledge            │
│ ├─ Spawn Task Agents          │           │                                │
│ ├─ Delegate Work              │           │ Object Storage                 │
│ ├─ Resource Allocation        │           │ ├─ User Media (images, video)  │
│ └─ Aggregate Results          │           │ ├─ AI-Generated Media          │
│                               │           │ └─ File Attachments            │
│ 🤖 Task (3xxxx)               │           └───────────────────────────────┘
│ ├─ Execute Commands           │
│ ├─ Generate Code              │
│ ├─ Submit Learnings           │
│ └─ Query Knowledge            │
└───────────────┬───────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🔍 Execution Validation Layer (Critics — Independent Judiciary)             │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐       │
│  │ Plan Critic 9xxxx│   │ Code Critic 7xxxx│   │ Output Critic 8x │       │
│  │ DAG Soundness    │   │ Syntax/Security  │   │ User Intent      │       │
│  │ VETO → Retry     │   │ VETO → Retry     │   │ VETO → Retry     │       │
│  │ ESCALATE→Council │   │ ESCALATE→Lead    │   │ ESCALATE→Lead    │       │
│  └──────────────────┘   └──────────────────┘   └──────────────────┘       │
│                                                                             │
│  ┌──────────────────────┐         ┌──────────────────────┐                │
│  │  REMOTE EXECUTOR     │         │  CHECKPOINT SERVICE  │                │
│  │  (Sandboxed Docker)  │         │  (State Capture)     │                │
│  │  Raw data never      │         │  Phase Boundaries    │                │
│  │  enters agent ctx    │         │  Time-Travel/Branch  │                │
│  └──────────────────────┘         └──────────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🧠 Background Processing Layer                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Celery Workers       │  Constitutional Patrol   │  Knowledge Maintenance   │
│  ├─ Task Queue        │  (Heartbeat)             │  (Deduplication)         │
│  ├─ Vote Tally        │  Compliance Checks       │  Embedding Updates       │
│  ├─ Critic Queue      │  Auto-termination        │  Orphaned Data Cleanup   │
│  └─ Agent Liquidation │  Idle Detection          │  Semantic Indexing       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

**Separation of Powers**

- **Executive** (Head): Final approval, emergency override
- **Legislative** (Council): Voting, amendments, strategic policy
- **Judicial** (Critics): Independent validation, veto authority — outside the democratic chain
- **Workers** (Task/Lead): Execution without political influence

**Democratic Accountability**

- All Council votes stored in PostgreSQL with timestamp, tally, and agent signatures
- Constitution changes require 60% quorum + Head ratification
- Agent liquidation requires Council vote or constitutional violation proof
- Every action traceable to a specific agent ID

**Knowledge Sovereignty**

- **PostgreSQL**: Source of truth for entities, hierarchies, votes, conversations
- **ChromaDB**: Semantic understanding (embeddings of constitution, learnings)
- **Dual Query**: Agents query both databases before major decisions
- **RAG Pipeline**: Task agents retrieve past learnings and constitutional context automatically

**Cognitive Discipline (Ethos)**

- Each agent maintains a minimal working memory (Ethos) — continuously updated, never bloated
- Ethos is read before task execution, updated during, compressed after
- Higher-tier agents may view and correct subordinate Ethos
- Constitutional recalibration occurs between every task

---

## 🚀 Quick Start

### Prerequisites

- Docker Desktop (Windows/macOS) or Docker Engine + Compose (Linux)
- 8 GB RAM minimum (16 GB recommended)
- 10 GB free disk space

### Installation

```bash
# Clone the repository
git clone https://github.com/AshminDhungana/Agentium.git
cd Agentium

# Launch the stack
docker compose up -d
# First build takes 10–20 minutes

# Watch initialization logs
docker compose logs -f

# Access the dashboard
open http://localhost:3000
```

**First Login**: You'll be guided through the **Genesis Protocol** — your AI Nation is named by democratic Council vote before any tasks are accepted.

### System Requirements

- Works identically on **Windows, macOS, and Linux**
- No local Python/Node setup required — everything runs in Docker
- Ideal for local development, experimentation, and self-hosting

---

## 🏠 Self-Hosting Guide

👉 [Self-Hosting Documentation](./docs/selfhost.md)

---

## 📖 Usage Guide

### 1. The Genesis (First Run)

Upon first login, you'll witness the **Initialization Protocol**:

1. The Head of Council greets you (The Sovereign)
2. Council proposes names for your "Nation" (the system instance)
3. Democratic vote executes — watch the real-time tally in the dashboard
4. Constitution is ratified with your chosen name and stored in both PostgreSQL and ChromaDB
5. System becomes fully operational

### 2. Daily Operations

**Submitting a Task**:

```
You (Sovereign) → Head (0xxxx): "Analyze Q3 financial reports"
    ↓
Head validates intent + constitutional compliance
    ↓
Council votes on resource allocation (if required)
    ↓
Lead Agent (2xxxx) creates execution DAG
    ↓
Plan Critic (6xxxx) validates DAG
    ↓
Task Agents (3xxxx) execute — with Code + Output Critics reviewing
    ↓
Results aggregated → Head → You (2–3 line response only)
```

**Auto-Scaling in Action**:

- Load increases → Lead detects queue depth
- Lead requests Council approval for new Task Agents
- Council votes (automated if resolved <5 seconds)
- New `3xxxx` agents spawned with knowledge from Vector DB
- When queue empties, oldest Task Agents liquidated
- Leads can nest further Leads below them for large task trees

**Multi-Channel**: Send tasks from WhatsApp, Telegram, Slack, Discord, or any connected channel. The conversation is unified — you'll see full history in the web dashboard regardless of which channel you used.

---

## 🛠️ Technology Stack

| Component            | Technology                                             | Purpose                                               |
| -------------------- | ------------------------------------------------------ | ----------------------------------------------------- |
| **Frontend**         | React 18, TypeScript, Tailwind, Zustand                | Dashboard, voting UI, agent tree, checkpoint timeline |
| **API Gateway**      | FastAPI, WebSocket, Pydantic                           | REST + real-time communication                        |
| **Message Bus**      | Redis, Celery                                          | Inter-agent routing, background tasks                 |
| **Structured Data**  | PostgreSQL, SQLAlchemy, Alembic                        | Entity state, voting records, audit, conversations    |
| **Vector Knowledge** | ChromaDB, Sentence-Transformers (all-MiniLM-L6-v2)     | RAG, constitution, learnings                          |
| **AI Models**        | OpenAI, Anthropic, Groq, Ollama, any OpenAI-compatible | Agent intelligence, multi-provider failover           |
| **Code Execution**   | Docker sandbox (Remote Executor)                       | Isolated code execution, PII containment              |
| **Tool Governance**  | MCP SDK + Constitutional Guard                         | Tiered external tool access                           |
| **Containerization** | Docker, Compose, Healthchecks                          | Cross-platform deployment                             |
| **Security**         | JWT, Role-based capabilities                           | Per-agent authentication and authorization            |

---

## 🧪 Development Roadmap

### Phase 0: Foundation ✅ COMPLETE

- [x] PostgreSQL entity models
- [x] Hierarchical ID system (0/1/2/3/4/5/6xxxx)
- [x] Docker Compose setup with health checks
- [x] Alembic migrations, audit log, voting models

### Phase 1: Knowledge Infrastructure ✅ COMPLETE

- [x] ChromaDB integration with sentence-transformers
- [x] Knowledge Library service with moderation queue
- [x] RAG pipeline with constitutional context injection
- [x] Initialization Protocol (democratic country naming)
- [x] Duplicate detection and revision-aware knowledge storage

### Phase 2: Governance Core ✅ COMPLETE

- [x] Message Bus (Redis) with hierarchical validation + rate limiting
- [x] Agent Orchestrator with circuit breaker and metrics
- [x] Constitutional Guard — two-tier (PostgreSQL hard rules + ChromaDB semantic)
- [x] Voting Service with quorum logic, delegation, and timeout handling
- [x] Amendment Service (propose → debate → vote → ratify → broadcast)
- [x] Critic Agents with veto authority (Code/Output/Plan — `4/5/6xxxx`)

### Phase 3: Agent Lifecycle Management ✅ COMPLETE

- [x] Agent Factory (spawn/liquidate with collision-safe ID generation)
- [x] Auto-scaling algorithms
- [x] Capability Registry with runtime checks and dynamic granting
- [x] Idle governance — auto-terminate agents idle >7 days

### Phase 4: Multi-Channel Integration ✅ COMPLETE

- [x] Channel Manager with unified inbox and silent delivery logic
- [x] WhatsApp, Telegram, Discord, Slack, Signal
- [x] Google Chat, Microsoft Teams, iMessage (macOS), Zalo, Matrix
- [x] WebSocket real-time dashboard
- [x] Loop prevention — no re-echo to origin channel
- [x] Media normalization — all media stored in object storage, accessible from any channel

### Phase 5: AI Model Integration ✅ COMPLETE (core) / 🚧 Enhancements Pending

- [x] Multi-provider support: OpenAI, Anthropic, Groq, Ollama, any OpenAI-compatible endpoint
- [x] API key failover (primary → secondary → tertiary → local fallback)
- [x] Circuit breaker, exponential backoff, token usage tracking
- [x] Universal model provider (custom base URL, dynamic model discovery)
- [ ] Browser automation integration (Phase 10)
- [ ] Advanced RAG with source citations (Phase 10)
- [ ] Voice interface — Whisper + TTS (Phase 10)

### Phase 6: Advanced Execution Ecosystem ✅ COMPLETE

- [x] Tool Creation Service with Council approval workflow
- [x] Acceptance Criteria Service — machine-validatable task success conditions
- [x] Context Ray Tracing — role-based context visibility (Planners / Executors / Critics / Siblings)
- [x] Checkpointing & Time-Travel Recovery — resume or branch from any execution phase
- [x] Remote Code Executor — sandboxed Docker container, raw data never enters agent context
- [x] MCP Server Integration — constitutional tier-based tool approval and per-invocation audit logging

### Phase 7: Frontend Development ✅ COMPLETE

- [x] Login / Signup pages with JWT authentication and admin approval flow
- [x] Dashboard — system overview, agent stats, health metrics
- [x] Agent Tree — collapsible hierarchy visualization with real-time status
- [x] Tasks Page — filtering, critic dashboard tab, checkpoint timeline tab
- [x] Chat Page — WebSocket chat with Head of Council
- [x] Voting Page — active votes, countdown timers, amendment diff viewer, vote history
- [x] Constitution Page — Markdown editor, semantic search, amendment history timeline, PDF export
- [x] Channels Page — multi-channel management with status indicators
- [x] Models Page — AI provider configuration
- [x] Monitoring Page — system health and performance metrics
- [x] MCP Tool Registry — browse tools by tier, propose new MCP servers, per-tool audit log viewer
- [x] Critic Dashboard — approval bars, review counts, avg review time, per-subtask verdict expansion

### Phase 8: Testing & Reliability 🚧 NEXT

- [ ] Concurrent agent spawning stress tests (1,000+ simultaneous)
- [ ] Message Bus load test (10,000 messages/hour)
- [ ] Constitutional Guard performance: <50ms SQL, <200ms semantic
- [ ] Critic layer effectiveness target: 87.8% error catch rate
- [ ] Voting system: quorum accuracy, delegation chains, concurrent sessions
- [ ] Zero data loss during container restarts

### Phase 9: Production Readiness 📅 PENDING

- [ ] Kubernetes manifests (Helm charts)
- [ ] Prometheus + Grafana monitoring
- [ ] Daily PostgreSQL backups, point-in-time recovery
- [ ] MFA, token rotation, session management
- [ ] Rate limiting, HTTPS enforcement, DDoS protection

### Phase 10: Advanced Intelligence 🔮 FUTURE

- [ ] Browser automation (Playwright/Puppeteer) with URL whitelisting
- [ ] Advanced RAG with source attribution and confidence scoring
- [ ] Voice interface (Whisper STT + ElevenLabs/Coqui TTS)
- [ ] Autonomous learning — best practice extraction from task outcomes

### Phase 11–12: Federation & SDK 🔮 FUTURE

- [ ] Inter-Agentium federation protocol
- [ ] Python SDK (`pip install agentium-sdk`)
- [ ] TypeScript SDK (`npm install @agentium/sdk`)
- [ ] All SDK calls produce identical audit trails to direct API calls

---

## 🛡️ Security & Ethics

- **Local-First**: Your data never leaves your infrastructure by default
- **Immutable Audit**: All votes, actions, and terminations logged to PostgreSQL
- **Principle of Least Privilege**: Task agents cannot spawn other agents
- **Constitutional Bounded**: Agents cannot override the Constitution without democratic process
- **Emergency Brakes**: Head can halt the entire system; Council can veto Head with 75% supermajority
- **Execution Isolation**: Raw data and PII are confined to the sandboxed Remote Executor — never in agent reasoning context
- **Tool Governance**: MCP tools are constitutionally tiered; Tier 3 tools are categorically forbidden
- **Ethos Hygiene**: Individual agent Ethos must be removed after agent deletion or reassignment
- **Original Constitution**: Can never be deleted under any circumstances

---

## 🤝 Contributing

Agentium is built for the community. We welcome:

- 🏛️ **Governance Models**: New voting algorithms, constitutional frameworks
- 🧠 **Knowledge Systems**: RAG improvements, embedding models
- 🔌 **Integrations**: New messaging channels, AI providers, MCP servers
- 📖 **Documentation**: Tutorials, constitutional examples
- 🐛 **Bug Reports**: Help us maintain integrity

Read our [Contributing Guide](./CONTRIBUTING.md)

---

## 💬 Support

- 📧 Email: **dhungana.ashmin@gmail.com**

---

## 📄 License

Apache License 2.0 — See [LICENSE](LICENSE) file

**Built with ❤️ and purpose by Ashmin Dhungana**

> _"The price of freedom is eternal vigilance. The price of AI sovereignty is democratic architecture."_
