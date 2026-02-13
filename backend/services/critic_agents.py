"""
Critic Agents Service for Agentium.
Manages task output review, retry logic, and escalation to Council.
Critics operate OUTSIDE the democratic chain with absolute veto authority.
"""

import hashlib
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from backend.models.database import get_db_context
from backend.models.entities.agents import Agent, AgentType, AgentStatus
from backend.models.entities.critics import (
    CriticAgent, CritiqueReview, CriticType, CriticVerdict, CRITIC_TYPE_TO_AGENT_TYPE
)
from backend.models.entities.task import Task, TaskStatus
from backend.models.entities.audit import AuditLog, AuditLevel, AuditCategory


class CriticService:
    """
    Orchestrates critic reviews on task outputs.
    
    Flow:
        Task Output → route to correct critic → review → verdict
        PASS     → output approved, return to caller
        REJECT   → retry within same team (up to max_retries)
        ESCALATE → forward to Council after exhausting retries
    """
    
    DEFAULT_MAX_RETRIES = 5
    
    async def review_task_output(
        self,
        db: Session,
        task_id: str,
        output_content: str,
        critic_type: CriticType,
        subtask_id: Optional[str] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Submit a task output for critic review.
        
        Args:
            db: Database session
            task_id: ID of the task being reviewed
            output_content: The output to validate
            critic_type: Which critic type should review (CODE, OUTPUT, PLAN)
            subtask_id: Optional subtask ID if reviewing a subtask
            retry_count: Current retry attempt number
            
        Returns:
            Dict with verdict, review details, and retry/escalation info
        """
        start_time = time.monotonic()
        
        # 1. Find an available critic of the right type
        critic = self._get_available_critic(db, critic_type)
        if not critic:
            # No critic available — auto-pass with warning
            return {
                'verdict': CriticVerdict.PASS.value,
                'message': f'No {critic_type.value} critic available — auto-passed',
                'auto_passed': True,
                'task_id': task_id,
            }
        
        # 2. Set critic to REVIEWING status
        original_status = critic.status
        critic.status = AgentStatus.REVIEWING
        
        # 3. Hash the output for deduplication
        output_hash = hashlib.sha256(output_content.encode()).hexdigest()
        
        # 4. Check if we already reviewed this exact output (dedup)
        existing_review = db.query(CritiqueReview).filter(
            CritiqueReview.task_id == task_id,
            CritiqueReview.output_hash == output_hash,
            CritiqueReview.critic_type == critic_type,
        ).first()
        
        if existing_review:
            critic.status = original_status
            return {
                'verdict': existing_review.verdict.value,
                'message': 'Duplicate output — returning cached review',
                'review_id': existing_review.id,
                'task_id': task_id,
                'cached': True,
            }
        
        # 5. Perform the review
        verdict, reason, suggestions = await self._execute_review(
            db, critic, task_id, output_content, critic_type
        )
        
        duration_ms = (time.monotonic() - start_time) * 1000
        
        # 6. Determine if we should escalate
        if verdict == CriticVerdict.REJECT and retry_count >= self.DEFAULT_MAX_RETRIES:
            verdict = CriticVerdict.ESCALATE
            reason = f"Max retries ({self.DEFAULT_MAX_RETRIES}) exhausted. Original: {reason}"
        
        # 7. Create review record
        review = CritiqueReview(
            task_id=task_id,
            subtask_id=subtask_id,
            critic_type=critic_type,
            critic_agentium_id=critic.agentium_id,
            verdict=verdict,
            rejection_reason=reason if verdict != CriticVerdict.PASS else None,
            suggestions=suggestions,
            retry_count=retry_count,
            max_retries=self.DEFAULT_MAX_RETRIES,
            review_duration_ms=duration_ms,
            model_used=critic.preferred_review_model,
            output_hash=output_hash,
            agentium_id=f"CR{critic.agentium_id}",  # CritiqueReview agentium_id
        )
        
        db.add(review)
        
        # 8. Update critic stats
        critic.record_review(verdict, duration_ms)
        critic.status = AgentStatus.ACTIVE
        
        # 9. Audit log
        self._log_review(db, critic, task_id, verdict, reason)
        
        db.commit()
        
        # 10. Build response
        result = {
            'verdict': verdict.value,
            'review_id': review.id,
            'task_id': task_id,
            'critic_id': critic.agentium_id,
            'critic_type': critic_type.value,
            'rejection_reason': reason if verdict != CriticVerdict.PASS else None,
            'suggestions': suggestions,
            'retry_count': retry_count,
            'max_retries': self.DEFAULT_MAX_RETRIES,
            'review_duration_ms': round(duration_ms, 1),
            'cached': False,
        }
        
        # 11. Handle escalation
        if verdict == CriticVerdict.ESCALATE:
            result['escalation'] = await self._escalate_to_council(
                db, task_id, critic_type, reason
            )
        
        return result
    
    def _get_available_critic(
        self, db: Session, critic_type: CriticType
    ) -> Optional[CriticAgent]:
        """Find an available critic agent of the specified type."""
        agent_type = CRITIC_TYPE_TO_AGENT_TYPE[critic_type]
        
        critic = db.query(CriticAgent).filter(
            CriticAgent.agent_type == agent_type,
            CriticAgent.is_active == 'Y',
            CriticAgent.status.in_([AgentStatus.ACTIVE, AgentStatus.IDLE_WORKING]),
        ).order_by(
            CriticAgent.reviews_completed.asc()  # Load-balance: least busy first
        ).first()
        
        return critic
    
    async def _execute_review(
        self,
        db: Session,
        critic: CriticAgent,
        task_id: str,
        output_content: str,
        critic_type: CriticType,
    ) -> tuple:
        """
        Execute the actual review logic.
        
        In production this would call a different AI model than the executor.
        Currently implements rule-based checks as a foundation.
        
        Returns:
            (verdict: CriticVerdict, reason: Optional[str], suggestions: Optional[str])
        """
        # Get the task for context
        task = db.query(Task).filter_by(id=task_id).first()
        
        if critic_type == CriticType.CODE:
            return self._review_code(output_content, task)
        elif critic_type == CriticType.OUTPUT:
            return self._review_output(output_content, task)
        elif critic_type == CriticType.PLAN:
            return self._review_plan(output_content, task)
        
        return (CriticVerdict.PASS, None, None)
    
    def _review_code(self, content: str, task: Optional[Task]) -> tuple:
        """Code critic: check syntax, security, and logic."""
        issues = []
        suggestions = []
        
        # Security checks
        dangerous_patterns = [
            'eval(', 'exec(', '__import__', 'os.system(', 'subprocess.Popen(',
            'rm -rf', 'DROP TABLE', 'DELETE FROM', '; --',
        ]
        for pattern in dangerous_patterns:
            if pattern in content:
                issues.append(f"Dangerous pattern detected: '{pattern}'")
                suggestions.append(f"Remove or sandbox usage of '{pattern}'")
        
        # Basic quality checks
        if len(content.strip()) == 0:
            issues.append("Empty output")
        
        if len(content) > 100000:
            issues.append("Output exceeds 100K chars — may indicate unbounded generation")
            suggestions.append("Add output length constraints")
        
        if issues:
            return (
                CriticVerdict.REJECT,
                "; ".join(issues),
                "; ".join(suggestions) if suggestions else None,
            )
        
        return (CriticVerdict.PASS, None, None)
    
    def _review_output(self, content: str, task: Optional[Task]) -> tuple:
        """Output critic: validate against user intent."""
        issues = []
        suggestions = []
        
        if len(content.strip()) == 0:
            issues.append("Output is empty — does not fulfill any user intent")
            suggestions.append("Ensure the executor produces meaningful output")
        
        # Check if output seems like an error dump rather than real output
        error_indicators = ['Traceback (most recent call last)', 'Error:', 'Exception:']
        error_count = sum(1 for indicator in error_indicators if indicator in content)
        if error_count >= 2:
            issues.append("Output appears to be an error traceback, not a valid result")
            suggestions.append("Fix the underlying error before resubmitting")
        
        # Check against task description for relevance (basic keyword overlap)
        if task and task.description:
            task_keywords = set(task.description.lower().split())
            output_keywords = set(content.lower().split()[:200])  # First 200 words
            overlap = task_keywords & output_keywords
            relevance = len(overlap) / max(len(task_keywords), 1)
            
            if relevance < 0.05 and len(task_keywords) > 5:
                issues.append("Output appears unrelated to the task description")
                suggestions.append("Ensure output addresses the task requirements")
        
        if issues:
            return (
                CriticVerdict.REJECT,
                "; ".join(issues),
                "; ".join(suggestions) if suggestions else None,
            )
        
        return (CriticVerdict.PASS, None, None)
    
    def _review_plan(self, content: str, task: Optional[Task]) -> tuple:
        """Plan critic: validate execution DAG soundness."""
        issues = []
        suggestions = []
        
        if len(content.strip()) == 0:
            issues.append("Execution plan is empty")
            suggestions.append("Generate a valid plan with at least one step")
        
        # Check for circular references (basic heuristic)
        lines = content.lower().split('\n')
        if len(lines) > 1:
            seen_steps = set()
            for line in lines:
                stripped = line.strip()
                if stripped in seen_steps and stripped:
                    issues.append(f"Duplicate step detected: '{stripped[:50]}'")
                    suggestions.append("Remove duplicate steps from the plan")
                    break
                seen_steps.add(stripped)
        
        # Check for unreasonable plan size
        if len(lines) > 100:
            issues.append(f"Plan has {len(lines)} steps — may be over-engineered")
            suggestions.append("Simplify the plan to fewer, higher-level steps")
        
        if issues:
            return (
                CriticVerdict.REJECT,
                "; ".join(issues),
                "; ".join(suggestions) if suggestions else None,
            )
        
        return (CriticVerdict.PASS, None, None)
    
    async def _escalate_to_council(
        self,
        db: Session,
        task_id: str,
        critic_type: CriticType,
        reason: str,
    ) -> Dict[str, Any]:
        """Escalate to Council after max retries exhausted."""
        # Log the escalation
        audit = AuditLog(
            level=AuditLevel.WARNING,
            category=AuditCategory.GOVERNANCE,
            actor_type="critic",
            actor_id=f"critic_{critic_type.value}",
            action="critic_escalation",
            target_type="task",
            target_id=task_id,
            description=(
                f"Task {task_id} escalated to Council after max retries. "
                f"Critic type: {critic_type.value}. Reason: {reason}"
            ),
            created_at=datetime.utcnow(),
        )
        db.add(audit)
        
        # Update task status to indicate Council review needed
        task = db.query(Task).filter_by(id=task_id).first()
        if task:
            task.status = TaskStatus.DELIBERATING
            task._log_status_change(
                "deliberating",
                f"critic_{critic_type.value}",
                f"Escalated by {critic_type.value} critic: {reason[:200]}"
            )
        
        db.commit()
        
        return {
            'escalated': True,
            'reason': reason,
            'task_status': 'deliberating',
        }
    
    def _log_review(
        self,
        db: Session,
        critic: CriticAgent,
        task_id: str,
        verdict: CriticVerdict,
        reason: Optional[str],
    ):
        """Log every critic review in the audit trail."""
        level = AuditLevel.INFO if verdict == CriticVerdict.PASS else AuditLevel.WARNING
        
        audit = AuditLog(
            level=level,
            category=AuditCategory.GOVERNANCE,
            actor_type="critic",
            actor_id=critic.agentium_id,
            action=f"critic_review_{verdict.value}",
            target_type="task",
            target_id=task_id,
            description=(
                f"Critic {critic.agentium_id} ({critic.critic_specialty.value}) "
                f"verdict: {verdict.value}"
                + (f" — {reason[:200]}" if reason else "")
            ),
            created_at=datetime.utcnow(),
        )
        db.add(audit)
    
    def get_reviews_for_task(
        self, db: Session, task_id: str
    ) -> List[Dict[str, Any]]:
        """Get all critic reviews for a specific task."""
        reviews = db.query(CritiqueReview).filter(
            CritiqueReview.task_id == task_id,
            CritiqueReview.is_active == 'Y',
        ).order_by(CritiqueReview.reviewed_at.desc()).all()
        
        return [r.to_dict() for r in reviews]
    
    def get_critic_stats(self, db: Session) -> Dict[str, Any]:
        """Get aggregate statistics for all critic agents."""
        critics = db.query(CriticAgent).filter(
            CriticAgent.is_active == 'Y',
        ).all()
        
        total_reviews = sum(c.reviews_completed for c in critics)
        total_vetoes = sum(c.vetoes_issued for c in critics)
        total_escalations = sum(c.escalations_issued for c in critics)
        
        by_type = {}
        for c in critics:
            ct = c.critic_specialty.value
            if ct not in by_type:
                by_type[ct] = {
                    'count': 0, 'reviews': 0, 'vetoes': 0,
                    'escalations': 0, 'approval_rate': 0.0,
                }
            by_type[ct]['count'] += 1
            by_type[ct]['reviews'] += c.reviews_completed
            by_type[ct]['vetoes'] += c.vetoes_issued
            by_type[ct]['escalations'] += c.escalations_issued
        
        # Calculate approval rates per type
        for ct in by_type:
            reviews = by_type[ct]['reviews']
            vetoes = by_type[ct]['vetoes']
            by_type[ct]['approval_rate'] = (
                round(((reviews - vetoes) / reviews) * 100, 1)
                if reviews > 0 else 0.0
            )
        
        return {
            'total_critics': len(critics),
            'total_reviews': total_reviews,
            'total_vetoes': total_vetoes,
            'total_escalations': total_escalations,
            'overall_approval_rate': (
                round(((total_reviews - total_vetoes) / total_reviews) * 100, 1)
                if total_reviews > 0 else 0.0
            ),
            'by_type': by_type,
            'critics': [c.to_dict() for c in critics],
        }


# Singleton instance
critic_service = CriticService()
