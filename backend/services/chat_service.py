"""
Chat service for Head of Council interactions.
Handles message processing, task creation, and context management.
"""

import re
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.models.entities import Agent, HeadOfCouncil, Task, TaskPriority, TaskType
from backend.models.entities.audit import AuditLog, AuditLevel, AuditCategory

class ChatService:
    """Service for handling Sovereign ↔ Head of Council chat."""
    
    @staticmethod
    async def process_message(
        head: HeadOfCouncil,
        message: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Process a message and return response.
        Non-streaming version.
        """
        provider = await ModelService.get_provider("sovereign")
        if not provider:
            raise ValueError("No model provider available")
        
        system_prompt = head.get_system_prompt()
        context = await ChatService.get_system_context(db)
        
        full_prompt = f"""{system_prompt}

Current System State:
{context}

Address the Sovereign respectfully. If they issue a command that requires execution, indicate that you will create a task."""

        result = await provider.generate(full_prompt, message)
        
        # Analyze if we should create a task
        task_info = await ChatService.analyze_for_task(head, message, result["content"], db)
        
        return {
            "content": result["content"],
            "model": result["model"],
            "task_created": task_info["created"],
            "task_id": task_info.get("task_id")
        }
    
    @staticmethod
    async def get_system_context(db: Session) -> str:
        """Get current system state for context."""
        # Count agents by type
        agents = db.query(Agent).all()
        
        head_count = sum(1 for a in agents if a.agent_type.value == "head_of_council" and a.is_active == 'Y')
        council_count = sum(1 for a in agents if a.agent_type.value == "council_member" and a.is_active == 'Y')
        lead_count = sum(1 for a in agents if a.agent_type.value == "lead_agent" and a.is_active == 'Y')
        task_count = sum(1 for a in agents if a.agent_type.value == "task_agent" and a.is_active == 'Y')
        
        # Get active tasks
        pending_tasks = db.query(Task).filter(Task.status.in_(["pending", "deliberating", "in_progress"])).count()
        
        return f"""- Head of Council: {'Active' if head_count > 0 else 'Inactive'}
- Council Members: {council_count} active
- Lead Agents: {lead_count} active  
- Task Agents: {task_count} active
- Pending Tasks: {pending_tasks}"""
    
    @staticmethod
    async def analyze_for_task(
        head: HeadOfCouncil,
        prompt: str,
        response: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Analyze if the message should create a task.
        Looks for execution keywords in both prompt and response.
        """
        execution_keywords = [
            "create", "execute", "run", "analyze", "process", "generate",
            "write", "code", "research", "investigate", "calculate",
            "deploy", "build", "test", "validate"
        ]
        
        # Check if it seems like a command
        is_command = any(keyword in prompt.lower() for keyword in execution_keywords)
        
        # Check if Head acknowledged it as a task
        task_acknowledged = any(phrase in response.lower() for phrase in [
            "i shall", "i will", "creating task", "delegating", "assigning",
            "the council will", "lead agents will"
        ])
        
        if is_command and task_acknowledged:
            # Create a task
            task = Task(
                title=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                description=prompt,
                task_type=TaskType.EXECUTION,
                priority=TaskPriority.NORMAL,
                created_by="sovereign",
                head_of_council_id=head.id,
                requires_deliberation=True
            )
            
            db.add(task)
            db.commit()
            
            # Start deliberation
            council = db.query(Agent).filter_by(agent_type="council_member", is_active='Y').all()
            if council:
                task.start_deliberation([c.agentium_id for c in council])
                db.commit()
            
            return {
                "created": True,
                "task_id": task.agentium_id
            }
        
        return {"created": False}
    
    @staticmethod
    async def log_interaction(
        head_agentium_id: str,
        prompt: str,
        response: str,
        config_id: str,
        db: Session
    ):
        """Log chat interaction for audit trail."""
        log = AuditLog.log(
            level=AuditLevel.INFO,
            category=AuditCategory.COMMUNICATION,
            actor_type="agent",
            actor_id=head_agentium_id,
            action="chat_response",
            target_type="conversation",
            target_id=None,
            description=f"Head of Council responded to Sovereign",
            before_state={"prompt": prompt[:500]},
            after_state={"response": response[:1000]},
            metadata={
                "config_id": config_id,
                "full_prompt_length": len(prompt),
                "full_response_length": len(response)
            }
        )
        db.add(log)
        db.commit()