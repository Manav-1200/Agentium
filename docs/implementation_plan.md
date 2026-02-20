# Implement task_execution.md – Governance Architecture Alignment

Bring the existing backend implementation in line with the full specification in [task_execution.md](file:///e:/Agentium/docs/task_execution.md). Many pieces already exist; this plan focuses on **gaps and upgrades** only.

## Gap Summary

| Spec Section | Current State | Action |
|---|---|---|
| II. Task Entity | Most columns exist, missing `constitutional_basis`, `parent_task_id` FK, `RETRYING`/`ESCALATED`/`STOPPED` statuses, `SOVEREIGN` priority, `ONE_TIME`/`RECURRING` types | **Update model** |
| III. Governance Flow | Council deliberation + Head approval + Lead delegation + Critic review all exist | **Minor wiring** |
| IV. Self-Healing Loop | Retry exists (max 3) but no Lead analysis, no Council escalation after exhaustion | **Update retry + add escalation** |
| V. Knowledge Integration | [KnowledgeGovernanceService](file:///e:/Agentium/backend/services/knowledge_governance.py#68-451) + `KnowledgeService` + ChromaDB exist | ✅ Already implemented |
| VI. Data Retention | Cleanup for channel messages exists (30 days). No completed task cleanup, no orphan embedding removal, no ethos cleanup | **Add cleanup tasks** |
| VII. Multi-Channel Sync | `ChannelManager` (114KB), WebSocket, Redis pub/sub all exist | ✅ Already implemented |
| VIII. Communication Policy | Handled in Head ethos/prompt templates | ✅ Already implemented |
| IX.1 Event Sourcing | `status_history` JSON column exists but not a proper event log | **Add TaskEvent model** |
| IX.2 State Machine | No enforcement – any status can be set freely | **Add state machine** |
| IX.3 Auto-Scaling | [IdleGovernanceEngine](file:///e:/Agentium/backend/services/idle_governance.py#109-643) does agent liquidation but not scaling-up | **Add scaling trigger** |
| X. Safety Guarantees | ConstitutionalGuard enforces tier-based permissions | ✅ Already implemented |

---

## Proposed Changes

### Task Model Layer

#### [MODIFY] [task.py](file:///e:/Agentium/backend/models/entities/task.py)

1. **Add missing columns** to [Task](file:///e:/Agentium/backend/models/entities/task.py#64-409):
   - `constitutional_basis = Column(Text, nullable=True)` – reason the task is constitutionally valid
   - `parent_task_id = Column(String(36), ForeignKey('tasks.id'), nullable=True)` – for hierarchical task nesting
   - `execution_plan_id = Column(String(36), nullable=True)` – link to execution plan

2. **Add missing enum values**:
   - [TaskStatus](file:///e:/Agentium/backend/models/entities/task.py#22-40): add `RETRYING`, `ESCALATED`, `STOPPED`
   - [TaskPriority](file:///e:/Agentium/backend/models/entities/task.py#14-21): add `SOVEREIGN` (highest, skips all governance)
   - [TaskType](file:///e:/Agentium/backend/models/entities/task.py#41-62): add `ONE_TIME`, `RECURRING`

3. **Add parent-child relationship**:
   ```python
   parent_task = relationship("Task", remote_side="Task.id", backref="child_tasks")
   ```

4. **Update `max_retries` default** from `3` → `5`

5. **Update [fail()](file:///e:/Agentium/backend/models/entities/task.py#331-344) method** to:
   - Set status to `RETRYING` when retrying (instead of `ASSIGNED`)
   - Set status to `ESCALATED` after exhausting all 5 retries (instead of `FAILED`)

---

### State Machine Enforcement

#### [NEW] [task_state_machine.py](file:///e:/Agentium/backend/services/task_state_machine.py)

A lightweight service that enforces legal state transitions:

```
LEGAL_TRANSITIONS = {
    PENDING      → [DELIBERATING, APPROVED, CANCELLED]
    DELIBERATING → [APPROVED, REJECTED]
    APPROVED     → [DELEGATING, IN_PROGRESS, CANCELLED]
    DELEGATING   → [ASSIGNED]
    ASSIGNED     → [IN_PROGRESS, CANCELLED]
    IN_PROGRESS  → [REVIEW, COMPLETED, FAILED, RETRYING, STOPPED]
    REVIEW       → [COMPLETED, FAILED, RETRYING]
    RETRYING     → [IN_PROGRESS, ESCALATED]
    ESCALATED    → [IN_PROGRESS, CANCELLED, FAILED]
    FAILED       → [RETRYING]  (only if retry_count < max)
    COMPLETED    → []  (terminal)
    CANCELLED    → []  (terminal)
    STOPPED      → []  (terminal)
}
```

- `validate_transition(current, proposed)` → raises `IllegalStateTransition` on invalid moves
- Integrated into Task model via a `set_status()` method that calls validation before assignment

---

### Event Sourcing

#### [NEW] [task_events.py](file:///e:/Agentium/backend/models/entities/task_events.py)

```python
class TaskEvent(BaseEntity):
    __tablename__ = 'task_events'
    task_id     = Column(ForeignKey('tasks.id'))
    event_type  = Column(String(50))  # TaskCreated, TaskApproved, etc.
    actor_id    = Column(String(36))
    data        = Column(JSON)
    created_at  = Column(DateTime)
```

Events emitted from `Task.set_status()` and stored immutably. A `reconstruct_state(task_id)` utility replays events to derive current state.

---

### Self-Healing Execution Loop

#### [MODIFY] [task.py](file:///e:/Agentium/backend/models/entities/task.py)

Update [fail()](file:///e:/Agentium/backend/models/entities/task.py#331-344) to store structured failure reason and use `RETRYING` status:

```diff
 def fail(self, error_message: str, can_retry: bool = True):
     self.error_count += 1
-    self.last_error = error_message
+    self.last_error = json.dumps({
+        "message": error_message,
+        "retry_number": self.retry_count,
+        "timestamp": datetime.utcnow().isoformat()
+    })
     if can_retry and self.retry_count < self.max_retries:
         self.retry_count += 1
-        self.status = TaskStatus.ASSIGNED
+        self.status = TaskStatus.RETRYING
     else:
-        self.status = TaskStatus.FAILED
+        self.status = TaskStatus.ESCALATED
```

#### [MODIFY] [task_executor.py](file:///e:/Agentium/backend/services/tasks/task_executor.py)

Add a new Celery task `handle_task_escalation` that:
1. Queries for tasks with `status == ESCALATED`
2. Creates a Council deliberation for escalated tasks
3. Council decides: liquidate (cancel), modify scope (update description + retry), or allocate more resources (spawn agents)

---

### Data Retention

#### [MODIFY] [task_executor.py](file:///e:/Agentium/backend/services/tasks/task_executor.py)

Add new Celery task `sovereign_data_retention`:
- Delete completed tasks older than 30 days (preserving audit snapshots)
- Remove ethos entries for deleted agents
- Compress execution logs (archive to JSON summary)

#### [MODIFY] [celery_app.py](file:///e:/Agentium/backend/celery_app.py)

Add beat schedule entry:
```python
'sovereign-data-retention': {
    'task': 'backend.services.tasks.task_executor.sovereign_data_retention',
    'schedule': 86400.0,  # Daily
},
```

---

### Auto-Scaling Governance

#### [MODIFY] [idle_governance.py](file:///e:/Agentium/backend/services/idle_governance.py)

Add `auto_scale_check()` method to [EnhancedIdleGovernanceEngine](file:///e:/Agentium/backend/services/idle_governance.py#109-643):
- Monitor queue depth (pending tasks count)
- If threshold exceeded (e.g., >10 pending tasks), trigger Council micro-vote to spawn additional 3xxxx agents
- Log scaling decisions in audit trail

---

### API Layer

#### [MODIFY] [tasks.py](file:///e:/Agentium/backend/api/routes/tasks.py)

Add new endpoint:
- `POST /tasks/{task_id}/escalate` – manually escalate a task to Council

Update [_serialize()](file:///e:/Agentium/backend/api/routes/tasks.py#16-45) to include new fields (`constitutional_basis`, `parent_task_id`, event count).

#### [MODIFY] [task.py](file:///e:/Agentium/backend/api/schemas/task.py)

Add `constitutional_basis` and `parent_task_id` to [TaskCreate](file:///e:/Agentium/backend/api/schemas/task.py#20-38) and [TaskResponse](file:///e:/Agentium/backend/api/schemas/task.py#40-56).

---

## User Review Required

> [!IMPORTANT]
> **Database Migration Required**: The new columns (`constitutional_basis`, `parent_task_id`, `execution_plan_id`) and new table (`task_events`) require an Alembic migration. This is a non-breaking change (all new columns are nullable), but the migration must be run before the updated code deploys.

> [!WARNING]
> **Status Enum Changes**: Adding `RETRYING`, `ESCALATED`, `STOPPED` to [TaskStatus](file:///e:/Agentium/backend/models/entities/task.py#22-40) and `SOVEREIGN` to [TaskPriority](file:///e:/Agentium/backend/models/entities/task.py#14-21) requires a PostgreSQL enum-type migration. Alembic can handle this with `op.execute("ALTER TYPE taskstatus ADD VALUE 'retrying'")` etc.

---

## Verification Plan

### Automated Tests

**Run existing tests** to confirm no regressions:
```bash
cd e:\Agentium
python -m pytest tests/ -v
```

**New test: State Machine** (`tests/test_task_state_machine.py`):
- Test all legal transitions succeed
- Test all illegal transitions raise `IllegalStateTransition`
- Run with: `python -m pytest tests/test_task_state_machine.py -v`

**New test: Task Event Sourcing** (`tests/test_task_events.py`):
- Test event emission on status changes
- Test state reconstruction from events
- Run with: `python -m pytest tests/test_task_events.py -v`

### Manual Verification

The user should verify the following when the backend is running:
1. **Create a task** via `POST /api/tasks/` and confirm new fields (`constitutional_basis`, `parent_task_id`) are accepted and returned
2. **Verify state machine** by attempting an illegal status transition via `PATCH /api/tasks/{id}` (e.g., `COMPLETED` → `PENDING`) and confirming it returns a 400 error
3. **Run Alembic migration** with `alembic upgrade head` in the backend container to confirm no migration errors
