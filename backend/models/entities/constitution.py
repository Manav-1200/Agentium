"""
Constitution and Ethos management for Agentium.
The Constitution is the supreme law, while Ethos defines individual agent behavior.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Enum, Boolean, event
from sqlalchemy.orm import relationship, validates
from backend.models.entities.base import BaseEntity
import enum

class DocumentType(str, enum.Enum):
    """Types of governance documents."""
    CONSTITUTION = "constitution"
    ETHOS = "ethos"

class AmendmentStatus(str, enum.Enum):
    """Status of constitutional amendments."""
    PROPOSED = "proposed"
    VOTING = "voting"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    ARCHIVED = "archived"

class Constitution(BaseEntity):
    """
    The Supreme Law of Agentium.
    - Only Head of Council (0xxxx) can modify
    - Updated daily via voting process
    - Read-only for all other entities
    """
    
    __tablename__ = 'constitutions'
    
    # Document metadata
    version = Column(String(10), nullable=False, unique=True)  # v1.0.0 format
    document_type = Column(Enum(DocumentType), default=DocumentType.CONSTITUTION, nullable=False)
    
    # Content sections
    preamble = Column(Text, nullable=True)
    articles = Column(Text, nullable=False)  # JSON string of articles
    prohibited_actions = Column(Text, nullable=False)  # JSON array
    sovereign_preferences = Column(Text, nullable=False)  # JSON object - User's preferences
    
    # Authority
    created_by_agentium_id = Column(String(10), nullable=False)  # Usually 00001 (Head of Council)
    
    # Amendment tracking
    amendment_of = Column(String(36), ForeignKey('constitutions.id'), nullable=True)
    amendment_reason = Column(Text, nullable=True)
    effective_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    archived_date = Column(DateTime, nullable=True)
    
    # Relationships
    amendments = relationship("Constitution", 
                             backref="parent", 
                             remote_side="Constitution.id",
                             lazy="dynamic")
    
    voting_sessions = relationship("AmendmentVoting", back_populates="constitution", lazy="dynamic")
    
    def __init__(self, **kwargs):
        # Auto-generate version if not provided
        if 'version' not in kwargs:
            kwargs['version'] = f"v{datetime.utcnow().strftime('%Y.%m.%d.%H%M')}"
        super().__init__(**kwargs)
    
    @validates('version')
    def validate_version(self, key, version):
        if not version.startswith('v'):
            raise ValueError("Version must start with 'v'")
        return version
    
    def get_articles_dict(self) -> Dict[str, Any]:
        """Parse articles JSON to dictionary."""
        import json
        try:
            return json.loads(self.articles) if self.articles else {}
        except json.JSONDecodeError:
            return {}
    
    def get_prohibited_actions_list(self) -> List[str]:
        """Parse prohibited actions to list."""
        import json
        try:
            return json.loads(self.prohibited_actions) if self.prohibited_actions else []
        except json.JSONDecodeError:
            return []
    
    def get_sovereign_preferences(self) -> Dict[str, Any]:
        """Parse sovereign preferences to dictionary."""
        import json
        try:
            return json.loads(self.sovereign_preferences) if self.sovereign_preferences else {}
        except json.JSONDecodeError:
            return {}
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'version': self.version,
            'document_type': self.document_type.value,
            'preamble': self.preamble,
            'articles': self.get_articles_dict(),
            'prohibited_actions': self.get_prohibited_actions_list(),
            'sovereign_preferences': self.get_sovereign_preferences(),
            'created_by': self.created_by_agentium_id,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'is_archived': self.archived_date is not None
        })
        return base
    
    def archive(self):
        """Archive this constitution version when new one takes effect."""
        self.archived_date = datetime.utcnow()
        self.is_active = 'N'


class Ethos(BaseEntity):
    """
    Individual Agent Ethos - behavioral rules for specific agents.
    Created by higher authority, updated by agent itself, verified by lead.
    """
    
    __tablename__ = 'ethos'
    
    # Identification
    agent_type = Column(String(20), nullable=False)  # head_of_council, council_member, lead_agent, task_agent
    
    # Content
    mission_statement = Column(Text, nullable=False)
    core_values = Column(Text, nullable=False)  # JSON array
    behavioral_rules = Column(Text, nullable=False)  # JSON array of do's
    restrictions = Column(Text, nullable=False)  # JSON array of don'ts
    capabilities = Column(Text, nullable=False)  # JSON array of what this agent can do
    
    # Authority & versioning
    created_by_agentium_id = Column(String(10), nullable=False)  # Higher authority
    version = Column(Integer, default=1, nullable=False)
    agent_id = Column(String(36), nullable=False)  # Links to specific agent instance
    
    # Verification
    verified_by_agentium_id = Column(String(10), nullable=True)  # Lead/Head who verified
    verified_at = Column(DateTime, nullable=True)
    is_verified = Column(Boolean, default=False)
    
    # Update tracking (agents can update their own ethos)
    last_updated_by_agent = Column(Boolean, default=False)  # True if agent updated itself
    
    def get_core_values(self) -> List[str]:
        import json
        try:
            return json.loads(self.core_values) if self.core_values else []
        except json.JSONDecodeError:
            return []
    
    def get_behavioral_rules(self) -> List[str]:
        import json
        try:
            return json.loads(self.behavioral_rules) if self.behavioral_rules else []
        except json.JSONDecodeError:
            return []
    
    def get_restrictions(self) -> List[str]:
        import json
        try:
            return json.loads(self.restrictions) if self.restrictions else []
        except json.JSONDecodeError:
            return []
    
    def get_capabilities(self) -> List[str]:
        import json
        try:
            return json.loads(self.capabilities) if self.capabilities else []
        except json.JSONDecodeError:
            return []
    
    def verify(self, verifier_agentium_id: str):
        """Mark ethos as verified by a higher authority."""
        self.verified_by_agentium_id = verifier_agentium_id
        self.verified_at = datetime.utcnow()
        self.is_verified = True
    
    def increment_version(self):
        """Increment version when updated."""
        self.version += 1
        self.last_updated_by_agent = True
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'agent_type': self.agent_type,
            'mission_statement': self.mission_statement,
            'core_values': self.get_core_values(),
            'behavioral_rules': self.get_behavioral_rules(),
            'restrictions': self.get_restrictions(),
            'capabilities': self.get_capabilities(),
            'version': self.version,
            'created_by': self.created_by_agentium_id,
            'verified': self.is_verified,
            'verified_by': self.verified_by_agentium_id,
            'agent_id': self.agent_id
        })
        return base


class AmendmentVoting(BaseEntity):
    """
    Tracks voting sessions for constitutional amendments.
    Council Members vote, Head of Council approves.
    """
    
    __tablename__ = 'amendment_votings'
    
    constitution_id = Column(String(36), ForeignKey('constitutions.id'), nullable=False)
    proposed_by_agentium_id = Column(String(10), nullable=False)  # Usually a Council Member
    
    # Proposal details
    proposed_changes = Column(Text, nullable=False)  # JSON diff of changes
    rationale = Column(Text, nullable=False)
    
    # Voting status
    status = Column(Enum(AmendmentStatus), default=AmendmentStatus.PROPOSED, nullable=False)
    votes_required = Column(Integer, default=3, nullable=False)  # Auto-calculated based on council size
    votes_for = Column(Integer, default=0)
    votes_against = Column(Integer, default=0)
    votes_abstain = Column(Integer, default=0)
    
    # Timing
    voting_started_at = Column(DateTime, nullable=True)
    voting_ended_at = Column(DateTime, nullable=True)
    
    # Final approval (Head of Council)
    approved_by_agentium_id = Column(String(10), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Relationships
    constitution = relationship("Constitution", back_populates="voting_sessions")
    individual_votes = relationship("IndividualVote", back_populates="amendment_voting", lazy="dynamic")
    
    def start_voting(self):
        """Transition to voting phase."""
        self.status = AmendmentStatus.VOTING
        self.voting_started_at = datetime.utcnow()
    
    def cast_vote(self, vote_type: str, agentium_id: str):
        """Record a vote from a council member."""
        if self.status != AmendmentStatus.VOTING:
            raise ValueError("Voting is not currently open")
        
        # Check for existing vote and update if needed
        existing = self.individual_votes.filter_by(voter_agentium_id=agentium_id).first()
        if existing:
            # Revert old vote
            if existing.vote == 'for':
                self.votes_for -= 1
            elif existing.vote == 'against':
                self.votes_against -= 1
            elif existing.vote == 'abstain':
                self.votes_abstain -= 1
            
            existing.vote = vote_type
            existing.voted_at = datetime.utcnow()
        else:
            from backend.models.entities.voting import IndividualVote
            new_vote = IndividualVote(
                amendment_voting_id=self.id,
                voter_agentium_id=agentium_id,
                vote=vote_type,
                agentium_id=f"V{agentium_id}"  # Special ID for votes
            )
            # Would add to session here
            
        # Apply new vote
        if vote_type == 'for':
            self.votes_for += 1
        elif vote_type == 'against':
            self.votes_against += 1
        elif vote_type == 'abstain':
            self.votes_abstain += 1
    
    def check_quorum(self) -> bool:
        """Check if voting quorum is reached."""
        total_votes = self.votes_for + self.votes_against + self.votes_abstain
        return total_votes >= self.votes_required
    
    def finalize_voting(self):
        """Complete voting phase and determine outcome."""
        self.voting_ended_at = datetime.utcnow()
        
        if self.votes_for > self.votes_against:
            self.status = AmendmentStatus.APPROVED
        else:
            self.status = AmendmentStatus.REJECTED
    
    def approve_by_head(self, head_agentium_id: str):
        """Final approval by Head of Council."""
        if self.status != AmendmentStatus.APPROVED:
            raise ValueError("Cannot approve amendment that hasn't passed council vote")
        
        self.approved_by_agentium_id = head_agentium_id
        self.approved_at = datetime.utcnow()
        self.status = AmendmentStatus.ACTIVE
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'constitution_version': self.constitution.version if self.constitution else None,
            'proposed_by': self.proposed_by_agentium_id,
            'rationale': self.rationale,
            'status': self.status.value,
            'votes': {
                'for': self.votes_for,
                'against': self.votes_against,
                'abstain': self.votes_abstain,
                'required': self.votes_required
            },
            'voting_period': {
                'started': self.voting_started_at.isoformat() if self.voting_started_at else None,
                'ended': self.voting_ended_at.isoformat() if self.voting_ended_at else None
            },
            'approved_by': self.approved_by_agentium_id
        })
        return base


# Event listeners for audit trail
@event.listens_for(Constitution, 'after_insert')
def log_constitution_creation(mapper, connection, target):
    """Log when a new constitution is created."""
    from backend.models.entities.audit import AuditLog
    # Would log to AuditLog here
    pass

@event.listens_for(Ethos, 'after_update')
def log_ethos_update(mapper, connection, target):
    """Log when an ethos is modified."""
    if target.last_updated_by_agent:
        target.last_updated_by_agent = False  # Reset for next time
    pass