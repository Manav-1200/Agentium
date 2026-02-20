# Task Execution Architecture – Implementation Checklist

## 1. Task Model Updates ([task.py](file:///e:/Agentium/backend/api/schemas/task.py))
- [ ] Add missing fields: `constitutional_basis`, `hierarchical_id`, `execution_plan_id`, `parent_task_id`
- [ ] Add `RETRYING`, `ESCALATED`, `STOPPED` to [TaskStatus](file:///e:/Agentium/backend/models/entities/task.py#22-40) enum
- [ ] Add `SOVEREIGN` priority level to [TaskPriority](file:///e:/Agentium/backend/models/entities/task.py#14-21)
- [ ] Add `ONE_TIME`, `RECURRING` to [TaskType](file:///e:/Agentium/backend/models/entities/task.py#41-62) enum
- [ ] Increase `max_retries` default from 3 → 5
- [ ] Add parent-child task relationship

## 2. State Machine Enforcement (`task_state_machine.py`)
- [ ] Create state machine service with legal transition map
- [ ] Integrate validation into Task model status changes
- [ ] Block illegal transitions (raise error)

## 3. Self-Healing Execution Loop ([task.py](file:///e:/Agentium/backend/api/schemas/task.py) + [task_executor.py](file:///e:/Agentium/backend/services/tasks/task_executor.py))
- [ ] Implement structured failure reason storage
- [ ] Update retry logic: Lead analyzes failure → plan refinement → retry
- [ ] Add escalation to Council after 5 failed retries
- [ ] Add Council decision options: liquidate, modify scope, allocate resources

## 4. Event Sourcing (`task_events.py`)
- [ ] Create `TaskEvent` model with event types
- [ ] Emit events on every state change
- [ ] Add method to reconstruct task state from events

## 5. Data Retention & Cleanup ([task_executor.py](file:///e:/Agentium/backend/services/tasks/task_executor.py) + [celery_app.py](file:///e:/Agentium/backend/celery_app.py))
- [ ] Implement completed task cleanup (>30 days)
- [ ] Implement orphan embedding removal
- [ ] Implement execution log compression
- [ ] Implement constitutional history archival
- [ ] Implement deleted agent ethos removal
- [ ] Add Celery beat schedule entry for daily data retention

## 6. Task API Updates ([api/routes/tasks.py](file:///e:/Agentium/backend/api/routes/tasks.py) + [api/schemas/task.py](file:///e:/Agentium/backend/api/schemas/task.py))
- [ ] Add task escalation endpoint
- [ ] Add subtask listing endpoint
- [ ] Add task events/history endpoint
- [ ] Update schemas for new fields

## 7. Verification
- [ ] Run existing tests to ensure no regressions
- [ ] Write unit tests for state machine transitions
- [ ] Write unit test for event sourcing
- [ ] Manual: verify task CRUD with new fields via API
