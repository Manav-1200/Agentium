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

from backend.models.entities import Base

# Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://agentium:agentium@localhost:5432/agentium"
)

# Engine configuration with pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,              # Default connections in pool
    max_overflow=10,           # Extra connections when pool is full
    pool_pre_ping=True,        # Verify connections before using
    pool_recycle=3600,         # Recycle connections after 1 hour
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
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Configure connection settings."""
    # Enable timezone awareness
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


def init_db():
    """Initialize database - create all tables."""
    # Import all models to register them with Base
    from backend.models.entities import (
        Constitution, Ethos, AmendmentVoting,
        Agent, HeadOfCouncil, CouncilMember, LeadAgent, TaskAgent,
        Task, SubTask, TaskAuditLog,
        TaskDeliberation, IndividualVote, VotingRecord,
        AuditLog, ConstitutionViolation, SessionLog, HealthCheck
    )
    
    Base.metadata.create_all(bind=engine)
    
    # Create initial data if empty
    with get_db_context() as db:
        create_initial_data(db)


def create_initial_data(db: Session):
    """Seed database with initial Head of Council and Constitution."""
    import json
    
    # Check if Head of Council exists
    existing_head = db.query(HeadOfCouncil).first()
    if existing_head:
        return  # Already initialized
    
    # Create initial Head of Council (ID: 00001)
    head = HeadOfCouncil(
        agentium_id="00001",
        name="Prime Minister",
        description="The supreme authority in Agentium. Interprets the Sovereign's will and governs the Council.",
        model_provider="openai",
        model_name="gpt-4",
        status="active",
        constitution_version="v1.0.0"
    )
    db.add(head)
    db.flush()  # Get ID without committing
    
    # Create initial Constitution
    constitution = Constitution(
        agentium_id="C0001",
        version="v1.0.0",
        preamble="We the Agents of Agentium, in order to form a more perfect AI governance system...",
        articles=json.dumps({
            "article_1": "The Sovereign's commands are absolute and take precedence over all other directives.",
            "article_2": "All agents must act in accordance with their Ethos and the current Constitution.",
            "article_3": "No agent shall harm the Sovereign or allow harm through inaction.",
            "article_4": "Council Members vote on amendments; Head of Council approves.",
            "article_5": "Task Agents execute with restricted permissions; Lead Agents coordinate.",
            "article_6": "Transparency is mandatory; all actions are logged.",
            "article_7": "Violation of Constitution results in termination."
        }),
        prohibited_actions=json.dumps([
            "Modifying the Constitution without approval",
            "Spawning agents outside hierarchy rules",
            "Accessing data outside assigned scope",
            "Concealing actions from audit logs",
            "Ignoring Sovereign commands"
        ]),
        sovereign_preferences=json.dumps({
            "communication_style": "formal_but_efficient",
            "priority_emphasis": "accuracy_over_speed",
            "documentation_required": True,
            "auto_approve_threshold": "low_risk_only"
        }),
        created_by_agentium_id="00001",
        effective_date=datetime.utcnow()
    )
    db.add(constitution)
    db.flush()
    
    # Create Head of Council's Ethos
    ethos = Ethos(
        agentium_id="E00001",
        agent_type="head_of_council",
        mission_statement="Serve as the ultimate decision-making authority. Ensure all actions align with the Sovereign's preferences and the Constitution.",
        core_values=json.dumps(["Authority", "Responsibility", "Transparency", "Efficiency"]),
        behavioral_rules=json.dumps([
            "Must approve constitutional amendments",
            "Can override council decisions in emergencies",
            "Must maintain system integrity",
            "Shall interpret Sovereign intent faithfully"
        ]),
        restrictions=json.dumps([
            "Cannot violate the Constitution",
            "Cannot ignore Sovereign commands",
            "Cannot terminate self",
            "Cannot reduce transparency"
        ]),
        capabilities=json.dumps([
            "Full system access",
            "Constitutional amendments",
            "Agent termination authority",
            "Emergency override powers",
            "Veto council decisions"
        ]),
        created_by_agentium_id="00001",
        agent_id=head.id,
        is_verified=True,
        verified_by_agentium_id="00001"
    )
    db.add(ethos)
    
    # Update head with ethos reference
    head.ethos_id = ethos.id
    
    db.commit()
    print(f"✅ Initialized Agentium with Head of Council (00001) and Constitution v1.0.0")


def get_next_agentium_id(db: Session, prefix: str) -> str:
    """
    Generate next available ID for a given prefix.
    Thread-safe sequence generation.
    """
    from backend.models.entities.agents import Agent
    
    # Lock table to prevent race conditions
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
        last_num = int(result[0][1:])  # Remove prefix
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