"""
Database configuration and session management for Agentium.
PostgreSQL-backed with connection pooling and async support.
"""

import os
from typing import Generator, Optional
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool

from backend.models.entities.base import Base

# Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://agentium:agentium@localhost:5432/agentium"
)

# Engine configuration with pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true"
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Thread-local sessions
db_session = scoped_session(SessionLocal)


@event.listens_for(Engine, "connect")
def set_timezone(dbapi_conn, connection_record):
    """Set UTC timezone for all connections."""
    cursor = dbapi_conn.cursor()
    cursor.execute("SET timezone TO 'UTC'")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI endpoints.
    Yields a database session and ensures cleanup.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for database sessions in non-request contexts."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_next_agentium_id(db: Session, prefix: str) -> str:
    """
    Generate next available ID for a given prefix.
    Thread-safe sequence generation using SELECT FOR UPDATE.
    """
    from backend.models.entities.agents import Agent

    result = db.execute(
        text("""
            SELECT agentium_id FROM agents
            WHERE agentium_id LIKE :pattern
            ORDER BY agentium_id DESC
            FOR UPDATE
        """),
        {"pattern": f"{prefix}%"}
    ).fetchone()

    if result:
        last_num = int(result[0][1:])
        new_num = last_num + 1
    else:
        new_num = 1

    return f"{prefix}{new_num:04d}"


def check_health() -> dict:
    """Check database connectivity and performance."""
    try:
        start = datetime.utcnow()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        return {
            "status": "healthy",
            "latency_ms": round(latency, 2),
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "database": "disconnected"
        }


def _ensure_system_settings(db: Session):
    """
    Create the system_settings table if it doesn't exist and seed
    default budget values. Uses raw SQL so it works before Alembic
    has run the dedicated migration.
    """
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key         VARCHAR(128) PRIMARY KEY,
            value       TEXT         NOT NULL,
            description TEXT,
            updated_at  TIMESTAMP    NOT NULL DEFAULT NOW()
        )
    """))

    # Seed defaults only if rows don't exist yet
    db.execute(text("""
        INSERT INTO system_settings (key, value, description, updated_at)
        VALUES
            ('daily_token_limit', '100000',
             'Maximum tokens per day across all API providers', NOW()),
            ('daily_cost_limit',  '5.0',
             'Maximum USD cost per day across all API providers', NOW())
        ON CONFLICT (key) DO NOTHING
    """))
    db.commit()


def create_initial_data(db: Session):
    """
    Minimal seeding after tables are created.
    Constitution and Head of Council are created by PersistentCouncilService.
    """
    _ensure_system_settings(db)


def init_db():
    """
    Initialize database — create all tables via SQLAlchemy metadata.
    Imports every entity so their mappers register with Base.metadata
    before create_all() runs.
    """
    # ── Core / Base ──────────────────────────────────────────────────────────
    from backend.models.entities.base import Base  # noqa: F401

    # ── User & Auth ──────────────────────────────────────────────────────────
    from backend.models.entities.user import User  # noqa: F401
    from backend.models.entities.user_config import (  # noqa: F401
        UserModelConfig, ModelUsageLog, ProviderType, ConnectionStatus
    )

    # ── Chat ─────────────────────────────────────────────────────────────────
    from backend.models.entities.chat_message import (  # noqa: F401
        ChatMessage, Conversation
    )

    # ── Constitution & Ethos ─────────────────────────────────────────────────
    from backend.models.entities.constitution import (  # noqa: F401
        Constitution, Ethos, DocumentType
    )

    # ── Agents ───────────────────────────────────────────────────────────────
    from backend.models.entities.agents import (  # noqa: F401
        Agent, HeadOfCouncil, CouncilMember, LeadAgent, TaskAgent,
        AgentType, AgentStatus
    )

    # ── Tasks ────────────────────────────────────────────────────────────────
    from backend.models.entities.task import (  # noqa: F401
        Task, SubTask, TaskAuditLog, TaskStatus, TaskPriority, TaskType
    )

    # ── Voting ───────────────────────────────────────────────────────────────
    from backend.models.entities.voting import (  # noqa: F401
        TaskDeliberation, IndividualVote, VotingRecord,
        AmendmentVoting, AmendmentStatus
    )

    # ── Audit ────────────────────────────────────────────────────────────────
    from backend.models.entities.audit import (  # noqa: F401
        AuditLog, ConstitutionViolation, SessionLog, HealthCheck,
        AuditLevel, AuditCategory
    )

    # ── Monitoring ───────────────────────────────────────────────────────────
    from backend.models.entities.monitoring import (  # noqa: F401
        AgentHealthReport, ViolationReport, ViolationSeverity,
        TaskVerification, PerformanceMetric, MonitoringAlert, MonitoringStatus
    )

    # ── Critics ──────────────────────────────────────────────────────────────
    from backend.models.entities.critics import (  # noqa: F401
        CriticAgent, CritiqueReview, CriticType, CriticVerdict
    )

    # ── Channels ─────────────────────────────────────────────────────────────
    from backend.models.entities.channels import (  # noqa: F401
        ExternalChannel, ExternalMessage, ChannelType, ChannelStatus
    )

    # ── Scheduled Tasks ──────────────────────────────────────────────────────
    from backend.models.entities.scheduled_task import (  # noqa: F401
        ScheduledTask, ScheduledTaskExecution
    )

    # Create all tables that don't exist yet
    Base.metadata.create_all(bind=engine)

    # Seed initial/system data
    with get_db_context() as db:
        create_initial_data(db)