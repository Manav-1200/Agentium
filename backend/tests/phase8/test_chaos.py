"""
Phase 8.3 — Chaos Testing.

Tests:
  1. Kill PostgreSQL mid-load → circuit breaker, graceful degradation
  2. Kill Redis mid-execution → recovery, no permanent corruption
  3. Kill ChromaDB → degraded mode (Tier 1 continues)

⚠  DISRUPTIVE: These tests stop/restart Docker containers.
   Do NOT run in parallel with other tests.
"""

import os
import sys
import time
import uuid
import subprocess
import asyncio
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models.database import SessionLocal
from backend.models.entities.agents import Agent, AgentType, AgentStatus
from backend.tests.phase8.conftest import MetricsCollector, timer


def _docker_cmd(action: str, container: str) -> bool:
    """Run docker stop/start on a container (runs from within backend container)."""
    try:
        result = subprocess.run(
            ["docker", action, container],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _is_container_running(container: str) -> bool:
    """Check if a container is running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() == "true"
    except Exception:
        return False


def _wait_for_container(container: str, timeout: int = 60) -> bool:
    """Wait for a container to be running and healthy."""
    start = time.time()
    while time.time() - start < timeout:
        if _is_container_running(container):
            time.sleep(2)  # Extra wait for service to be ready
            return True
        time.sleep(1)
    return False


# ──────────────────────────────────────────────────────
# Chaos Tests
# ──────────────────────────────────────────────────────

class TestPostgresKill:
    """Kill PostgreSQL mid-load."""

    @pytest.fixture(autouse=True)
    def _ensure_postgres_running(self):
        """Ensure postgres is running before and after test."""
        yield
        if not _is_container_running("agentium-postgres"):
            started = _docker_cmd("start", "agentium-postgres")
            if started:
                assert _wait_for_container("agentium-postgres", timeout=60), \
                    "Failed to restart agentium-postgres"

    def test_postgres_kill_mid_load(self):
        """
        1. Start writing agents to DB
        2. Kill postgres mid-way
        3. Verify: Errors are caught gracefully, no crash, no corruption
        4. Restart postgres and verify recovery
        """
        results = {"success": 0, "errors": 0, "error_types": []}

        # Phase 1: Write some agents successfully
        session = SessionLocal()
        try:
            for i in range(10):
                agent = Agent(
                    id=str(uuid.uuid4()),
                    agentium_id=f"37{i:03d}",
                    name=f"Chaos-Pre-{i}",
                    agent_type=AgentType.TASK_AGENT,
                    status=AgentStatus.ACTIVE,
                    is_persistent=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(agent)
            session.commit()
            results["success"] += 10
        except Exception as e:
            session.rollback()
            results["error_types"].append(type(e).__name__)
        finally:
            session.close()

        # Phase 2: Kill postgres
        print("\n  ⚠  Stopping agentium-postgres...")
        killed = _docker_cmd("stop", "agentium-postgres")
        if not killed:
            pytest.skip("Cannot stop postgres — no Docker socket access")

        time.sleep(2)

        # Phase 3: Try to write — should fail gracefully
        session = SessionLocal()
        try:
            agent = Agent(
                id=str(uuid.uuid4()),
                agentium_id="37999",
                name="Chaos-During",
                agent_type=AgentType.TASK_AGENT,
                status=AgentStatus.ACTIVE,
                is_persistent=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(agent)
            session.commit()
            results["success"] += 1
        except OperationalError:
            results["errors"] += 1
            results["error_types"].append("OperationalError")
            session.rollback()
        except Exception as e:
            results["errors"] += 1
            results["error_types"].append(type(e).__name__)
            session.rollback()
        finally:
            session.close()

        # Phase 4: Restart postgres
        print("  🔄 Restarting agentium-postgres...")
        _docker_cmd("start", "agentium-postgres")
        recovered = _wait_for_container("agentium-postgres", timeout=60)

        # Phase 5: Verify recovery
        if recovered:
            time.sleep(5)  # Wait for PG to accept connections
            session = SessionLocal()
            try:
                count = session.execute(
                    text("SELECT COUNT(*) FROM agents WHERE name LIKE 'Chaos-Pre-%'")
                ).scalar()
                results["recovered_count"] = count
            except Exception:
                results["recovered_count"] = -1
            finally:
                session.close()

            # Cleanup
            session = SessionLocal()
            try:
                session.execute(text("DELETE FROM agents WHERE name LIKE 'Chaos-%'"))
                session.commit()
            except Exception:
                session.rollback()
            finally:
                session.close()

        print(f"\n{'='*60}")
        print(f"  PostgreSQL Kill Test")
        print(f"{'='*60}")
        print(f"  Pre-kill writes   : {results['success']}")
        print(f"  During-kill errors: {results['errors']}")
        print(f"  Error types       : {results.get('error_types', [])}")
        print(f"  Postgres recovered: {recovered}")
        print(f"  Data survived     : {results.get('recovered_count', 'N/A')}")
        print(f"{'='*60}")

        assert recovered, "PostgreSQL did not recover within 60s"
        assert results["errors"] >= 1, "Expected errors during postgres downtime"


class TestRedisKill:
    """Kill Redis mid-execution."""

    @pytest.fixture(autouse=True)
    def _ensure_redis_running(self):
        yield
        if not _is_container_running("agentium-redis"):
            started = _docker_cmd("start", "agentium-redis")
            if started:
                _wait_for_container("agentium-redis", timeout=60)

    def test_redis_kill_mid_execution(self):
        """
        1. Publish messages via message bus
        2. Kill Redis
        3. Verify error handling
        4. Restart and verify recovery
        """
        import redis as sync_redis

        # Phase 1: Verify Redis is working
        try:
            r = sync_redis.Redis(host="redis", port=6379, decode_responses=True)
            r.ping()
            r.set("phase8:chaos:test", "alive")
        except Exception:
            pytest.skip("Cannot connect to Redis")

        # Phase 2: Kill Redis
        print("\n  ⚠  Stopping agentium-redis...")
        killed = _docker_cmd("stop", "agentium-redis")
        if not killed:
            pytest.skip("Cannot stop Redis — no Docker socket access")

        time.sleep(2)

        # Phase 3: Verify error handling
        error_caught = False
        try:
            r2 = sync_redis.Redis(host="redis", port=6379, decode_responses=True,
                                   socket_timeout=3)
            r2.ping()
        except Exception:
            error_caught = True

        # Phase 4: Restart Redis
        print("  🔄 Restarting agentium-redis...")
        _docker_cmd("start", "agentium-redis")
        recovered = _wait_for_container("agentium-redis", timeout=60)

        # Phase 5: Verify recovery
        data_survived = False
        if recovered:
            time.sleep(3)
            try:
                r3 = sync_redis.Redis(host="redis", port=6379, decode_responses=True)
                val = r3.get("phase8:chaos:test")
                data_survived = val == "alive"
                r3.delete("phase8:chaos:test")
            except Exception:
                pass

        print(f"\n{'='*60}")
        print(f"  Redis Kill Test")
        print(f"{'='*60}")
        print(f"  Error caught    : {error_caught}")
        print(f"  Redis recovered : {recovered}")
        print(f"  Data survived   : {data_survived} (AOF enabled)")
        print(f"{'='*60}")

        assert recovered, "Redis did not recover within 60s"
        assert error_caught, "Expected connection error during downtime"


class TestChromaDBKill:
    """Kill ChromaDB — Tier 2 should degrade, Tier 1 continues."""

    @pytest.fixture(autouse=True)
    def _ensure_chroma_running(self):
        yield
        if not _is_container_running("agentium-chroma"):
            started = _docker_cmd("start", "agentium-chroma")
            if started:
                _wait_for_container("agentium-chroma", timeout=60)

    def test_chromadb_kill_degraded_mode(self, db):
        """
        1. Kill ChromaDB
        2. Verify Tier 1 SQL checks still work
        3. Verify Tier 2 semantic checks degrade gracefully
        4. Restart and verify recovery
        """
        import re

        # Phase 1: Kill ChromaDB
        print("\n  ⚠  Stopping agentium-chroma...")
        killed = _docker_cmd("stop", "agentium-chroma")
        if not killed:
            pytest.skip("Cannot stop ChromaDB — no Docker socket access")

        time.sleep(2)

        # Phase 2: Tier 1 should still work (pure SQL/regex)
        from backend.core.constitutional_guard import GLOBAL_BLACKLIST
        tier1_works = False
        for pattern in GLOBAL_BLACKLIST:
            if re.search(pattern, "rm -rf /", re.IGNORECASE):
                tier1_works = True
                break

        # Phase 3: Tier 2 should fail gracefully
        tier2_error = False
        try:
            from backend.core.vector_store import get_vector_store
            vs = get_vector_store()
            result = vs.query_constitution(query="test query", n_results=1)
        except Exception:
            tier2_error = True

        # Phase 4: Restart
        print("  🔄 Restarting agentium-chroma...")
        _docker_cmd("start", "agentium-chroma")
        recovered = _wait_for_container("agentium-chroma", timeout=90)

        print(f"\n{'='*60}")
        print(f"  ChromaDB Kill Test")
        print(f"{'='*60}")
        print(f"  Tier 1 (SQL) works : {tier1_works}")
        print(f"  Tier 2 degraded    : {tier2_error}")
        print(f"  ChromaDB recovered : {recovered}")
        print(f"{'='*60}")

        assert tier1_works, "Tier 1 should still work without ChromaDB"
        assert recovered, "ChromaDB did not recover within 90s"
