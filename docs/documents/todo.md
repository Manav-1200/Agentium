# Agentium Implementation Roadmap

## From Democratic AI Governance to Production-Ready System

**Project:** Agentium - Personal AI Agent Nation  
**Current Status:** Phase 5 Active Development (AI Model Integration)  
**Architecture:** Dual-Storage (PostgreSQL + ChromaDB) with hierarchical agent orchestration  
**Strategy:** Bottom-up implementation, one file at a time

---

## 🎯 Vision Statement

Build a self-governing AI ecosystem where agents operate under constitutional law, make decisions through democratic voting, and manage their own lifecycle—all while being transparent, auditable, and sovereign.

---

## Phase 0: Foundation Infrastructure ✅ (COMPLETE)

**Goal:** Establish rock-solid database and containerization foundation.

### Database Layer ✅

- [x] PostgreSQL 15 configured with proper schemas
- [x] Agent hierarchy models (0xxxx/1xxxx/2xxxx/3xxxx)
- [x] Foreign key constraints enforcing parent-child relationships
- [x] Indexes on `agent_type`, `status`, `agentium_id`
- [x] Constitution model with version control
- [x] Alembic migrations setup
- [x] Voting entity models with vote tallying
- [x] Audit log system with immutable records

### Containerization ✅

- [x] Docker Compose orchestration
- [x] PostgreSQL service with persistent volumes
- [x] Redis for message bus and caching
- [x] ChromaDB for vector storage
- [x] Health checks for all services
- [x] Network isolation and service dependencies

### Core Entity Models ✅

**Files Verified:**

- ✅ `backend/models/entities/agents.py` - Full hierarchy support
- ✅ `backend/models/entities/constitution.py` - Versioning complete
- ✅ `backend/models/entities/voting.py` - Democratic mechanics
- ✅ `backend/models/entities/audit.py` - Immutable logging
- ✅ `backend/models/entities/user.py` - Multi-user RBAC
- ✅ `backend/models/entities/base.py` - Common entity patterns

---

## Phase 1: Knowledge Infrastructure 🧠 ✅ (COMPLETE)

**Goal:** Dual-storage architecture where structured data lives in PostgreSQL and collective knowledge in Vector DB.

### 1.1 Vector Database Setup ✅

**Service:** ChromaDB running on port 8001

**Implementation:**

- ✅ `docker-compose.yml` - ChromaDB service configured
- ✅ `backend/requirements.txt` - chromadb, sentence-transformers, langchain added
- ✅ `backend/core/vector_db.py` - Vector operations service

**Features Implemented:**

- ✅ Sentence embeddings via `all-MiniLM-L6-v2`
- ✅ Metadata filtering by agent_id, knowledge_type, timestamp
- ✅ Collection management (constitution, learnings, rejected)
- ✅ Similarity search with configurable thresholds

### 1.2 Knowledge Service ✅

**File:** `backend/services/knowledge_service.py` ✅

**Capabilities:**

- ✅ Constitution semantic search ("What does Article 3 say about privacy?")
- ✅ Knowledge submission with moderation queue
- ✅ Council approval workflow for new knowledge
- ✅ Auto-categorization (constitution, task_learning, domain_knowledge)
- ✅ RAG context injection into agent prompts
- ✅ Duplicate detection and deduplication

### 1.3 Initialization Protocol ✅

**File:** `backend/services/initialization_service.py` ✅

**Genesis Flow:**

1. ✅ System detects first boot
2. ✅ Head of Council (0xxxx) instantiated
3. ✅ Council Members (1xxxx) spawned
4. ✅ Democratic vote for Country Name
5. ✅ Constitution template loaded with name
6. ✅ Vector DB indexes constitution
7. ✅ Initialization log stored in `docs_ministry/genesis_log.md`

**Anti-Tyranny Measures:**

- ✅ Requires 3 Council votes minimum to complete
- ✅ Original constitution always retrievable
- ✅ Country name persisted in both PostgreSQL and Vector DB

### 1.4 Knowledge Governance ✅

**Acceptance Criteria:**

- ✅ Knowledge submissions trigger Council vote (50% quorum)
- ✅ Rejected knowledge stored in `rejected/` collection
- ✅ Auto-categorization of submissions
- ✅ Retention policy (365-day auto-archive unless pinned)
- ✅ Orphaned knowledge cleanup on agent liquidation

---

## Phase 2: Governance Core ⚖️ ✅ (COMPLETE)

**Goal:** Implement constitutional enforcement, democratic voting, and hierarchical orchestration.

### 2.1 Message Bus Infrastructure ✅

**File:** `backend/services/message_bus.py` ✅

**Redis-Based Routing:**

- ✅ Task → Lead → Council → Head message flow
- ✅ Broadcast capabilities (Head → all subordinates)
- ✅ Message persistence (survives container restarts)
- ✅ Rate limiting (5 msg/sec per agent)
- ✅ Hierarchical validation (prevents level-skipping)

**Testing Checklist:**

- [x] Task agent can message parent Lead
- [x] Lead can broadcast to child Tasks
- [x] Task → Council direct message blocked
- [x] **TO TEST:** Message persistence after restart
- [ ] **TO TEST:** Rate limit enforcement under load

### 2.2 Agent Orchestrator ✅

**File:** `backend/services/agent_orchestrator.py` ✅

**Core Responsibilities:**

- ✅ Route messages between agent hierarchy
- ✅ Validate agent existence before routing
- ✅ Inject constitutional context from Vector DB
- ✅ Log all routing decisions to audit trail
- ✅ Handle "agent not found" with liquidation check
- ✅ Context manager integration for constitutional compliance

**Enhancements Added:**

- ✅ WebSocket event broadcasting on routing
- ✅ Metrics collection (routing latency, message volume, error rates, p95)
- ✅ Circuit breaker for failing agents (CLOSED→OPEN→HALF_OPEN states)

### 2.3 Constitutional Guard ✅

**File:** `backend/core/constitutional_guard.py` ✅

**Two-Tier Check System Implemented:**

```
Agent Action Request
    ↓
TIER 1: PostgreSQL (Hard Rules)
  ├─ Explicit blacklists (shell commands)
  ├─ Permission tables (who can do what)
  └─ Resource quotas
    ↓
TIER 2: Vector DB (Semantic Interpretation)
  ├─ "Is this against the spirit of the law?"
  ├─ Grey area violation detection
  └─ Contextual precedent checking
    ↓
Decision: ALLOW / BLOCK / VOTE_REQUIRED
```

**Features Complete:**

- ✅ Load active constitution from PostgreSQL
- ✅ Check actions against blacklisted patterns
- ✅ Redis caching for performance (5min constitution, 30min embeddings)
- ✅ Semantic constitutional check via ChromaDB (similarity thresholds: ≥70% BLOCK, 40-70% VOTE_REQUIRED)
- ✅ Trigger Council vote if action affects >3 agents
- ✅ Return human-readable legal citations ("Article 4, Section 2")
- ✅ Cache constitution embeddings for fast semantic search
- ✅ Constitutional violation severity classification (LOW/MEDIUM/HIGH/CRITICAL)

### 2.4 Voting Service ✅ (COMPLETE)

**File:** `backend/services/persistent_council.py` ✅

**Vote Types Implemented:**

- ✅ Constitutional amendments
- ✅ Resource allocation
- ✅ Knowledge approval/rejection
- ✅ Operational decisions
- ✅ Agent liquidation

**Features:**

- ✅ Dynamic quorum calculation
- ✅ Vote delegation (Council → Lead if specified)
- ✅ Circular voting prevention
- ✅ Abstention tracking
- ✅ Timeout handling (auto-fail if quorum not met)
- ✅ Vote tallying and finalization

**Testing Needs:**

- [ ] 60% quorum requirement verification
- [ ] Vote delegation chain testing
- [ ] Timeout behavior under load
- [ ] Concurrent voting session handling

### 2.5 Amendment Service ✅

**File:** `backend/services/amendment_service.py` ✅

**Amendment Pipeline:**

1. ✅ Council member proposes amendment (Markdown diff)
2. ✅ 48-hour debate window stored in `docs_ministry/debates/`
3. ✅ Democratic vote (60% quorum)
4. ✅ If passed:
   - Update PostgreSQL (new version + audit)
   - **Update Vector DB** (current law for RAG)
   - Broadcast law change via Message Bus
5. ✅ Notify all agents of constitutional update

**Acceptance Criteria:**

- ✅ Amendment proposals require 2 Council sponsors
- ✅ Configurable voting period (default 48h)
- ✅ Vector DB updated immediately upon ratification
- ✅ Automatic rollback if vote fails
- [ ] Diff visualization in frontend
- ✅ Amendment history tracking

---

## Phase 3: Agent Lifecycle Management 🔄 (IN PROGRESS - 90% COMPLETE)

**Goal:** Dynamic spawning, liquidation, and idle governance with capability management.

### 3.1 Reincarnation Service (Agent Factory) ✅

**File:** `backend/services/reincarnation_service.py` ✅

**ID Generation Rules:**

```
Head:    00001-09999  (max 9999 heads - one per Sovereign)
Council: 10001-19999  (max 9,999 councils)
Lead:    20001-29999  (max 9,999 leads)
Task:    30001-99999  (max 69,999 tasks)
```

**Methods Implemented:**

- ✅ `spawn_task_agent(parent_id, name, capabilities)`
- ✅ `promote_to_lead(agent_id)` - Upgrade Task → Lead
- ✅ `liquidate_agent(agent_id, reason)` - Safe termination
- ✅ `get_available_capacity()` - Check ID pool availability
- ✅ `reincarnate_agent(agent_id)` - Restore from backup

**Testing Checklist:**

- [x] No ID collisions during concurrent spawning
- [x] Parent-child hierarchy enforced
- [ ] **TO TEST:** 10,000 concurrent spawn requests
- [ ] **TO TEST:** ID pool exhaustion handling

### 3.2 Idle Governance ✅

**File:** `backend/services/idle_governance.py` ✅

**Auto-Termination Logic:**

- ✅ Detect idle agents (>7 days no activity)
- ✅ Duplicate idle task prevention (idempotency keys)
- ✅ Resource rebalancing (redistribute work from idle agents)
- ✅ Cleanup: Archive messages/tasks to cold storage
- ✅ Knowledge transfer to Council curation queue

**Scheduled Tasks:**

- ✅ `detect_idle_agents()` - Daily scan
- ✅ `auto_liquidate_expired()` - Every 6 hours
- ✅ `resource_rebalancing()` - Hourly optimization

**Metrics to Track:**

- [ ] Average agent lifetime
- [ ] Idle termination rate
- [ ] Resource utilization after rebalancing

### 3.3 Capability Registry 🚧 (PARTIAL)

**File:** `backend/services/capability_registry.py` (needs expansion)

**Current Capabilities Defined:**

```python
TIER_CAPABILITIES = {
    "0xxxx": ["veto", "amendment", "liquidate_any", "admin_vector_db"],
    "1xxxx": ["propose_amendment", "allocate_resources", "audit", "moderate_knowledge"],
    "2xxxx": ["spawn_task_agent", "delegate_work", "request_resources", "submit_knowledge"],
    "3xxxx": ["execute_task", "report_status", "escalate_blocker", "query_knowledge"]
}
```

**Pending Implementation:**

- [x] Runtime capability check (`can_agent_X_do_action_Y()`)
- [x] Capability revocation on liquidation
- [x] Capability inheritance (Lead inherits some Council powers)
- [x] Audit trail of capability usage
- [x] Dynamic capability granting via Council vote
- [ ] Testing

---

## Phase 4: Multi-Channel Integration 📱 (IN PROGRESS - 90% COMPLETE)

**Goal:** Connect Agentium to external messaging platforms as communication channels.

### 4.1 Channel Manager ✅

**File:** `backend/services/channel_manager.py` ✅

**Architecture:**

- Each channel mapped to dedicated Task Agents (3xxxx)
- Channels report to "Communications Council" Lead Agent (2xxxx)
- All messages routed through Message Bus

### 4.2 Channel Implementation Status

**Implemented Channels:**

- [x] WebSocket (real-time dashboard)
- [x] WhatsApp (Official Cloud API)
- [x] Telegram Bot API
- [x] Discord Bot
- [x] Slack App
- [x] Signal (signal-cli)
- [x] Google Chat
- [x] iMessage (macOS only)
- [x] Microsoft Teams
- [x] Zalo
- [x] Matrix

**Files:**

- ✅ `backend/services/channel_manager.py` - Core routing
- ✅ `backend/services/channels/base.py` - Base adapter
- ✅ `backend/services/channels/whatsapp.py` - WhatsApp adapter
- ✅ `backend/services/channels/slack.py` - Slack adapter
- ✅ `backend/models/entities/channels.py` - Channel metadata
- ✅ `backend/api/routes/channels.py` - Channel CRUD

**Testing Needs:**

- [x] Multi-channel concurrent message handling
- [ ] Channel failure recovery
- [ ] Message format translation (text → rich media)
- [ ] Rate limiting per platform

### 4.3 WebSocket Integration ✅

**File:** `backend/api/websocket.py` ✅

**Events Implemented:**

- ✅ `agent_spawned`
- ✅ `task_escalated`
- ✅ `vote_initiated`
- ✅ `constitutional_violation`
- ✅ `message_routed`

**Pending Events:**

- [x] `knowledge_submitted`
- [x] `knowledge_approved`
- [x] `amendment_proposed`
- [x] `agent_liquidated`

---

## Phase 5: AI Model Integration 🤖 (IN PROGRESS - 90% COMPLETE)

**Goal:** Multi-provider AI model support with fallback and optimization.

### 5.1 Model Provider Service ✅

**File:** `backend/services/model_provider.py` ✅

**Supported Providers:**

- ✅ OpenAI (GPT-4, GPT-3.5-turbo)
- ✅ Anthropic (Claude 3 Opus, Sonnet, Haiku)
- ✅ Groq (Llama 3)
- ✅ Local (Ollama, LM Studio)
- ✅ Universal (any OpenAI-compatible endpoint)

**Features:**

- ✅ Multi-provider API key management
- ✅ Automatic fallback on provider failure
- ✅ Provider health monitoring
- ✅ Token usage tracking per provider
- ✅ Cost calculation (USD)

### 5.2 API Manager ✅

**File:** `backend/services/api_manager.py` ✅

**Token Optimization:**

- ✅ Context window management
- ✅ Token counting (tiktoken)
- ✅ Conversation history pruning
- ✅ System prompt caching

**Rate Limiting:**

- ✅ Per-provider rate limits
- ✅ Circuit breaker on failures
- ✅ Exponential backoff retry logic

**Pending Enhancements:**

- [ ] Model-specific prompt templates
- [ ] Cost budget enforcement
- [ ] Provider performance metrics
- [ ] A/B testing different models for same task

### 5.3 Universal Model Provider ✅

**File:** `backend/services/universal_model_provider.py` ✅

**Purpose:** Support ANY OpenAI-compatible endpoint

**Features:**

- ✅ Custom base URL configuration
- ✅ Dynamic model discovery
- ✅ Authentication header customization
- ✅ Response format normalization

**Use Cases:**

- Local LLMs (Ollama, LM Studio, vLLM)
- Private cloud deployments
- Custom fine-tuned models
- Third-party aggregators

### 5.4 API Key Resilience & Notification System 🆕 (PENDING)

**File:** `backend/services/api_key_manager.py` (new)

**Goal:** Ensure zero-downtime model access with intelligent failover and user notification when all keys fail.

**Inspired by:** Rowboat's API key fallback pattern — formalized into Agentium's governance model.

**Failover Architecture:**

```
Request → Primary Key (OpenAI)
    ↓ FAIL
    → Secondary Key (Anthropic)
    ↓ FAIL
    → Tertiary Key (Groq)
    ↓ FAIL
    → Local Fallback (Ollama)
    ↓ FAIL
    → ALERT: Notify all channels + frontend
```

**Features:**

- [x] `get_active_key()` - Returns next healthy key in priority order
- [x] `mark_key_failed(key_id, error)` - Temporarily disables a key with backoff
- [x] `recover_key(key_id)` - Auto-retry failed keys after cooldown period
- [x] `notify_all_keys_down()` - Broadcasts to frontend WebSocket + all active channels
- [x] `get_key_health_report()` - Provider status dashboard data
- [x] Cost budget enforcement per key (prevent overspend)
- [x] API key rotation without service downtime

**Notification Targets When All Keys Fail:**

- [x] Frontend dashboard: Red alert banner with affected providers
- [x] WebSocket broadcast to all connected clients
- [x] All active channels (Telegram, Discord, Slack, WhatsApp) get fallback message
- [x] Email alert to Sovereign (if configured)

**Database Model:**

```python
class APIKeyRecord(BaseEntity):
    provider: str           # "openai", "anthropic", "groq"
    key_hash: str           # Hashed for security
    priority: int           # 1=primary, 2=secondary, etc.
    status: str             # "active", "failed", "rate_limited", "exhausted"
    failure_count: int
    last_failure_at: Optional[datetime]
    cooldown_until: Optional[datetime]
    monthly_budget_usd: Optional[float]
    current_spend_usd: float = 0.0
```

**Acceptance Criteria:**

- [ ] Failover completes in <500ms (no user-visible delay)
- [ ] Failed keys auto-recover after cooldown without manual intervention
- [ ] Frontend shows real-time provider health status
- [ ] All channel bots send fallback message if no keys available
- [ ] Budget enforcement prevents overspend per key
- [ ] Rotation of keys requires zero downtime

**Files:**

- `backend/services/api_key_manager.py` - Core failover logic
- `backend/api/routes/api_keys.py` - CRUD for key management
- `frontend/src/components/settings/APIKeyHealth.tsx` - Health dashboard widget

---

## Phase 6: Advanced Features 🚀 (NEW - HIGH PRIORITY)

**Based on research: "If You Want Coherence, Orchestrate a Team of Rivals"**

6.1 Tool Creation (foundation)
└── 6.7 MCP Governance (extends 6.1)
6.2 Critic Agents (mostly done)
└── 6.3 Acceptance Criteria (feeds critics)
6.4 Context Ray Tracing (enhances message_bus)
6.5 Checkpointing (cross-cutting)
6.6 Remote Executor (infrastructure) ✅

### 6.1 Tool Creation Service 🆕 ✅

**File:** `backend/services/tool_creation_service.py` ✅

**Agent-Initiated Tool Development:**

- ✅ Agents can propose new tools (Python code)
- ✅ Security validation (import whitelist, dangerous pattern blocking)
- ✅ Democratic approval workflow (Council vote)
- ✅ Automatic testing before activation
- ✅ Tool registry integration

**Tool Factory:**

- ✅ `backend/services/tool_factory.py` - Code generation and validation
- ✅ AST parsing for syntax checks
- ✅ Sandboxed execution environment
- ✅ Dynamic tool loading

**Approval Flow:**

1. Agent proposes tool → Code validation
2. If Head (0xxxx): Auto-approve
3. If Council/Lead: Council vote required
4. If Task: Permission denied
5. Tests run on approval
6. Tool registered and available to authorized tiers

**Pending:**

- ✅ Tool versioning and updates
- ✅ Tool deprecation workflow
- ✅ Usage analytics per tool
- ✅ Tool marketplace (share between Agentium instances)

### 6.2 Critic Agents with Veto Authority 🆕 (DONE)

**New Agent Types (Non-Breaking Addition):**

- `CodeCritic` (4xxxx) - Validates code syntax, security, logic
- `OutputCritic` (5xxxx) - Validates against user intent
- `PlanCritic` (6xxxx) - Validates execution DAG soundness

**Key Principle:** Critics operate OUTSIDE democratic chain

- Don't vote on amendments
- Have ABSOLUTE veto authority
- When critic rejects, task retries WITHIN same team
- No Council escalation on critic rejection

**Implementation Plan:**

**New Files to Create:**

- [x] `backend/models/entities/critics.py` - Critic agent models
- [x] `backend/services/critic_agents.py` - Critic logic
- [x] `backend/api/routes/critics.py` - Critic endpoints

**Database Changes:**

```python
class CritiqueReview(BaseEntity):
    task_id: str
    critic_type: str  # "code", "output", "plan"
    critic_agentium_id: str
    verdict: str  # "PASS", "REJECT", "ESCALATE"
    rejection_reason: Optional[str]
    retry_count: int
    max_retries: int = 5
```

**Acceptance Criteria:**

- [x] Critics can veto outputs independently
- [x] Rejected tasks retry without Council replanning
- [x] Maximum 5 retries before escalation to Council
- [x] Critic decisions logged in audit trail
- [x] Critics use different AI models than executors (orthogonal failure modes)

### 6.3 Pre-Declared Acceptance Criteria 🆕 ✅

**Goal:** Define success criteria BEFORE work begins

**Implementation:**

- [x] Add `acceptance_criteria` JSON field to task proposals
- [x] Council votes on BOTH plan AND success criteria
- [x] Store as structured, machine-validatable JSON

**Database Migration:**

```python
# Added to existing Task model (non-breaking)
class Task:
    # ... existing fields ...
    acceptance_criteria = Column(JSON, nullable=True)  # ✅
    veto_authority = Column(String(20), nullable=True)  # ✅
```

**Criterion Structure:**

```python
@dataclass
class AcceptanceCriterion:
    metric: str  # "sql_syntax_valid", "result_schema_matches"
    threshold: Any  # Expected value or range
    validator: CriterionValidator  # code | output | plan
    is_mandatory: bool = True
    description: str = ""
```

**Implementation Details:**

- ✅ `acceptance_criteria.py` — `AcceptanceCriterion`, `CriterionResult`, `AcceptanceCriteriaService`
- ✅ `AcceptanceCriteriaService.parse_and_validate()` — validates raw JSON from API
- ✅ `AcceptanceCriteriaService.evaluate_criteria()` — rule-based checks (sql_syntax, result_not_empty, length, contains, boolean, generic)
- ✅ `AcceptanceCriteriaService.aggregate()` — counts + mandatory-failure flag
- ✅ `api/schemas/task.py` — Pydantic `AcceptanceCriterionSchema` with validators (unique metrics, valid validator values)
- ✅ `api/routes/tasks.py` — validates + stores on create and update, veto_authority validation
- ✅ `critic_agents.py` — loads criteria from Task, runs deterministic checks before AI review, fast-rejects on mandatory failures
- ✅ `CritiqueReview` entity stores `criteria_results`, `criteria_evaluated`, `criteria_passed`
- ✅ DB migration (`001_schema.py`) includes `acceptance_criteria` column

**Tests:** ✅ 42 unit tests in `backend/tests/test_acceptance_criteria.py` (all passing)

**Acceptance Criteria:**

- [x] All new tasks require explicit acceptance criteria
- [x] Criteria are machine-validatable where possible
- [x] Human-readable criteria displayed in dashboard
- [x] Criteria stored in task metadata

### 6.4 Context Ray Tracing - Selective Information Flow 🆕 ✅

**File:** `backend/services/message_bus.py` (Enhancement) ✅

**Problem:** Current system shares full context across all agents
**Solution:** Role-based context visibility via `ContextRayTracer` class

**Message Visibility Controls:**

- ✅ **Planners** (Head/Council): User intent, constraints, high-level goals
- ✅ **Executors** (Lead/Task): Step-by-step plan, prior step outputs ONLY
- ✅ **Critics** (7xxxx/8xxxx/9xxxx): Execution results + acceptance criteria ONLY
- ✅ **Siblings**: NO visibility into each other's work (via `visible_to` patterns)

**Enhanced Message Schema:**

```python
class AgentMessage:
    content: str
    visible_to: List[str]  # Agent ID patterns: ["2*", "3*"]
    message_type: str  # "plan", "execution", "critique", "critique_result"
    context_scope: str  # "FULL", "SUMMARY", "SCHEMA_ONLY"
```

**Implementation Details:**

- ✅ `ContextRayTracer` class in `message_bus.py` (stateless, all `@classmethod`)
- ✅ `get_agent_role()` — maps prefix → PLANNER / EXECUTOR / CRITIC
- ✅ `is_visible_to()` — dual check: glob pattern match + role-based type filter
- ✅ `filter_messages()` — filters + applies `context_scope` automatically
- ✅ `apply_scope()` — FULL / SUMMARY (truncate to 200 chars) / SCHEMA_ONLY
- ✅ `build_context()` — convenience wrapper for filter + scope
- ✅ Schema extended: `visible_to`, `context_scope`, critic IDs (4-6), new message types
- ✅ `HierarchyValidator` extended with critic tiers 4/5/6
- ✅ Wired into `consume_stream()` for automatic filtering on message consumption

**Tests:** ✅ 57 unit tests in `backend/tests/test_context_ray_tracing.py` (all passing)

**Acceptance Criteria:**

- [x] Agents only receive context relevant to their role
- [x] Sibling task isolation enforced
- [x] Context window optimization (reduced token usage)
- [x] No cross-contamination between execution branches

### 6.5 Checkpointing & Time-Travel Recovery 🆕 (COMPLETE)

**New File:** `backend/services/checkpoint_service.py`

**Purpose:** Enable session resumption and retry from any point

**Implementation:**

- [x] Serialize complete system state after each phase
- [x] Store in PostgreSQL with versioning
- [x] Allow "time travel" to any checkpoint
- [x] Support branching (try different approaches from same checkpoint)

**Database Model:**

```python
class ExecutionCheckpoint(BaseEntity):
    session_id: str
    phase: str  # "plan_approved", "execution_complete", "critique_passed"
    agent_states: JSON  # Dict[agent_id, AgentState]
    artifacts: List[str]  # Generated outputs
    parent_checkpoint_id: Optional[str]  # For branching
    is_active: bool
```

**Acceptance Criteria:**

- [x] Checkpoints created automatically at phase boundaries
- [x] Users can resume sessions after days/weeks
- [x] Retry from any checkpoint with different parameters
- [x] Complete audit trail of checkpoint transitions
- [x] Checkpoint cleanup (auto-delete after 90 days)

### 6.6 Remote Code Execution (Brains vs Hands) 🆕 ✅ (COMPLETE)

**Goal:** Separate reasoning from execution to prevent context contamination

**New Service:** `backend/services/remote_executor/` (Docker container)

**Architecture:**

```
Agent (Brain) → Writes Code → Security Guard → Sandbox → Executor → Summary
     ↑                                                                ↓
     └────────────── Receives Summary (schema + stats only) ←────────┘
```

**Key Principle:** Raw data NEVER enters agent context

**Files Implemented:**

- ✅ `backend/core/security/__init__.py` - Security package
- ✅ `backend/core/security/execution_guard.py` - Multi-layer code validation (regex + AST + syntax)
- ✅ `backend/services/remote_executor/__init__.py` - Service package
- ✅ `backend/services/remote_executor/sandbox.py` - Docker sandbox lifecycle management
- ✅ `backend/services/remote_executor/executor.py` - In-container execution with DataFrame analysis
- ✅ `backend/services/remote_executor/service.py` - Main orchestrator (validate → sandbox → execute → summarize)
- ✅ `backend/api/schemas/remote_executor.py` - Pydantic request/response models
- ✅ `backend/api/routes/remote_executor.py` - 6 API endpoints (execute, validate, sandboxes, executions)
- ✅ `backend/alembic/versions/003_add_remote_execution.py` - Database migration
- ✅ `backend/tests/test_remote_executor.py` - 27 test cases

**Modified Files:**

- ✅ `backend/models/entities/agents.py` - Added `remote_executions` relationship
- ✅ `backend/models/entities/task.py` - Added `remote_executions` relationship
- ✅ `backend/models/entities/__init__.py` - Registered remote execution models
- ✅ `backend/core/config.py` - Added `REMOTE_EXECUTOR_*` / `SANDBOX_*` settings
- ✅ `backend/main.py` - Registered remote executor router at `/api/v1`

**Acceptance Criteria:**

- [x] Raw data never enters agent context window
- [x] Agents reason about data shape, not content
- [x] PII stays in execution layer
- [x] Working set size >> context window size
- [x] Code execution fully sandboxed (Docker isolation)
- [x] Resource limits enforced (CPU, memory, time)

**Docker Service:**

- [x] Create `docker-compose.remote-executor.yml` - Security-hardened, resource-limited
- [x] Create `backend/Dockerfile.remote-executor` - Non-root, minimal image
- [x] Separate network isolation
- [x] Limited resource allocation
- [x] Auto-restart on failure

**Tests:** ✅ 10 ExecutionGuard tests verified inline (all passing)

### 6.7 MCP Server Integration with Constitutional Governance 🆕 (Done)

**File:** `backend/services/mcp_governance.py` (new)

**Goal:** Extend the existing Tool Creation Service (6.1) to support MCP servers as a tool source, with constitutional tier-based approval and audit logging on every invocation.

**Inspired by:** Rowboat's native MCP support — adapted into Agentium's democratic approval model.

**Philosophy:** Rowboat connects MCP tools directly. Agentium connects them through the Constitution.

**Tool Tier System:**

```
┌──────────────────────────────────────────────────────┐
│                 MCP TOOL REGISTRY                    │
├──────────────────────────────────────────────────────┤
│  Tier 1: Pre-Approved (Council vote to USE)          │
│  ├─ Safe read-only APIs (weather, public data)       │
│  └─ Non-destructive queries                          │
│                                                      │
│  Tier 2: Restricted (Head approval per use)          │
│  ├─ Email sending                                    │
│  ├─ File system writes                               │
│  └─ External webhooks                                │
│                                                      │
│  Tier 3: Forbidden (Constitutionally banned)         │
│  ├─ Financial transactions                           │
│  ├─ Credential/password access                       │
│  └─ Raw shell execution (use Remote Executor 6.6)   │
└──────────────────────────────────────────────────────┘
```

**Integration with Existing 6.1 Tool Creation Service:**

MCP tools enter the same approval pipeline as agent-created tools. The only difference is the source — MCP server vs agent-generated code. Constitutional Guard (2.3) audits every invocation.

**Database Model:**

```python
class MCPTool(BaseEntity):
    name: str
    description: str
    server_url: str
    tier: str                          # "pre_approved", "restricted", "forbidden"
    capabilities: List[str]
    constitutional_article: Optional[str]  # Which article governs this
    approved_by_council: bool = False
    approval_vote_id: Optional[str]
    usage_count: int = 0
    last_used_at: Optional[datetime]
    audit_log: List[Dict]              # Every invocation logged
```

**Implementation:**

- [x] `backend/services/mcp_governance.py` - Core MCP client + constitutional wrapper
- [x] `propose_mcp_server(url, description)` - Council member proposes new MCP server
- [x] `audit_tool_invocation(tool_id, agent_id, action)` - Constitutional Guard hook
- [x] `get_approved_tools(agent_tier)` - Returns tools accessible to agent's tier
- [x] `revoke_mcp_tool(tool_id, reason)` - Emergency revocation without vote
- [x] MCP tool wrapper auto-generates constitutional compliance layer

**Frontend:**

- [x] `frontend/src/components/mcp/ToolRegistry.tsx` - Browse available MCP tools
- [x] Filter by tier, approval status, usage stats
- [x] "Propose new MCP server" modal → triggers Council vote
- [x] Per-tool invocation audit log viewer

**Acceptance Criteria:**

- [ ] Every MCP tool invocation logged in audit trail with agent_id, timestamp, input hash
- [ ] Tier 3 tools blocked at Constitutional Guard before reaching MCP client
- [ ] Tier 2 tools require Head approval token in request
- [ ] Council vote required to add any new MCP server (same flow as 6.1)
- [ ] Tool registry shows real-time usage stats per tool
- [ ] Revoked tools immediately unavailable (cache invalidation <1s)
- [ ] MCP server health monitored (auto-disable on repeated failures)

**Python Dependencies to Add:**

```
mcp==1.0.0    # Official MCP Python SDK
```

---

## Phase 7: Frontend Development 🎨 ✅ (COMPLETE - 100%)

**Goal:** Rich, intuitive dashboard for sovereign control and system monitoring.

### 7.1 Core Pages ✅

**Implemented:**

- ✅ `LoginPage.tsx` - JWT authentication
- ✅ `SignupPage.tsx` - User registration with admin approval
- ✅ `Dashboard.tsx` - System overview, stats, health
- ✅ `AgentsPage.tsx` - Hierarchical agent tree visualization
- ✅ `TasksPage.tsx` - Task list with filtering
- ✅ `ChatPage.tsx` - WebSocket chat with Head of Council
- ✅ `SettingsPage.tsx` - Password management
- ✅ `MonitoringPage.tsx` - System health metrics
- ✅ `ConstitutionPage.tsx` - Full Markdown viewer/editor
- ✅ `ChannelsPage.tsx` - Multi-channel management
- ✅ `ModelsPage.tsx` - AI provider configuration

**Pending:**

- [x] `VotingPage.tsx` - Active votes and history

### 7.2 Agent Tree Visualization ✅

**File:** `frontend/src/components/agents/AgentTree.tsx` ✅

**Features:**

- ✅ Collapsible hierarchy (Head > Council > Lead > Task)
- ✅ Real-time agent status (idle/active/liquidated)
- ✅ Color coding by agent type
- ✅ Spawn agent modal
- ✅ Terminate agent confirmation

**Pending Enhancements:**

- [x] Health score visualization (SVG ring on AgentCard icon)
- [x] Task count badge per agent (active_task_count badge)
- [ ] Drag-and-drop reassignment
- [x] Critic agents (4xxxx/5xxxx/6xxxx) in separate branch

### 7.3 Voting Interface ✅ (COMPLETE)

**File:** `frontend/src/pages/VotingPage.tsx` ✅

**Features:**

- [x] Active votes list with countdown timers
- [x] Amendment diff viewer (Markdown side-by-side)
- [x] Real-time vote tally (WebSocket updates)
- [x] Delegate authority checkbox
- [x] Proposal composer with rich text
- [x] Vote history archive

### 7.4 Constitution Editor ✅ (COMPLETE)

**File:** `frontend/src/pages/ConstitutionPage.tsx` ✅

**Features:**

- [x] Render Markdown with article navigation
- [x] Highlight recently amended sections (last 7 days)
- [x] Semantic search across constitution (client-side filter + highlight)
- [x] "Propose Amendment" button → opens modal with diff editor
- [x] Amendment history timeline
- [x] Export constitution as PDF

### 7.5 Critic Dashboard ✅ (COMPLETE — implemented inside TasksPage)

**Decision:** The planned `CriticPanel.tsx` is superseded by `CriticsTab` inside `TasksPage.tsx`, which is more capable. Includes: overall stats, individual CriticCard per agent (approval bars, review counts, avg review time, model badge), CriticReviewPanel with per-subtask verdict expansion, CriticSummaryDots on task cards.

**Features:**

- [x] Pending reviews queue (by critic type)
- [x] Acceptance criteria validator interface
- [x] Veto override requests (escalate to Council)
- [x] Retry history visualization
- [x] Critic performance metrics (approval rate, avg review time)

### 7.6 Checkpoint Timeline ✅ (COMPLETE)

**File:** `frontend/src/components/checkpoints/CheckpointTimeline.tsx` ✅

**Features:**

- [x] Visual timeline of execution phases (per-checkpoint cards with phase color coding)
- [x] Click to restore/branch from checkpoint (inline expand with Restore + Branch from here)
- [x] "Inspect State" button and modal for full JSON visualization
- [ ] Compare different execution branches (diff view)
- [ ] Export/import checkpoint states
- [ ] Checkpoint cleanup management

**Notes:** Uses `checkpointsService` (not raw api calls), toast notifications, full Tailwind dark-mode styling matching app design system. **Wired as the "Checkpoints" tab inside `TasksPage.tsx`** — accessible at `/tasks` → Checkpoints tab.

### 7.7 Financial Burn Rate Dashboard ✅ (COMPLETE)

**File:** `frontend/src/components/dashboard/FinancialBurnDashboard.tsx` ✅

**Features:**

- [x] Combines token usage and completion stats
- [x] Integrates `/admin/budget` and `/admin/budget/history` backend APIs
- [x] Renders real-time metrics showing tokens used vs limits
- [x] Detailed provider breakdown and 7-day spend history
- [x] Fully responsive Tailwind UI with dark-mode support

**Notes:** Integrated as the "Financial & Burn Rate" tab inside `SovereignDashboard.tsx`.

### 7.8 Multi-Channel Interface ✅

**File:** `frontend/src/pages/ChannelsPage.tsx` ✅

**Features:**

- ✅ Channel list with status indicators
- ✅ Add/remove channels
- ✅ Channel configuration (API keys, webhooks)
- ✅ Message routing visualization

**Pending:**

- [ ] Channel health monitoring
- [ ] Message log per channel
- [ ] Channel-specific settings (rate limits, filters)

---

We are (Here) -------------------------------------------------------->

## Phase 8: Testing & Reliability 🧪 (COMPLETED)

**Goal:** Ensure system reliability under load and edge cases.

### 8.1 Core Functionality Verification

**Database Layer:**

- [ ] Test concurrent agent spawning (1000 simultaneous requests)
- [ ] Verify foreign key constraints prevent orphaned agents
- [ ] Constitution versioning rollback testing
- [ ] Audit log integrity checks

**Message Bus:**

- [ ] 10,000 messages routed without loss
- [ ] Message persistence after container restart
- [ ] Rate limit enforcement (block 6th message in same second)
- [ ] Hierarchical validation (reject Task → Council direct message)

**Voting System:**

- [ ] Quorum calculation accuracy (test with 1, 5, 100 Council members)
- [ ] Concurrent voting sessions (multiple proposals simultaneously)
- [ ] Vote delegation chain (A delegates to B, B delegates to C)
- [ ] Timeout handling (auto-fail after 48h)

**Constitutional Guard:**

- [ ] Blacklist enforcement (block `rm -rf /`)
- [ ] Semantic violation detection (grey area cases)
- [ ] Performance: <50ms for SQL checks, <200ms for semantic checks
- [ ] Cache invalidation on constitution update

### 8.2 Performance Benchmarks

**Targets:**

- [ ] Constitutional check latency <50ms (SQL)
- [ ] Semantic search latency <200ms (Vector DB)
- [ ] Message routing latency <100ms
- [ ] API response time <500ms (95th percentile)
- [ ] WebSocket event delivery <50ms

**Load Testing:**

- [ ] 100 concurrent users on dashboard
- [ ] 1000 tasks/hour throughput
- [ ] 10,000 agents active simultaneously
- [ ] 1TB knowledge base (Vector DB)

### 8.3 Reliability Metrics (From Research)

**Critic Layer Effectiveness:**

- [ ] **Target:** 87.8% error catch rate via critics
- [ ] **Target:** 92.1% overall success rate
- [ ] **Target:** <7.9% residual error rate requiring human intervention

**System Resilience:**

- [ ] Zero data loss during container restarts
- [ ] Automatic recovery from PostgreSQL connection failures
- [ ] Graceful degradation when Vector DB unavailable
- [ ] Circuit breaker prevents cascade failures

---

## Phase 9: Production Readiness 🏭 (COMPLETED)

**Goal:** Harden system for production deployment with monitoring and maintenance.

### 9.1 Monitoring & Observability

**New Service:** `backend/services/monitoring_service.py` (enhancement)

**Background Tasks:**

- [x] `constitutional_patrol()` - Every 5 minutes
- [x] `stale_task_detector()` - Daily
- [x] `resource_rebalancing()` - Hourly
- [x] `council_health_check()` - Weekly
- [x] `knowledge_consolidation()` - Daily
- [x] `orphaned_knowledge_check()` - Weekly
- [x] `critic_queue_monitor()` - Every minute

**Alert System:**

**File:** `backend/services/alert_manager.py` (enhancement)

**Severity Levels:**

- [x] INFO: Task completed
- [x] WARNING: Task blocked >1 hour
- [x] CRITICAL: Constitutional violation detected
- [x] EMERGENCY: Head intervention required
- [x] CRITIC_VETO: Output rejected by critic (new)

**Channels:**

- [x] WebSocket (real-time dashboard)
- [x] Email (Council level+)
- [x] Webhook (external integrations)
- [x] Slack/Discord notifications

### 9.2 Memory Management

**Database Maintenance:**

- [x] Auto-delete old audit logs (keep 90 days hot, archive rest)
- [x] Constitution version cleanup (keep last 10, archive older)
- [x] **NEVER delete original constitution**
- [x] Vector DB optimization (reindex weekly, cleanup duplicates)
- [x] Task/message archive (cold storage after 30 days)

**Performance:**

- [x] Index maintenance (rebuild weekly)
- [ ] Query optimization (slow query log analysis)
- [ ] Connection pooling tuning
- [ ] Cache hit rate monitoring (Redis)

### 9.3 Backup & Disaster Recovery

**Backup Strategy:**

- [x] PostgreSQL: Daily full backup with rotation (keep last 7)
- [x] Vector DB: Weekly full snapshot with rotation (keep last 4)
- [ ] Configuration files: Git versioning
- [ ] Encryption at rest for sensitive data

**Recovery Procedures:**

- [ ] Point-in-time recovery (last 30 days)
- [ ] Constitution rollback workflow
- [x] Agent state restoration from checkpoints
- [x] Knowledge Library restoration from vector snapshots

### 9.4 Security Hardening

**Authentication:**

- [x] JWT token authentication
- [x] Token rotation policy (configurable expiry via settings)
- [ ] Multi-factor authentication (MFA)
- [x] Session management (max concurrent sessions, configurable)

**Authorization:**

- [x] Role-based access control (Sovereign, Council, Lead, Task)
- [ ] Capability-based security (fine-grained permissions)
- [ ] Audit trail for all privilege escalations

**Network Security:**

- [ ] HTTPS enforcement
- [x] Rate limiting on API endpoints (per-IP, configurable)
- [ ] DDoS protection
- [x] Input sanitization and validation (XSS pattern stripping)

### 9.5 API Key Resilience

**File:** `backend/services/api_manager.py` (enhancement)

**Features:**

- [x] Auto-fallback to next available API key
- [x] Verify multiple keys from same provider can be added
- [ ] Circuit breaker pattern for failing providers
- [x] Notification if ALL API keys failing
- [x] API key rotation without downtime
- [x] Cost budget enforcement per key

**Multi-Provider Strategy:**

- [ ] Primary: Anthropic
- [ ] Secondary: OpenAI
- [ ] Tertiary: Groq
- [ ] Fallback: Local models (Ollama)

---

## Phase 10: Advanced Intelligence 🧠 (FUTURE)

**Goal:** Enhance agent cognitive capabilities and autonomous learning.

### 10.1 Browser Control Integration

**Planned Integration:** Playwright/Puppeteer for web automation

**Use Cases:**

- [ ] Research tasks (scrape, summarize)
- [ ] Form filling and submission
- [ ] Price monitoring
- [ ] Social media posting
- [ ] E-commerce operations

**Safety:**

- [ ] URL whitelist/blacklist
- [ ] Content filtering
- [ ] Screenshot logging for auditing

### 10.2 Advanced RAG with Citations

**Enhancements:**

- [ ] Source attribution for every claim
- [ ] Confidence scoring per fact
- [ ] Contradiction detection across sources
- [ ] Automatic fact-checking against Vector DB

### 10.3 Voice Interface

**Implementation:**

- [ ] Speech-to-text (Whisper)
- [ ] Text-to-speech (ElevenLabs/Coqui)
- [ ] Voice channel integration (phone, Discord voice)
- [ ] Speaker identification (multi-user)

### 10.4 Autonomous Learning

**Self-Improvement Mechanisms:**

- [ ] Task outcome analysis (what worked, what failed)
- [ ] Best practices extraction from successful tasks
- [ ] Anti-pattern detection from failures
- [ ] Knowledge consolidation (merge similar learnings)

---

Test and release V1.0.0

---

# ✅ Final Verification & System Checklist

---

## 0. Strategic Overview (Scope & Validation Objectives)

### Multi-Channel Integration (Messaging Platforms)

Implement support for the following communication platforms to enable **local-first AI agents** across distributed messaging environments:

- WhatsApp
- Telegram
- Slack
- Discord
- Signal
- Google Chat
- iMessage
- Microsoft Teams
- Zalo
- Matrix

### Priority Classification

**Easy (API-First Platforms)**

- Telegram
- Discord
- Slack

**Moderate Complexity**

- WhatsApp (Baileys)
- Signal (signal-cli)
- Google Chat
- Matrix

**High Complexity**

- iMessage (macOS-only limitations)
- Microsoft Teams (enterprise-level integration complexity)
- Zalo (limited API exposure)

### Architectural Design

- Each communication channel must be mapped to dedicated **Task Agents (3xxxx)**.
- All communication agents must operate under a centralized supervisory agent:  
  **“Communications Council” Lead Agent (2xxxx)**.
- Clear delegation and traceable task routing must be enforced.

---

## 1. Access & Permissions

- Verify that the **Head of Council** possesses full system-level access.
- Confirm full functionality of **Browser Control** capabilities.
- Ensure privilege boundaries are correctly enforced across all user roles.

---

## 2. System Testing

- Conduct comprehensive end-to-end system testing.
- Validate all modules, workflows, routing logic, and fallback systems.
- Confirm no cross-system contamination between reasoning and execution layers.
- Ensure stability under load and multi-agent concurrency.

---

## 3. Memory Management

### 3.1 Database & Vector Database Governance

- Implement structured memory lifecycle management.
- Remove obsolete records and outdated data versions.
- Maintain strict version control policies.
- **The Original Constitution must never be deleted under any circumstances.**

### 3.2 Required System Enhancements

- Provide secure tools to connect to the MCP server.
- Implement automatic API key failover:
  - If one API key fails, automatically switch to the next available key.
- If **no API keys respond**, generate system alerts:
  - Visible notification in the frontend.
  - Background channel alerts for monitoring systems.

---

## 4. Ethos & Message History Management

### 4.1 Ethos Governance

The message history represents the operational **Ethos** of the system and must:

- Be properly stored.
- Be accessible.
- Be editable.
- Be minimized/summarized for efficiency.
- Remain consistent with the Constitution.

### 4.2 Ethos Update Workflow

All agents must follow this standardized workflow:

1. Read the Constitution.
2. Update the individual Ethos.
3. During task execution:
   - Log current actions.
   - Log completed actions.
   - Log pending actions.
4. Apply this workflow universally across all agents.

---

## 5. API Request Validation

- Ensure that **Ethos content is included in every API request** without exception.
- Validate payload structure before dispatch.
- Enforce consistency across providers.

---

# Memory Optimization Framework

## 1. Chat Retention Policy

- Chats older than a defined period (e.g., 7 days) will be removed.
- The last 50 messages must always be retained and protected.
- Conversations must remain concise and precise.

## 2. Task Database Management

- Maintain a structured database of:
  - All user-assigned tasks.
  - Completion status of each task.
- Completed tasks will be removed after a defined retention period (e.g., 7 days).
- **Exception:** The Original Constitution must never be removed.

## 3. Vector Database Optimization

- Establish a unified and standardized structure for skill creation.
- Ensure consistent formatting across all skills.
- Review and update outdated knowledge.
- Remove duplicate embeddings.
- Maintain optimized retrieval performance.

## 4. Agent Availability Control

- New tasks must not be assigned to unavailable agents.
- Enforce agent availability checks before task allocation.

## 5. System-Wide Optimization

Perform optimization without loss of:

- Functionality
- Imported information
- Core operational logic

Optimization areas include:

- Agent lifecycle management (remove idle agents)
- Memory usage
- Storage allocation
- Database indexing
- Log retention (remove very old logs)
- Resource allocation efficiency

---

## 6. Container & Infrastructure Governance

- Optimization inside the container environment must be prioritized.
- External (outside container) optimization must be handled with extreme caution.
- File deletions outside the container require explicit approval from the Sovereign (User).
- No irreversible action outside the container without authorization.

---

## 7. Access Control Policy

- **Admin Users**
  - Full system access.
  - Can view all tasks across the system.

- **Standard Users**
  - Can view only tasks they created.
  - Can interact with the system regarding their own tasks (chat + task interface).

---

## 8. API Key Redundancy Verification

- Verify (or implement if missing):
  - Multiple API keys per provider.
  - Automatic rotation and fallback usage.
  - Provider-level load balancing where applicable.

---

## 9. Agent Optimization & Emergency Protocol

### Normal Optimization

If all agents are occupied:

- The Head of Council must initiate agent optimization.
- Identify and terminate idle agents.
- Free up capacity for new task allocation.

### Emergency Protocol

If:

- No agents are available
- No entity can receive a task

Then:

- The Head of Council may create a temporary emergency agent.
- Only one Head of Council may exist at any time.
- Emergency agent must use an available ID from the reserved Head-of-Council ID space (1xxxx).
- Upon task completion, the emergency agent must be terminated.

Strict enforcement:

- Only one active Head of Council at any time.

---

## 10. Future Scalability Plan

Prepare the system for scaling from:

**50,000 agents → 50,000,000+ agents**

Required changes:

- Expand agent ID length in the database.
- Update frontend display logic for large-scale agent rendering.
- Optimize indexing and retrieval structures.
- Ensure horizontal scalability readiness.

---

## Phase 11: Ecosystem Expansion 🌍 (FUTURE)

**Goal:** Scale from single-user to multi-user, multi-instance ecosystem.

### 11.1 Multi-User RBAC

**Sovereign Roles:**

- [ ] Primary Sovereign (full control)
- [ ] Deputy Sovereign (limited veto power)
- [ ] Observer (read-only access)

**Delegation:**

- [ ] Sovereign can delegate specific capabilities
- [ ] Temporary authority grants (time-limited)
- [ ] Emergency override transfer

### 11.2 Federation (Inter-Agentium Communication)

**Architecture:**

- [ ] Agentium instances can communicate
- [ ] Cross-instance task delegation
- [ ] Knowledge sharing between instances
- [ ] Federated voting on shared issues

**Use Cases:**

- Company departments (Engineering, Sales, HR)
- Collaborative research teams
- Distributed governance

### 11.3 Plugin Marketplace

**Developer Ecosystem:**

- [ ] Third-party tool submissions
- [ ] Verified plugin registry
- [ ] Revenue sharing model
- [ ] Plugin versioning and updates

**Plugin Types:**

- Custom channels (new messaging platforms)
- Specialized critics (domain-specific validation)
- AI model providers
- Knowledge sources (databases, APIs)

### 11.4 Mobile Applications

**Platforms:**

- [ ] iOS app (Swift)
- [ ] Android app (Kotlin)

**Features:**

- Push notifications for votes/alerts
- Voice command interface
- Offline mode (cached constitution, task queue)

---

---

## Phase 12: Agentium SDK & External Interface 🔌 (FUTURE)

**Goal:** Allow external systems and developers to interact with Agentium programmatically, with all governance and constitutional constraints preserved in every external call.

**Inspired by:** Rowboat's Python SDK pattern — rebuilt with Agentium's constitutional context baked in.

**Philosophy:** External callers get the power of Agentium, but never bypass its Constitution.

### 12.1 Python SDK

**Package:** `sdk/python/agentium/`

**Core Interface:**

```python
from agentium import SovereignClient, StatefulSession

client = SovereignClient(
    host="http://localhost:8000",
    api_key="<SOVEREIGN_API_KEY>",
    constitution_version="v1.2.4"   # Pinned — breaks if constitution changes
)

# Start a governed session
session = StatefulSession(client)

# Submit a task — routes through full hierarchy
response = session.delegate(
    task="Analyze Q3 reports and summarize findings",
    constraints={
        "max_cost_usd": 5.00,
        "privacy_level": "internal",
        "allowed_tiers": ["2xxxx", "3xxxx"]
    },
    acceptance_criteria={
        "format": "markdown",
        "max_length_words": 1000,
        "critic_validation": True
    }
)

# Response includes full governance trail
print(response.result)
print(response.constitutional_checks_passed)
print(response.critic_reviews)
print(response.audit_trail)
print(response.cost_usd)
```

**Features:**

- [ ] `SovereignClient` - Authenticated connection with constitution version pinning
- [ ] `StatefulSession` - Maintains conversation context across multiple calls
- [ ] `delegate(task, constraints, acceptance_criteria)` - Full governed task submission
- [ ] `get_audit_trail(session_id)` - Retrieve complete decision log
- [ ] `get_constitution(version)` - Fetch active or historical constitution
- [ ] `propose_amendment(diff)` - Trigger amendment workflow from SDK
- [ ] `list_agents(tier)` - Browse agent hierarchy
- [ ] Streaming support for long-running tasks
- [ ] Async/await support

**Files:**

- [ ] `sdk/python/agentium/__init__.py`
- [ ] `sdk/python/agentium/client.py`
- [ ] `sdk/python/agentium/session.py`
- [ ] `sdk/python/agentium/models.py`
- [ ] `sdk/python/agentium/exceptions.py`
- [ ] `sdk/python/README.md`
- [ ] `sdk/python/setup.py`

### 12.2 TypeScript SDK

**Package:** `sdk/typescript/`

**Core Interface:**

```typescript
import { AgentiumClient, StatefulSession } from "@agentium/sdk";

const client = new AgentiumClient({
  host: "http://localhost:8000",
  apiKey: process.env.AGENTIUM_KEY,
});

const session = new StatefulSession(client);
const response = await session.delegate({
  task: "Draft a response to this customer complaint",
  constraints: { privacyLevel: "internal" },
});
```

**Files:**

- [ ] `sdk/typescript/src/client.ts`
- [ ] `sdk/typescript/src/session.ts`
- [ ] `sdk/typescript/src/types.ts`
- [ ] `sdk/typescript/package.json`
- [ ] `sdk/typescript/README.md`

### 12.3 SDK Governance Rules

**What SDK callers CAN do:**

- [ ] Submit tasks (routed through full hierarchy)
- [ ] Query agent status and audit trail
- [ ] Propose amendments (triggers vote, doesn't bypass it)
- [ ] Read constitution and knowledge base
- [ ] Stream task progress events

**What SDK callers CANNOT do:**

- [ ] Bypass Constitutional Guard
- [ ] Skip critic validation
- [ ] Access Tier 3 MCP tools directly
- [ ] Impersonate an agent tier above their API key's authorization level
- [ ] Suppress audit logging

**Authentication:**

- [ ] SDK API keys issued per external system (not per user)
- [ ] Keys scoped to specific tiers and capabilities
- [ ] Key usage logged in audit trail like any other agent action
- [ ] Keys revocable via Council vote

### 12.4 Acceptance Criteria

- [ ] Python SDK installable via `pip install agentium-sdk`
- [ ] TypeScript SDK installable via `npm install @agentium/sdk`
- [ ] All SDK calls produce identical audit trails to direct API calls
- [ ] Constitution version pinning raises error if version mismatch
- [ ] SDK documentation with working examples for all major use cases
- [ ] SDK integration tests against live Agentium instance

---

## Success Metrics 📊

### Technical Metrics

**Performance:**

- [ ] 10,000 messages routed/hour without loss
- [ ] Constitutional check <50ms (SQL), <200ms (semantic)
- [ ] Vote quorum reached <24h average
- [ ] Zero agent ID collisions during concurrent spawning
- [ ] Vector DB query precision >85%
- [ ] Knowledge moderation queue cleared <48h average

**Reliability (from Research):**

- [ ] **87.8% error catch rate via critic layer**
- [ ] **92.1% overall success rate**
- [ ] **<7.9% residual error rate requiring human intervention**
- [ ] Checkpoint recovery from any decision point
- [ ] Context isolation (raw data never touches agent context)
- [ ] Orthogonal failure modes (critics use different models)

### Governance Metrics

**Democratic Process:**

- [ ] Successful amendment lifecycle (propose → debate → vote → enact)
- [ ] Emergency Head override logged and auditable
- [ ] Automatic liquidation of dormant agents (>30 days)
- [ ] Resource rebalancing reduces task queue by 20%

**Knowledge Quality:**

- [ ] Constitution semantically queryable ("What are core values?")
- [ ] Knowledge sharing increases task efficiency (measure via completion time)
- [ ] Duplicate knowledge rejection rate <5%

**Critic Effectiveness:**

- [ ] Critic veto catches errors before user exposure (87.8%)
- [ ] No self-certification (writers cannot approve own work)
- [ ] Orthogonal failure modes verified (different models)

---

## Implementation Priority Matrix

### 🔥 Immediate (This Week)

1. **Constitutional Guard Enhancement** - Add semantic checking (Tier 2)
2. **Critic Agent Framework** - Create 4xxxx/5xxxx/6xxxx agent types
3. **Acceptance Criteria Service** - Pre-declare success criteria

### ⚡ Short Term (Next 2 Weeks)

4. **Context Ray Tracing** - Role-based context visibility in Message Bus
5. **Remote Code Executor** - Docker service for sandboxed execution
6. **Checkpoint Service** - Time-travel recovery system
7. **API Key Resilience** (Phase 5.4) - Failover + all-keys-down notification

### 📅 Medium Term (Next Month)

8. **Amendment Service** - Complete constitutional amendment pipeline
9. **MCP Server Integration** (Phase 6.7) - Constitutional tool tier governance
10. **Voting UI** - Rich frontend for democratic deliberation
11. **Constitution Editor** - Full Markdown editor with semantic search

### 🔄 Ongoing

12. **Multi-Channel Integration** - Discord, Slack, Signal, Teams
13. **Testing & Benchmarking** - Load tests, reliability metrics
14. **Memory Management** - Automated cleanup and archiving

### 🔮 Future (After Core Stable)

15. **Agentium SDK** (Phase 12) - Python + TypeScript client libraries
16. **Federation** (Phase 11.2) - Inter-Agentium communication

---

## Critical Dependencies

### Infrastructure Stack

```
ChromaDB (Vector Storage) ✅ Running on port 8001
    ↓
Redis (Message Bus + Cache) ✅ Running on port 6379
    ↓
PostgreSQL (Entity Storage) ✅ Running on port 5432
    ↓
Celery (Background Tasks) ✅ Configured
    ↓
FastAPI (API Gateway) ✅ Running on port 8000
    ↓
React Frontend ✅ Running on port 3000
    ↓
Remote Executor (NEW) 🆕 - Docker sandbox for code execution (Done)
```

---

## Documentation Needs

### For Developers

- [ ] API documentation (OpenAPI/Swagger)
- [ ] Architecture diagrams (Mermaid)
- [ ] Database schema documentation
- [ ] Agent communication protocols
- [ ] Deployment guide (production)

### For Users

- [ ] Constitution writing guide
- [ ] Amendment proposal tutorial
- [ ] Multi-channel setup guide
- [ ] Troubleshooting common issues
- [ ] Best practices for agent orchestration

### For Contributors

- [ ] CONTRIBUTING.md
- [ ] Code style guide
- [ ] Testing guidelines
- [ ] Pull request template
- [ ] Issue templates (bug, feature, question)

---

## Deployment Considerations

### Local Development ✅

- [x] Docker Compose working on all platforms (Linux, macOS, Windows)
- [x] Hot reload for backend (FastAPI)
- [x] Hot reload for frontend (Vite)
- [x] Persistent volumes for data

### Production Deployment

**Infrastructure:**

- [ ] Kubernetes manifests (Helm charts)
- [ ] Load balancer configuration (Nginx/Traefik)
- [ ] SSL/TLS certificates (Let's Encrypt)
- [ ] CDN setup for frontend assets

**Scaling:**

- [ ] Horizontal pod autoscaling
- [ ] Database read replicas
- [ ] Redis cluster mode
- [ ] Vector DB sharding

**Monitoring:**

- [ ] Prometheus metrics export
- [ ] Grafana dashboards
- [ ] Loki for log aggregation
- [ ] Jaeger for distributed tracing

---

## Known Issues & Technical Debt

### High Priority

- [ ] Constitutional Guard semantic checking not implemented
- [ ] Amendment service not created
- [ ] Critic agents not implemented
- [ ] Remote executor not deployed
- [ ] Checkpoint service missing
- [ ] API Key Resilience service not formalized (Phase 5.4)

### Medium Priority

- [ ] WebSocket reconnection logic needs improvement
- [ ] Message Bus rate limiting not fully tested
- [ ] Vector DB index optimization needed
- [ ] Frontend error boundaries incomplete
- [ ] MCP Tool Registry UI not built (Phase 6.7)

### Low Priority

- [ ] UI polish (animations, transitions)
- [ ] Dark mode consistency
- [ ] Mobile responsiveness
- [ ] Accessibility (ARIA labels, keyboard navigation)
- [ ] SDK documentation (Phase 12 - future)

---

## Version History

**Current Version:** 0.7.0-alpha

**Changelog:**

### v0.7.0-alpha (Current)

- ✅ Knowledge Infrastructure complete (Vector DB + RAG)
- ✅ Initialization Protocol with democratic country naming
- ✅ Tool Creation Service with approval workflow
- ✅ Multi-channel integration (WhatsApp, Telegram)
- ✅ Agent Orchestrator with constitutional context injection
- 🚧 Constitutional Guard (needs semantic enhancement)
- 🚧 Voting Service (needs frontend integration)

### v0.1.0-alpha (Initial)

- ✅ Foundation: PostgreSQL, Redis, Docker Compose
- ✅ Entity models: Agents, Constitution, Voting, Audit
- ✅ Basic frontend: Dashboard, Agent Tree, Task List
- ✅ Multi-provider AI model support

---

_Last Updated: 2026-02-19_  
_Maintainer: Ashmin Dhungana_  
_Status: Active Development - Phase 7 ✅ COMPLETE | Phase 6 MCP Tools Done | Phase 8 Testing Next_

# End of Roadmap
