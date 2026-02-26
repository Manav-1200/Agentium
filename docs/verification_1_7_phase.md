# 🧠 Agentium — Remaining Implementation Items

> Consolidated list of features that are **not yet implemented** or **partially implemented** across Phases 4–7.

---

# 🚨 High-Priority Missing Features

# ⚠️ Medium Priority (Backend Exists, Frontend Missing)

## 4️⃣ Provider Performance Metrics Dashboard

**Phase 5**

**Backend:** ✅ Logs latency, cost, success/failure  
**Frontend:** ❌ Aggregation + visualization missing

### Missing:

- Aggregated provider comparison
- Cost over time charts
- Success rate per provider
- Average latency visualization
- Model-level breakdown

---

## 5️⃣ Checkpoint Branch Diff View

**Phase 6 + Phase 7**

**Backend:** ✅ `compare_branches()` implemented  
**Frontend:** ❌ Visualization missing

### Missing:

- Side-by-side branch comparison UI
- Result differences highlighting
- Agent state diff visualization
- Artifact comparison
- Change summary view

---

# 🧩 UX / Productivity Enhancements

## 6️⃣ Drag-and-Drop Agent Reassignment

**Phase 7**

**Status:** ❌ Not implemented

### Missing:

- Drag-and-drop in `AgentTree`
- Real-time hierarchy updates
- Capability validation on reassignment
- Optimistic UI updates

---

## 7️⃣ Checkpoint Export / Import

**Phase 7**

**Status:** ❌ Not implemented

### Missing:

- Export checkpoint as JSON
- Import checkpoint from JSON
- Integrity validation before restore
- Conflict resolution handling

### Use Cases:

- Backup
- Migration
- Debugging
- Sharing execution branches

---

No core architectural deficiencies remain.
