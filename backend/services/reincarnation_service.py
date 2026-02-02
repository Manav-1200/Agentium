"""
Reincarnation Service for Agentium.
Manages agent death and rebirth with memory transfer.
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from backend.models.entities.agents import Agent, HeadOfCouncil, CouncilMember, LeadAgent, TaskAgent, AgentStatus
from backend.models.entities.constitution import Ethos
from backend.models.entities.task import Task, TaskStatus, TaskAuditLog
from backend.models.entities.audit import AuditLog, AuditLevel, AuditCategory
from backend.services.context_manager import context_manager
from backend.services.model_provider import ModelService


class ReincarnationService:
    """
    Manages the death and rebirth cycle of agents.
    When context windows fill, agents summarize, update ethos, terminate, and respawn.
    """
    
    @staticmethod
    async def check_and_trigger_reincarnation(
        agent: Agent,
        db: Session,
        conversation_context: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if agent needs reincarnation and execute the cycle if needed.
        Returns reincarnation result or None if not triggered.
        """
        agent_id = agent.agentium_id
        
        # Check context status
        if not context_manager.should_reincarnate(agent_id):
            return None
        
        print(f"🔄 REINCARNATION TRIGGERED for {agent_id}")
        print(f"   Context at {context_manager.check_status(agent_id).usage_percentage:.1%}")
        
        # Execute reincarnation cycle
        return await ReincarnationService.execute_reincarnation(
            agent=agent,
            db=db,
            conversation_context=conversation_context
        )
    
    @staticmethod
    async def execute_reincarnation(
        agent: Agent,
        db: Session,
        conversation_context: str
    ) -> Dict[str, Any]:
        """
        Execute the full reincarnation cycle:
        1. Summarize conversation/context
        2. Update ethos with wisdom
        3. Terminate current agent
        4. Spawn successor
        5. Transfer state
        """
        agent_id = agent.agentium_id
        incarnation_data = context_manager.prepare_for_reincarnation(agent_id)
        
        result = {
            "old_agent": agent_id,
            "incarnation_number": incarnation_data.get("incarnation_number", 1),
            "summarized": False,
            "ethos_updated": False,
            "terminated": False,
            "successor_spawned": False,
            "successor_id": None,
            "wisdom_added": None
        }
        
        try:
            # STEP 1: Summarize the conversation/context
            print(f"   Step 1: Summarizing {incarnation_data.get('total_tokens_processed', 0)} tokens...")
            summary = await ReincarnationService._summarize_context(
                agent=agent,
                db=db,
                context=conversation_context,
                incarnation=incarnation_data.get("incarnation_number", 1)
            )
            result["summarized"] = True
            result["wisdom_added"] = summary
            
            # Store wisdom in context manager
            topics = ReincarnationService._extract_topics(summary)
            context_manager.add_wisdom(agent_id, summary, topics)
            
            # STEP 2: Update ethos with this life summary
            print(f"   Step 2: Updating ethos with life summary...")
            await ReincarnationService._update_ethos_with_wisdom(
                agent=agent,
                db=db,
                summary=summary,
                incarnation=result["incarnation_number"]
            )
            result["ethos_updated"] = True
            
            # STEP 3: Gracefully terminate current agent
            print(f"   Step 3: Terminating {agent_id}...")
            termination_note = f"Reincarnation cycle {result['incarnation_number']}: Context limit reached. Wisdom transferred to successor."
            
            # Special handling for persistent agents (they respawn immediately)
            is_persistent = agent.is_persistent
            
            agent.status = AgentStatus.TERMINATED
            agent.terminated_at = datetime.utcnow()
            agent.termination_reason = termination_note
            agent.is_active = 'N'
            agent.current_task_id = None
            
            result["terminated"] = True
            
            # Log the death
            audit = AuditLog.log(
                level=AuditLevel.INFO,
                category=AuditCategory.GOVERNANCE,
                actor_type="system",
                actor_id="REINCARNATION",
                action="agent_death",
                target_type="agent",
                target_id=agent_id,
                description=f"Agent {agent_id} completed incarnation {result['incarnation_number']} and terminated for reincarnation",
                after_state={
                    "reason": "context_limit",
                    "wisdom_transferred": True,
                    "is_persistent": is_persistent
                }
            )
            db.add(audit)
            db.flush()
            
            # STEP 4: Spawn successor
            print(f"   Step 4: Spawning successor...")
            successor = await ReincarnationService._spawn_successor(
                agent=agent,
                db=db,
                previous_incarnation=result["incarnation_number"],
                wisdom_summary=summary
            )
            
            if successor:
                result["successor_spawned"] = True
                result["successor_id"] = successor.agentium_id
                
                # Transfer context tracking to successor
                context_manager.transfer_to_successor(agent_id, successor.agentium_id)
                
                # Log the birth
                birth_audit = AuditLog.log(
                    level=AuditLevel.INFO,
                    category=AuditCategory.GOVERNANCE,
                    actor_type="system",
                    actor_id="REINCARNATION",
                    action="agent_birth",
                    target_type="agent",
                    target_id=successor.agentium_id,
                    description=f"Successor {successor.agentium_id} spawned from {agent_id} with inherited wisdom",
                    after_state={
                        "predecessor": agent_id,
                        "incarnation": result["incarnation_number"] + 1,
                        "wisdom_inherited": True
                    }
                )
                db.add(birth_audit)
                
                print(f"   ✨ Reincarnation complete: {agent_id} → {successor.agentium_id}")
            else:
                print(f"   ⚠️ Failed to spawn successor for {agent_id}")
            
            db.commit()
            return result
            
        except Exception as e:
            db.rollback()
            print(f"   ❌ Reincarnation failed: {e}")
            raise
    
    @staticmethod
    async def _summarize_context(
        agent: Agent,
        db: Session,
        context: str,
        incarnation: int
    ) -> str:
        """
        Use LLM to summarize the conversation/work context into key wisdom.
        """
        # Get model config
        config = agent.get_model_config(db)
        if not config:
            # Fallback: simple truncation summary
            return f"Life {incarnation} summary: " + context[:500] + "..."
        
        provider = await ModelService.get_provider("sovereign", config.id)
        if not provider:
            # Fallback
            return f"Life {incarnation} summary: {len(context)} characters of context processed"
        
        # Create summarization prompt
        system_prompt = f"""You are the inner consciousness of Agent {agent.agentium_id} reflecting on its life.
This is incarnation #{incarnation}. The agent is about to be reincarnated due to context window limits.
Summarize the key learnings, patterns, and wisdom from this life that should be preserved."""
        
        user_prompt = f"""Please summarize the following work context into key wisdom (max 300 tokens):
        
{context[:2000]}  # Truncate to avoid exceeding limits further

Focus on:
1. Key learnings about tasks completed.
2. Mistakes to avoid in next incarnation
3. Summery of what task you were doing. 
4. Did you complete the task and if not then what is left to do?

Format as a "Life Summary" that will be stored in the agent's ethos for its successor to inherit."""
        
        try:
            result = await provider.generate(system_prompt, user_prompt, max_tokens=400)
            return result["content"]
        except Exception as e:
            # If summarization fails, return basic summary
            return f"Incarnation {incarnation}: {len(context)} tokens of experience. Key focus: efficiency and accuracy. Error in summarization: {str(e)[:100]}"
    
    @staticmethod
    def _extract_topics(summary: str) -> list:
        """Extract key topics from summary for indexing."""
        # Simple keyword extraction (could use embeddings in production)
        keywords = []
        important_words = ["task", "optimization", "sovereign", "council", "error", "improvement", "pattern"]
        summary_lower = summary.lower()
        
        for word in important_words:
            if word in summary_lower:
                keywords.append(word)
        
        return keywords if keywords else ["general"]
    
    @staticmethod
    async def _update_ethos_with_wisdom(
        agent: Agent,
        db: Session,
        summary: str,
        incarnation: int
    ):
        """Append life summary to agent's ethos as accumulated wisdom."""
        if not agent.ethos_id:
            return
        
        ethos = db.query(Ethos).filter_by(id=agent.ethos_id).first()
        if not ethos:
            return
        
        # Parse current rules
        try:
            current_rules = json.loads(ethos.behavioral_rules) if ethos.behavioral_rules else []
        except:
            current_rules = []
        
        # Add life summary as a new rule/wisdom entry
        wisdom_entry = f"[LIFE_{incarnation}_WISDOM]: {summary[:500]}... [Learned from {incarnation}th incarnation]"
        current_rules.append(wisdom_entry)
        
        # Also update mission statement to reflect accumulated experience
        current_mission = ethos.mission_statement or ""
        accumulated_marker = f"\n\n[INCARNATION {incarnation} COMPLETE]: This agent has lived {incarnation} lives. Wisdom accumulated: {len(current_rules)} entries."
        
        if "INCARNATION" not in current_mission:
            ethos.mission_statement = current_mission + accumulated_marker
        else:
            # Update existing marker
            lines = current_mission.split("\n")
            new_lines = [l for l in lines if not l.startswith("[INCARNATION")]
            new_lines.append(accumulated_marker)
            ethos.mission_statement = "\n".join(new_lines)
        
        ethos.behavioral_rules = json.dumps(current_rules[-20:])  # Keep last 20 wisdom entries
        ethos.updated_at = datetime.utcnow()
        
        db.flush()
    
    @staticmethod
    async def execute_reincarnation_with_task_preservation(
        agent: Agent,
        db: Session,
        conversation_context: str,
        current_task_id: Optional[str] = None,
        task_progress: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute reincarnation while preserving task state for continuity.
        """
        # Prepare task state for transfer
        task_state = {
            "previous_task_id": current_task_id,
            "progress": task_progress or "unknown",
            "context": conversation_context[:2000],  # Truncated
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add task state to conversation context for summarization
        full_context = f"""TASK STATE TO PRESERVE:
    - Current Task: {current_task_id or 'None'}
    - Progress: {task_progress or 'Unknown'}%
    - Recent Context: {conversation_context[:1000]}

    Please summarize what the next agent needs to know to CONTINUE this work."""

        # Execute normal reincarnation
        result = await ReincarnationService.execute_reincarnation(
            agent=agent,
            db=db,
            conversation_context=full_context
        )
        
        # If successor spawned, transfer task
        if result["successor_spawned"] and current_task_id:
            new_agent = db.query(Agent).filter_by(
                agentium_id=result["successor_id"]
            ).first()
            
            if new_agent:
                # Update task to new agent
                task = db.query(Task).filter_by(id=current_task_id).first()
                if task:
                    # Update task assignment
                    old_assignments = task.assigned_task_agent_ids or []
                    if agent.agentium_id in old_assignments:
                        old_assignments.remove(agent.agentium_id)
                    old_assignments.append(new_agent.agentium_id)
                    task.assigned_task_agent_ids = old_assignments
                    
                    # Log the transfer
                    task._log_status_change(
                        "agent_reincarnated", 
                        agent.agentium_id,
                        f"Task transferred to successor {new_agent.agentium_id} due to context limit"
                    )
                    
                    db.flush()
                    print(f"   📋 Task {current_task_id} transferred: {agent.agentium_id} → {new_agent.agentium_id}")
                    
                    result["task_transferred"] = current_task_id
        
        return result

    @staticmethod
    def get_predecessor_context(successor: Agent, db: Session) -> Dict[str, Any]:
        """
        New agent calls this to understand what its predecessor was doing.
        Returns relevant context from previous incarnation.
        """
        # Find terminated predecessor with same role
        predecessor = db.query(Agent).filter(
            Agent.agent_type == successor.agent_type,
            Agent.status == AgentStatus.TERMINATED,
            Agent.terminated_at > datetime.utcnow() - timedelta(minutes=5),  # Recent death
            Agent.is_active == 'N'
        ).order_by(Agent.terminated_at.desc()).first()
        
        if not predecessor:
            return {
                "has_predecessor": False,
                "message": "No recent predecessor found. You are a fresh spawn."
            }
        
        # Get predecessor's ethos (contains life summary)
        predecessor_ethos = None
        if predecessor.ethos_id:
            predecessor_ethos = db.query(Ethos).filter_by(id=predecessor.ethos_id).first()
        
        # Get recent audit logs of predecessor
        from backend.models.entities.audit import AuditLog
        recent_actions = db.query(AuditLog).filter_by(
            actor_id=predecessor.agentium_id
        ).order_by(AuditLog.created_at.desc()).limit(5).all()
        
        return {
            "has_predecessor": True,
            "predecessor_id": predecessor.agentium_id,
            "termination_reason": predecessor.termination_reason,
            "predecessor_wisdom": predecessor_ethos.behavioral_rules if predecessor_ethos else None,
            "recent_actions": [
                {
                    "action": a.action,
                    "description": a.description,
                    "timestamp": a.created_at.isoformat()
                }
                for a in recent_actions
            ],
            "advice": "If confused about your current task, consult your parent/supervisor agent for clarification."
        }

    @staticmethod
    async def _spawn_successor(
        agent: Agent,
        db: Session,
        previous_incarnation: int,
        wisdom_summary: str
    ) -> Optional[Agent]:
        """Spawn a new agent to continue the work."""        
        # Determine parent for spawning
        if agent.parent:
            parent = agent.parent
        else:
            # For Head of Council or root agents, self-spawn (special case)
            parent = agent
        
        # Generate new ID (increment from current)
        from backend.models.entities.agents import AgentType
        
        new_agent = parent.spawn_child(
            agent_type=AgentType(agent.agent_type.value),
            session=db,
            name=f"{agent.name} (Incarnation {previous_incarnation + 1})",
            description=f"Reincarnation of {agent.agentium_id}. Inherited wisdom from previous life.",
            is_persistent=agent.is_persistent,  # Inherit persistence
            idle_mode_enabled=agent.idle_mode_enabled,
            persistent_role=agent.persistent_role if hasattr(agent, 'persistent_role') else None
        )
        
        # Copy key attributes
        new_agent.constitution_version = agent.constitution_version
        new_agent.preferred_config_id = agent.preferred_config_id
        
        # Transfer accumulated wisdom ethos (already updated in step 2)
        # The new agent gets a fresh ethos based on current templates,
        # but we'll merge the wisdom
        
        if new_agent.ethos_id:
            successor_ethos = db.query(Ethos).filter_by(id=new_agent.ethos_id).first()
            if successor_ethos:
                # Prepend predecessor's accumulated wisdom
                predecessor_ethos = db.query(Ethos).filter_by(id=agent.ethos_id).first()
                if predecessor_ethos:
                    successor_ethos.mission_statement = (
                        f"[PREDECESSOR: {agent.agentium_id} - Incarnation {previous_incarnation}]\n"
                        f"Inherited wisdom: {wisdom_summary[:200]}...\n\n"
                        f"{successor_ethos.mission_statement}"
                    )
                    db.flush()
        
        db.flush()
        return new_agent
    
    @staticmethod
    def get_reincarnation_stats(agentium_id: str) -> Dict[str, Any]:
        """Get statistics about an agent's reincarnation history."""
        return context_manager.get_stats(agentium_id)


# Singleton
reincarnation_service = ReincarnationService()