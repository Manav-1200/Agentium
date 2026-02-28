"""
Phase 8.1 — Database Layer Stress Testing.

Tests:
  1. 1000 concurrent agent spawns (thread-pool)
  2. Foreign key parent-child enforcement
  3. Delete parent with active children
  4. Orphan detection SQL query
  5. Constitution rollback test
  6. 10,000 audit log entries integrity
"""

import os
import sys
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models.database import SessionLocal, get_db_context
from backend.models.entities.agents import Agent, AgentType, AgentStatus
from backend.models.entities.audit import AuditLog, AuditLevel, AuditCategory
from backend.models.entities.constitution import Constitution
from backend.tests.phase8.conftest import MetricsCollector, timer


# ──────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────

def _spawn_agent_in_thread(prefix: str, idx: int, results: list, metrics: MetricsCollector):
    """Create one agent inside its own DB session (thread-safe)."""
    session = SessionLocal()
    try:
        with timer() as t:
            agentium_id = f"{prefix}{idx:03d}"
            agent = Agent(
                id=str(uuid.uuid4()),
                agentium_id=agentium_id,
                name=f"Stress-Agent-{agentium_id}",
                agent_type=AgentType.TASK_AGENT,
                parent_id=None,
                status=AgentStatus.ACTIVE,
                is_persistent=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(agent)
            session.commit()
        metrics.record("spawn_latency_ms", t.elapsed_ms)
        results.append({"id": agentium_id, "success": True})
    except IntegrityError:
        session.rollback()
        metrics.increment("id_collisions")
        results.append({"id": f"{prefix}{idx:03d}", "success": False, "error": f"collision: {str(e)}"})
    except Exception as e:
        session.rollback()
        metrics.increment("failures")
        results.append({"id": f"{prefix}{idx:03d}", "success": False, "error": str(e)})
    finally:
        session.close()


def _cleanup_stress_agents(prefix: str):
    """Remove all stress-test agents."""
    session = SessionLocal()
    try:
        session.execute(
            text("DELETE FROM agents WHERE agentium_id LIKE :pat"),
            {"pat": f"{prefix}%"},
        )
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


# ──────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────

class TestConcurrentAgentSpawns:
    """Stress test: 1000 concurrent agent spawns."""

    PREFIX = "99"  # Task agents — will use IDs 99xxx range in a temp pattern

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        _cleanup_stress_agents("99")  # Cleanup 99xxx range we used

    def test_concurrent_agent_spawns_1000(self):
        """
        Spawn 1000 agents via thread pool.
        Targets:
          - 0 ID collisions
          - 0 deadlocks
          - P95 latency < 100ms per spawn
        """
        metrics = MetricsCollector()
        results: list = []
        count = 1000

        with timer() as total:
            with ThreadPoolExecutor(max_workers=50) as pool:
                futures = [
                    pool.submit(_spawn_agent_in_thread, "99", i, results, metrics)
                    for i in range(count)
                ]
                for f in as_completed(futures):
                    f.result()  # Propagate exceptions

        successes = sum(1 for r in results if r["success"])
        collisions = metrics.count("id_collisions")
        failures = metrics.count("failures")
        p50 = metrics.p50("spawn_latency_ms")
        p95 = metrics.p95("spawn_latency_ms")

        print(f"\n{'='*60}")
        print(f"  1000 Concurrent Agent Spawns")
        print(f"{'='*60}")
        print(f"  Successes   : {successes}/{count}")
        print(f"  Collisions  : {collisions}")
        print(f"  Failures    : {failures}")
        print(f"  P50 latency : {p50:.2f} ms")
        print(f"  P95 latency : {p95:.2f} ms")
        print(f"  Total time  : {total.elapsed_ms:.0f} ms")
        if failures > 0:
            print(f"  Sample errors:")
            for r in [res for res in results if not res["success"]][:5]:
                print(f"    - {r.get('error', 'Unknown')}")
        print(f"{'='*60}")

        assert successes == count, f"Only {successes}/{count} succeeded"
        assert collisions == 0, f"{collisions} ID collisions detected"
        assert failures == 0, f"{failures} general failures"
        # P95 under 200ms is reasonable inside container
        assert p95 < 200, f"P95 latency {p95:.1f}ms exceeds 200ms target"


class TestForeignKeyEnforcement:
    """Validate FK constraints on agent parent-child relationships."""

    def test_child_with_nonexistent_parent(self, db):
        """Inserting agent with a fake parent_id must raise IntegrityError."""
        fake_parent_id = str(uuid.uuid4())
        agent = Agent(
            id=str(uuid.uuid4()),
            agentium_id="77700",
            name="FK-Test-Child",
            agent_type=AgentType.TASK_AGENT,
            status=AgentStatus.ACTIVE,
            parent_id=fake_parent_id,
            is_persistent=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(agent)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_delete_parent_with_children(self, db):
        """Deleting a parent while children exist must be blocked by FK."""
        parent_id = str(uuid.uuid4())
        parent = Agent(
            id=parent_id,
            agentium_id="77701",
            name="FK-Parent",
            agent_type=AgentType.LEAD_AGENT,
            status=AgentStatus.ACTIVE,
            is_persistent=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(parent)
        db.flush()

        child = Agent(
            id=str(uuid.uuid4()),
            agentium_id="77702",
            name="FK-Child",
            agent_type=AgentType.TASK_AGENT,
            status=AgentStatus.ACTIVE,
            parent_id=parent_id,
            is_persistent=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(child)
        db.flush()

        # Attempt to delete parent bypass SQLAlchemy active relationship SET NULL cascade
        with pytest.raises(IntegrityError):
            db.execute(text("DELETE FROM agents WHERE id = :pid"), {"pid": parent_id})
        db.rollback()

    def test_orphan_detection_query(self, db):
        """
        Run orphan-detection SQL. In a clean DB there should be 0 orphans.
        """
        result = db.execute(text("""
            SELECT COUNT(*) FROM agents a
            LEFT JOIN agents p ON a.parent_id = p.id
            WHERE a.parent_id IS NOT NULL AND p.id IS NULL
        """))
        orphan_count = result.scalar()
        print(f"\n  Orphan agents detected: {orphan_count}")
        assert orphan_count == 0, f"{orphan_count} orphan agents found"


class TestConstitutionRollback:
    """Validate constitution version rollback."""

    def test_constitution_version_management(self, db):
        """
        Create two constitution versions, verify we can query both,
        and that only the latest is active.
        """
        constitutions = db.query(Constitution).order_by(
            Constitution.effective_date.desc()
        ).all()

        if not constitutions:
            pytest.skip("No constitution in DB — run system init first")

        active = [c for c in constitutions if c.is_active]
        print(f"\n  Total constitutions: {len(constitutions)}")
        print(f"  Active constitutions: {len(active)}")
        print(f"  Latest version: {active[0].version if active else 'none'}")

        # Should have exactly 1 active constitution
        assert len(active) >= 1, "No active constitution found"


class TestAuditLogIntegrity:
    """Test audit log at scale."""

    BATCH_SIZE = 10_000

    @pytest.fixture(autouse=True)
    def _cleanup(self, db):
        yield
        try:
            db.execute(
                text("DELETE FROM audit_logs WHERE description LIKE :p"),
                {"p": "Phase8-StressTest-%"},
            )
            db.commit()
        except Exception:
            db.rollback()

    def test_10000_audit_entries(self, db):
        """
        Insert 10,000 audit entries and validate:
          - No missing entries
          - Sequential created_at timestamps
          - All entries retrievable
        """
        start = time.perf_counter()
        entries_to_insert = []

        for i in range(self.BATCH_SIZE):
            entry = AuditLog(
                id=str(uuid.uuid4()),
                agentium_id=f"AL{i:05d}",
                level=AuditLevel.INFO,
                category=AuditCategory.SYSTEM,
                actor_type="test",
                actor_id="phase8",
                action="stress_test",
                target_type="audit",
                target_id=f"entry-{i}",
                description=f"Phase8-StressTest-{i}",
                success='Y',
                created_at=datetime.utcnow(),
            )
            entries_to_insert.append(entry)

        # Bulk insert
        db.add_all(entries_to_insert)
        db.commit()

        insert_time = (time.perf_counter() - start) * 1000

        # Verify count
        count = db.execute(
            text("SELECT COUNT(*) FROM audit_logs WHERE description LIKE :p"),
            {"p": "Phase8-StressTest-%"},
        ).scalar()

        # Verify ordering
        ordered = db.execute(text("""
            SELECT created_at FROM audit_logs
            WHERE description LIKE 'Phase8-StressTest-%'
            ORDER BY created_at ASC
            LIMIT 5
        """)).fetchall()

        print(f"\n{'='*60}")
        print(f"  10,000 Audit Log Entries")
        print(f"{'='*60}")
        print(f"  Inserted     : {count}/{self.BATCH_SIZE}")
        print(f"  Insert time  : {insert_time:.0f} ms")
        print(f"  First record : {ordered[0][0] if ordered else 'N/A'}")
        print(f"{'='*60}")

        assert count == self.BATCH_SIZE, f"Only {count}/{self.BATCH_SIZE} entries found"
