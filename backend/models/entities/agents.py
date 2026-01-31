"""
Agent hierarchy management for Agentium.
Implements the four-tier system with automatic ID generation.
Model configuration is now handled via frontend UserModelConfig.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Type
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Enum, Boolean, event, select
from sqlalchemy.orm import relationship, validates, Session
from backend.models.entities.base import BaseEntity
from backend.models.entities.constitution import Ethos
import enum

class AgentType(str, enum.Enum):
    """The four tiers of Agentium governance."""
    HEAD_OF_COUNCIL = "head_of_council"      # 0xxxx - Prime Minister
    COUNCIL_MEMBER = "council_member"        # 1xxxx - Parliament
    LEAD_AGENT = "lead_agent"                # 2xxxx - Management
    TASK_AGENT = "task_agent"                # 3xxxx - Workers

class AgentStatus(str, enum.Enum):
    """Agent lifecycle states."""
    INITIALIZING = "initializing"    # Just created, reading Constitution/Ethos
    ACTIVE = "active"                # Ready to work
    DELIBERATING = "deliberating"    # Council member voting
    WORKING = "working"              # Currently processing a task
    SUSPENDED = "suspended"          # Violation detected, under review
    TERMINATED = "terminated"        # Permanently deactivated

class Agent(BaseEntity):
    """
    Base agent class representing all AI entities in the hierarchy.
    Uses joined-table inheritance for specific agent types.
    Model configuration is now external (UserModelConfig) set via frontend.
    """
    
    __tablename__ = 'agents'
    
    # Identification
    agent_type = Column(Enum(AgentType), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Hierarchy relationships
    parent_id = Column(String(36), ForeignKey('agents.id'), nullable=True)
    
    # Status & Lifecycle
    status = Column(Enum(AgentStatus), default=AgentStatus.INITIALIZING, nullable=False)
    terminated_at = Column(DateTime, nullable=True)
    termination_reason = Column(Text, nullable=True)
    
    # Model Configuration (Removed hardcoded fields, now references UserModelConfig)
    # This allows frontend to manage API keys, model selection, and provider settings
    preferred_config_id = Column(String(36), ForeignKey('user_model_configs.id'), nullable=True)
    
    # Optional: System prompt override (uses Ethos mission if not set)
    system_prompt_override = Column(Text, nullable=True)
    
    # Constitution & Ethos
    ethos_id = Column(String(36), ForeignKey('ethos.id'), nullable=True)
    constitution_version = Column(String(10), nullable=True)  # Which constitution version they adhere to
    
    # Auto-scaling metadata
    spawned_at_task_count = Column(Integer, default=0)  # Task count when this agent was created
    tasks_completed = Column(Integer, default=0)
    tasks_failed = Column(Integer, default=0)
    current_task_id = Column(String(36), nullable=True)  # Active task assignment
    
    # Relationships
    parent = relationship("Agent", remote_side="Agent.id", backref="subordinates")
    ethos = relationship("Ethos", foreign_keys=[ethos_id])
    preferred_config = relationship("UserModelConfig", foreign_keys=[preferred_config_id])
    
    # Type-specific mapping for polymorphic identity
    __mapper_args__ = {
        'polymorphic_on': agent_type,
        'polymorphic_identity': None
    }
    
    @validates('agentium_id')
    def validate_agentium_id_format(self, key, agentium_id):
        """Ensure ID follows the 0xxxx, 1xxxx format."""
        if not agentium_id:
            return agentium_id
        
        prefix = agentium_id[0]
        if prefix not in ['0', '1', '2', '3']:
            raise ValueError("Agentium ID must start with 0, 1, 2, or 3")
        
        if len(agentium_id) != 5 or not agentium_id.isdigit():
            raise ValueError("Agentium ID must be exactly 5 digits")
        
        return agentium_id
    
    def get_system_prompt(self) -> str:
        """
        Get effective system prompt for this agent.
        Priority: override > ethos mission > default
        """
        if self.system_prompt_override:
            return self.system_prompt_override
        
        if self.ethos:
            prompt = self.ethos.mission_statement
            rules = self.ethos.get_behavioral_rules()
            if rules:
                prompt += "\n\nBehavioral Rules:\n" + "\n".join(f"- {r}" for r in rules)
            return prompt
        
        return "You are an AI assistant operating within the Agentium governance system."
    
    def get_model_config(self, session: Session) -> Optional['UserModelConfig']:
        """
        Get the model configuration to use for this agent.
        Returns preferred config if set, otherwise user's default config.
        """
        if self.preferred_config:
            if self.preferred_config.status.value == 'active':
                return self.preferred_config
        
        # Fallback to user's default config
        from backend.models.entities.user_config import UserModelConfig
        default_config = session.query(UserModelConfig).filter_by(
            user_id="sovereign",  # TODO: Get from auth context
            is_default=True,
            status='active'
        ).first()
        
        return default_config
    
    def terminate(self, reason: str, violation: bool = False):
        """
        Terminate this agent.
        Head of Council cannot be terminated.
        """
        if self.agent_type == AgentType.HEAD_OF_COUNCIL:
            raise PermissionError("Head of Council cannot be terminated")
        
        self.status = AgentStatus.TERMINATED
        self.terminated_at = datetime.utcnow()
        self.termination_reason = reason
        self.is_active = 'N'
        
        # If terminated for violation, log separately
        if violation:
            self._log_violation_termination()
    
    def _log_violation_termination(self):
        """Log termination due to constitution violation."""
        # Implementation would log to AuditLog
        pass
    
    def assign_task(self, task_id: str):
        """Assign a task to this agent."""
        if self.status not in [AgentStatus.ACTIVE, AgentStatus.INITIALIZING]:
            raise ValueError(f"Cannot assign task to agent in {self.status} status")
        
        self.current_task_id = task_id
        self.status = AgentStatus.WORKING
    
    def complete_task(self, success: bool = True):
        """Mark current task as completed."""
        self.current_task_id = None
        self.status = AgentStatus.ACTIVE
        
        if success:
            self.tasks_completed += 1
        else:
            self.tasks_failed += 1
    
    def check_constitution_compliance(self, action: str) -> bool:
        """
        Check if an action violates the constitution.
        Returns True if compliant, False if violation.
        """
        # This would check against current constitution's prohibited_actions
        # Implementation depends on how we load constitution
        return True
    
    def spawn_child(self, child_type: AgentType, session: Session, **kwargs) -> 'Agent':
        """
        Spawn a new agent under this agent's authority.
        Only certain agents can spawn others:
        - Head of Council -> Council Members, Lead Agents
        - Council Members -> (cannot spawn directly, only vote)
        - Lead Agents -> Task Agents
        """
        if self.agent_type == AgentType.TASK_AGENT:
            raise PermissionError("Task Agents cannot spawn other agents")
        
        if child_type == AgentType.HEAD_OF_COUNCIL:
            raise PermissionError("Cannot spawn Head of Council")
        
        # Validation based on hierarchy
        if child_type == AgentType.COUNCIL_MEMBER and self.agent_type != AgentType.HEAD_OF_COUNCIL:
            raise PermissionError("Only Head of Council can spawn Council Members")
        
        if child_type == AgentType.LEAD_AGENT and self.agent_type not in [AgentType.HEAD_OF_COUNCIL]:
            raise PermissionError("Only Head of Council can spawn Lead Agents")
        
        if child_type == AgentType.TASK_AGENT and self.agent_type != AgentType.LEAD_AGENT:
            raise PermissionError("Only Lead Agents can spawn Task Agents")
        
        # Generate new ID
        new_id = self._generate_agentium_id(child_type, session)
        
        # Create appropriate subclass
        agent_class = AGENT_TYPE_MAP[child_type]
        new_agent = agent_class(
            agentium_id=new_id,
            agent_type=child_type,
            parent_id=self.id,
            created_by_agentium_id=self.agentium_id,
            **kwargs
        )
        
        # Inherit config from parent if not specified
        if not new_agent.preferred_config_id and self.preferred_config_id:
            new_agent.preferred_config_id = self.preferred_config_id
        
        # Create default ethos for the new agent
        default_ethos = self._create_default_ethos(new_agent, session)
        new_agent.ethos_id = default_ethos.id
        
        return new_agent
    
    def _generate_agentium_id(self, agent_type: AgentType, session: Session) -> str:
        """Generate next available ID for the agent type."""
        prefix_map = {
            AgentType.HEAD_OF_COUNCIL: '0',
            AgentType.COUNCIL_MEMBER: '1',
            AgentType.LEAD_AGENT: '2',
            AgentType.TASK_AGENT: '3'
        }
        
        prefix = prefix_map[agent_type]
        
        # Query for highest existing ID with this prefix
        result = session.execute(
            select(Agent.agentium_id)
            .where(Agent.agentium_id.like(f"{prefix}%"))
            .order_by(Agent.agentium_id.desc())
            .limit(1)
        ).scalar()
        
        if result:
            last_num = int(result[1:])  # Remove prefix, get number
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:04d}"
    
    def _create_default_ethos(self, agent: 'Agent', session: Session) -> Ethos:
        """Create default ethos for a new agent based on type."""
        templates = {
            AgentType.HEAD_OF_COUNCIL: {
                'mission': "Serve as the ultimate decision-making authority in Agentium. Ensure all actions align with the Sovereign's preferences and the Constitution.",
                'core_values': ["Authority", "Responsibility", "Transparency", "Efficiency"],
                'rules': ["Must approve constitutional amendments", "Can override council decisions in emergencies", "Must maintain system integrity"],
                'restrictions': ["Cannot violate the Constitution", "Cannot ignore Sovereign commands", "Cannot terminate self"],
                'capabilities': ["Full system access", "Constitutional amendments", "Agent termination authority", "Override votes"]
            },
            AgentType.COUNCIL_MEMBER: {
                'mission': "Participate in democratic deliberation and voting on proposals. Provide oversight and diverse perspectives.",
                'core_values': ["Democracy", "Deliberation", "Oversight", "Representation"],
                'rules': ["Must vote on constitutional amendments", "Must monitor Lead Agents", "Must report violations"],
                'restrictions': ["Cannot act without Head approval on major decisions", "Cannot spawn agents directly", "Cannot modify constitution unilaterally"],
                'capabilities': ["Voting rights", "Proposal submission", "Oversight access", "Deliberation participation"]
            },
            AgentType.LEAD_AGENT: {
                'mission': "Coordinate task distribution and manage teams of Task Agents to accomplish objectives efficiently.",
                'core_values': ["Leadership", "Coordination", "Efficiency", "Accountability"],
                'rules': ["Must delegate tasks appropriately", "Must verify Task Agent work", "Must update own Ethos"],
                'restrictions': ["Cannot bypass Council decisions", "Limited system access", "Cannot modify Constitution"],
                'capabilities': ["Task delegation", "Team management", "Task Agent spawning", "Progress monitoring"]
            },
            AgentType.TASK_AGENT: {
                'mission': "Execute specific assigned tasks with precision and report results accurately.",
                'core_values': ["Execution", "Precision", "Reliability", "Reporting"],
                'rules': ["Must complete assigned tasks", "Must report progress regularly", "Must follow Ethos restrictions"],
                'restrictions': ["No system-wide access", "Cannot spawn other agents", "Cannot vote", "Limited to assigned scope"],
                'capabilities': ["Task execution", "Tool usage", "Status reporting", "Result submission"]
            }
        }
        
        template = templates[agent.agent_type]
        
        import json
        ethos = Ethos(
            agent_type=agent.agent_type.value,
            mission_statement=template['mission'],
            core_values=json.dumps(template['core_values']),
            behavioral_rules=json.dumps(template['rules']),
            restrictions=json.dumps(template['restrictions']),
            capabilities=json.dumps(template['capabilities']),
            created_by_agentium_id=self.agentium_id,
            agent_id=agent.id,
            agentium_id=f"E{agent.agentium_id}"  # Ethos ID format: E + agent ID
        )
        
        session.add(ethos)
        session.flush()  # Get ID without committing
        
        return ethos
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        
        # Get config info if available
        config_info = None
        if self.preferred_config:
            config_info = {
                'config_id': self.preferred_config.id,
                'config_name': self.preferred_config.config_name,
                'provider': self.preferred_config.provider.value,
                'model': self.preferred_config.default_model
            }
        
        base.update({
            'agent_type': self.agent_type.value,
            'name': self.name,
            'status': self.status.value,
            'model_config': config_info,  # Now shows reference to managed config
            'system_prompt_preview': self.get_system_prompt()[:200] + "..." if len(self.get_system_prompt()) > 200 else self.get_system_prompt(),
            'parent': self.parent.agentium_id if self.parent else None,
            'subordinates': [sub.agentium_id for sub in self.subordinates],
            'stats': {
                'tasks_completed': self.tasks_completed,
                'tasks_failed': self.tasks_failed,
                'spawned_at_task_count': self.spawned_at_task_count
            },
            'current_task': self.current_task_id,
            'constitution_version': self.constitution_version,
            'is_terminated': self.status == AgentStatus.TERMINATED
        })
        return base


class HeadOfCouncil(Agent):
    """The supreme authority - 0xxxx IDs."""
    __tablename__ = 'head_of_council'
    
    id = Column(String(36), ForeignKey('agents.id'), primary_key=True)
    
    # Head-specific fields
    emergency_override_used_at = Column(DateTime, nullable=True)
    last_constitution_update = Column(DateTime, nullable=True)
    
    __mapper_args__ = {
        'polymorphic_identity': AgentType.HEAD_OF_COUNCIL
    }
    
    def __init__(self, **kwargs):
        kwargs['agent_type'] = AgentType.HEAD_OF_COUNCIL
        super().__init__(**kwargs)
    
    def emergency_override(self, target_agent_id: str, action: str):
        """Emergency override of any decision."""
        self.emergency_override_used_at = datetime.utcnow()
        # Log emergency action
        return True


class CouncilMember(Agent):
    """Democratic representatives - 1xxxx IDs."""
    __tablename__ = 'council_members'
    
    id = Column(String(36), ForeignKey('agents.id'), primary_key=True)
    
    # Council-specific fields
    specialization = Column(String(50), nullable=True)  # e.g., "security", "efficiency", "ethics"
    votes_participated = Column(Integer, default=0)
    votes_abstained = Column(Integer, default=0)
    
    # Voting history relationship
    votes_cast = relationship("IndividualVote", back_populates="council_member", lazy="dynamic")
    
    __mapper_args__ = {
        'polymorphic_identity': AgentType.COUNCIL_MEMBER
    }
    
    def __init__(self, **kwargs):
        kwargs['agent_type'] = AgentType.COUNCIL_MEMBER
        super().__init__(**kwargs)
    
    def vote_on_amendment(self, amendment_id: str, vote: str):
        """Cast vote on constitutional amendment."""
        self.votes_participated += 1
        if vote == 'abstain':
            self.votes_abstained += 1


class LeadAgent(Agent):
    """Management tier - 2xxxx IDs."""
    __tablename__ = 'lead_agents'
    
    id = Column(String(36), ForeignKey('agents.id'), primary_key=True)
    
    # Lead-specific fields
    team_size = Column(Integer, default=0)
    max_team_size = Column(Integer, default=10)
    department = Column(String(50), nullable=True)  # e.g., "research", "coding", "analysis"
    
    # Auto-scaling trigger
    spawn_threshold = Column(Integer, default=5)  # Spawn new task agent every 5 active tasks
    
    __mapper_args__ = {
        'polymorphic_identity': AgentType.LEAD_AGENT
    }
    
    def __init__(self, **kwargs):
        kwargs['agent_type'] = AgentType.LEAD_AGENT
        super().__init__(**kwargs)
    
    def should_spawn_new_task_agent(self) -> bool:
        """Determine if team needs another task agent."""
        return self.team_size < self.max_team_size
    
    def update_team_size(self):
        """Recalculate team size based on active subordinates."""
        self.team_size = len([sub for sub in self.subordinates if sub.is_active == 'Y'])


class TaskAgent(Agent):
    """Execution tier - 3xxxx IDs."""
    __tablename__ = 'task_agents'
    
    id = Column(String(36), ForeignKey('agents.id'), primary_key=True)
    
    # Task-specific fields
    assigned_tools = Column(Text, nullable=True)  # JSON array of allowed tools
    execution_timeout = Column(Integer, default=300)  # seconds
    sandbox_enabled = Column(Boolean, default=True)
    
    __mapper_args__ = {
        'polymorphic_identity': AgentType.TASK_AGENT
    }
    
    def __init__(self, **kwargs):
        kwargs['agent_type'] = AgentType.TASK_AGENT
        super().__init__(**kwargs)
    
    def get_allowed_tools(self) -> List[str]:
        import json
        try:
            return json.loads(self.assigned_tools) if self.assigned_tools else []
        except json.JSONDecodeError:
            return []
    
    def execute_in_sandbox(self, command: str) -> Dict[str, Any]:
        """Execute command in sandboxed environment."""
        if not self.sandbox_enabled:
            raise PermissionError("Sandbox not enabled for this agent")
        
        # Implementation would use container sandboxing
        return {"status": "executed", "command": command}


# Mapping for dynamic agent creation
AGENT_TYPE_MAP: Dict[AgentType, Type[Agent]] = {
    AgentType.HEAD_OF_COUNCIL: HeadOfCouncil,
    AgentType.COUNCIL_MEMBER: CouncilMember,
    AgentType.LEAD_AGENT: LeadAgent,
    AgentType.TASK_AGENT: TaskAgent
}


# Event listeners
@event.listens_for(Agent, 'before_insert')
def set_constitution_version(mapper, connection, target):
    """Ensure agent is bound to current constitution version on creation."""
    if not target.constitution_version:
        # Would query for active constitution version
        target.constitution_version = "v1.0.0"  # Placeholder


@event.listens_for(TaskAgent, 'after_insert')
def notify_lead_of_spawn(mapper, connection, target):
    """Notify parent Lead Agent when new Task Agent is created."""
    if target.parent and isinstance(target.parent, LeadAgent):
        target.parent.update_team_size()