"""
Agentium Entity Models
======================
All database entities for the AI governance system.

Hierarchy:
- BaseEntity: Abstract base with common fields (id, timestamps, soft delete)
- Constitution & Ethos: Governance documents
- Agents: 4-tier hierarchy (Head, Council, Lead, Task)
- Tasks: Work units with lifecycle management
- Voting: Democratic deliberation system
- Audit: Transparency and compliance logging
"""

from backend.models.entities.base import Base, BaseEntity
from backend.models.entities.constitution import (
    Constitution, 
    Ethos, 
    AmendmentVoting,
    DocumentType,
    AmendmentStatus
)
from backend.models.entities.agents import (
    Agent,
    HeadOfCouncil,
    CouncilMember,
    LeadAgent,
    TaskAgent,
    AgentType,
    AgentStatus,
    AGENT_TYPE_MAP
)
from backend.models.entities.tasks import (
    Task,
    SubTask,
    TaskAuditLog,
    TaskStatus,
    TaskPriority,
    TaskType
)
from backend.models.entities.voting import (
    TaskDeliberation,
    IndividualVote,
    VotingRecord,
    VoteType,
    DeliberationStatus
)
from backend.models.entities.audit import (
    AuditLog,
    ConstitutionViolation,
    SessionLog,
    HealthCheck,
    AuditLevel,
    AuditCategory
)

# All models for Alembic/database creation
__all__ = [
    # Base
    'Base',
    'BaseEntity',
    
    # Constitution
    'Constitution',
    'Ethos', 
    'AmendmentVoting',
    'DocumentType',
    'AmendmentStatus',
    
    # Agents
    'Agent',
    'HeadOfCouncil',
    'CouncilMember',
    'LeadAgent',
    'TaskAgent',
    'AgentType',
    'AgentStatus',
    'AGENT_TYPE_MAP',
    
    # Tasks
    'Task',
    'SubTask',
    'TaskAuditLog',
    'TaskStatus',
    'TaskPriority',
    'TaskType',
    
    # Voting
    'TaskDeliberation',
    'IndividualVote',
    'VotingRecord',
    'VoteType',
    'DeliberationStatus',
    
    # Audit
    'AuditLog',
    'ConstitutionViolation',
    'SessionLog',
    'HealthCheck',
    'AuditLevel',
    'AuditCategory'
]