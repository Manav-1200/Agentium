"""
Agent Orchestrator - Central routing and governance coordinator.
Enforces hierarchy (0xxxx→1xxxx→2xxxx→3xxxx) and integrates Vector DB context.
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.models.schemas.messages import AgentMessage, RouteResult
from backend.services.message_bus import MessageBus, get_message_bus, HierarchyValidator
from backend.core.vector_store import get_vector_store, VectorStore
from backend.models.entities.agents import Agent, AgentType
from backend.models.entities.audit import AuditLog, AuditLevel, AuditCategory


class AgentOrchestrator:
    """
    Central orchestrator for Agentium multi-agent governance.
    Handles intent processing, routing decisions, and context enrichment.
    """
    
    def __init__(self, db: Session, message_bus: Optional[MessageBus] = None):
        self.db = db
        self.message_bus = message_bus
        self.vector_store: Optional[VectorStore] = None
        self._routing_cache: Dict[str, datetime] = {}
    
    async def initialize(self):
        """Initialize orchestrator dependencies."""
        if self.message_bus is None:
            self.message_bus = await get_message_bus()
        self.vector_store = get_vector_store()
    
    async def process_intent(self, raw_input: str, source_id: str, target_id: Optional[str] = None) -> RouteResult:
        """
        Process intent and route to appropriate agent.
        Auto-determines direction based on hierarchy.
        """
        start = datetime.utcnow()
        
        # Validate source
        source = self._get_agent(source_id)
        if not source:
            return RouteResult(success=False, message_id="", error=f"Agent {source_id} not found")
        
        # Determine target
        recipient = target_id or self._get_parent_id(source_id)
        direction = self._get_direction(source_id, recipient)
        
        # Create message
        msg = AgentMessage(
            sender_id=source_id,
            recipient_id=recipient,
            content=raw_input,
            message_type="intent",
            route_direction=direction
        )
        
        # Validate hierarchy
        if not HierarchyValidator.can_route(source_id, recipient, direction):
            await self._log(source_id, "routing_violation", f"Attempted {direction} to {recipient}", AuditLevel.WARNING)
            return RouteResult(success=False, message_id=msg.message_id, error="Hierarchy violation")
        
        # Enrich and route
        msg = await self.enrich_with_context(msg)
        
        if direction == "up":
            result = await self.message_bus.route_up(msg)
        elif direction == "down":
            result = await self.message_bus.route_down(msg)
        else:
            result = await self.message_bus.publish(msg)
        
        result.latency_ms = (datetime.utcnow() - start).total_seconds() * 1000
        return result
    
    async def escalate_to_council(self, issue: str, reporter_id: str) -> RouteResult:
        """Escalate issue to Council tier (1xxxx)."""
        msg = AgentMessage(
            sender_id=reporter_id,
            recipient_id="",
            message_type="escalation",
            content=issue,
            priority="high"
        )
        
        # Enrich with constitution
        if self.vector_store:
            articles = self.vector_store.query_constitution(issue, n_results=3)
            msg.constitutional_basis = articles.get("documents", [[]])[0]
        
        return await self.message_bus.route_up(msg, auto_find_parent=True)
    
    async def delegate_to_task(self, task: Dict, lead_id: str, task_id: Optional[str] = None) -> RouteResult:
        """Delegate from Lead (2xxxx) to Task (3xxxx)."""
        if not task_id:
            task_id = await self._find_available_task(lead_id)
        
        if not task_id:
            return RouteResult(success=False, message_id="", error="No Task Agent available")
        
        msg = AgentMessage(
            sender_id=lead_id,
            recipient_id=task_id,
            message_type="delegation",
            content=task.get("description", ""),
            payload=task,
            route_direction="down"
        )
        
        # Enrich with patterns
        if self.vector_store:
            patterns = self.vector_store.get_collection("task_patterns").query(
                query_texts=[task.get("description", "")],
                n_results=3
            )
            msg.rag_context = {"patterns": patterns}
        
        return await self.message_bus.route_down(msg)
    
    async def enrich_with_context(self, msg: AgentMessage) -> AgentMessage:
        """Inject Vector DB context before routing."""
        if not self.vector_store:
            return msg
        
        agent_type = self._get_type(msg.sender_id)
        ctx = self.vector_store.query_hierarchical_context(
            agent_type=agent_type,
            task_description=msg.content,
            n_results=5
        )
        
        const = self.vector_store.query_constitution(msg.content, n_results=2)
        msg.rag_context = {
            "hierarchy": ctx,
            "constitution": const,
            "timestamp": datetime.utcnow().isoformat()
        }
        return msg
    
    async def check_permission(self, from_id: str, to_id: str) -> bool:
        """Validate routing permission."""
        return HierarchyValidator.can_route(from_id, to_id, self._get_direction(from_id, to_id))
    
    def _get_agent(self, agent_id: str) -> Optional[Agent]:
        """Query agent from DB (cacheable in production)."""
        return self.db.query(Agent).filter_by(agentium_id=agent_id, is_active='Y').first()
    
    def _get_parent_id(self, agent_id: str) -> str:
        """Get parent agent ID from DB."""
        agent = self._get_agent(agent_id)
        if agent and agent.parent:
            return agent.parent.agentium_id
        # Return generic tier target if no specific parent
        tier = HierarchyValidator.get_tier(agent_id)
        parents = {3: "2xxxx", 2: "1xxxx", 1: "00001"}
        return parents.get(tier, "00001")
    
    def _get_direction(self, from_id: str, to_id: str) -> str:
        """Determine routing direction."""
        from_tier = HierarchyValidator.get_tier(from_id)
        to_tier = HierarchyValidator.get_tier(to_id)
        
        if to_id == "broadcast":
            return "broadcast"
        if to_tier < from_tier:
            return "up"
        if to_tier > from_tier:
            return "down"
        return "lateral"
    
    def _get_type(self, agent_id: str) -> str:
        """Map ID prefix to agent type string."""
        return {'0': 'head', '1': 'council', '2': 'lead', '3': 'task'}.get(agent_id[0], 'task')
    
    async def _find_available_task(self, lead_id: str) -> Optional[str]:
        """Find available Task Agent under Lead."""
        lead = self._get_agent(lead_id)
        if not lead:
            return None
        
        # Find subordinate Task Agent with ACTIVE status
        for sub in lead.subordinates:
            if sub.agent_type == AgentType.TASK_AGENT and sub.status.value == 'active':
                return sub.agentium_id
        return None
    
    async def _log(self, actor: str, action: str, desc: str, level=AuditLevel.INFO, target=None):
        """Write to audit log."""
        audit = AuditLog(
            level=level,
            category=AuditCategory.GOVERNANCE,
            actor_type="agent",
            actor_id=actor,
            action=action,
            target_type="agent",
            target_id=target or "",
            description=desc
        )
        self.db.add(audit)
        self.db.commit()