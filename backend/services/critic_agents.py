"""
Critic Agents Service for Agentium.
Manages task output review, retry logic, and escalation to Council.
Critics operate OUTSIDE the democratic chain with absolute veto authority.
"""

import hashlib
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from backend.models.database import get_db_context
from backend.models.entities.agents import Agent, AgentType, AgentStatus
from backend.models.entities.critics import (
    CriticAgent, CritiqueReview, CriticType, CriticVerdict, CRITIC_TYPE_TO_AGENT_TYPE
)
from backend.models.entities.task import Task, TaskStatus
from backend.models.entities.audit import AuditLog, AuditLevel, AuditCategory
from backend.services.acceptance_criteria import (   # Phase 6.3
    AcceptanceCriteriaService, AcceptanceCriterion, CriterionResult
)


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
        
        # 5. Load acceptance criteria for this task (Phase 6.3)
        task_for_criteria = db.query(Task).filter_by(id=task_id).first()
        task_criteria: list[AcceptanceCriterion] = []
        criteria_results: list[CriterionResult] = []
        if task_for_criteria and task_for_criteria.acceptance_criteria:
            task_criteria = AcceptanceCriteriaService.from_json(
                task_for_criteria.acceptance_criteria
            )

        # 6. Run deterministic criteria checks (before AI model call)
        if task_criteria:
            criteria_results = AcceptanceCriteriaService.evaluate_criteria(
                task_criteria, output_content, critic_type.value
            )
            aggregation = AcceptanceCriteriaService.aggregate(criteria_results)
            if not aggregation["all_mandatory_passed"]:
                # Mandatory criterion failed — reject immediately, skip AI call
                failed_metrics = ", ".join(aggregation["mandatory_failures"])
                duration_ms = (time.monotonic() - start_time) * 1000
                review = CritiqueReview(
                    task_id=task_id,
                    subtask_id=subtask_id,
                    critic_type=critic_type,
                    critic_agentium_id=critic.agentium_id,
                    verdict=CriticVerdict.REJECT,
                    rejection_reason=f"Mandatory acceptance criteria failed: {failed_metrics}",
                    suggestions="Fix the criteria listed in criteria_results before resubmitting.",
                    retry_count=retry_count,
                    max_retries=self.DEFAULT_MAX_RETRIES,
                    review_duration_ms=duration_ms,
                    model_used=critic.preferred_review_model,
                    output_hash=output_hash,
                    criteria_results=[r.to_dict() for r in criteria_results],
                    criteria_evaluated=aggregation["total"],
                    criteria_passed=aggregation["passed"],
                    agentium_id=f"CR{critic.agentium_id}",
                )
                db.add(review)
                critic.record_review(CriticVerdict.REJECT, duration_ms)
                critic.status = original_status
                self._log_review(db, critic, task_id, CriticVerdict.REJECT,
                                 f"Mandatory criteria failed: {failed_metrics}")
                db.commit()
                return {
                    'verdict': CriticVerdict.REJECT.value,
                    'review_id': review.id,
                    'task_id': task_id,
                    'critic_id': critic.agentium_id,
                    'critic_type': critic_type.value,
                    'rejection_reason': f"Mandatory acceptance criteria failed: {failed_metrics}",
                    'suggestions': "Fix the criteria listed in criteria_results.",
                    'criteria_results': [r.to_dict() for r in criteria_results],
                    'criteria_summary': aggregation,
                    'retry_count': retry_count,
                    'max_retries': self.DEFAULT_MAX_RETRIES,
                    'review_duration_ms': round(duration_ms, 1),
                    'cached': False,
                }

        # 7. Perform the AI model review
        verdict, reason, suggestions = await self._execute_review(
            db, critic, task_id, output_content, critic_type
        )
        
        duration_ms = (time.monotonic() - start_time) * 1000
        
        # 8. Determine if we should escalate
        if verdict == CriticVerdict.REJECT and retry_count >= self.DEFAULT_MAX_RETRIES:
            verdict = CriticVerdict.ESCALATE
            reason = f"Max retries ({self.DEFAULT_MAX_RETRIES}) exhausted. Original: {reason}"
        
        # 9. Create review record (Phase 6.3: include criteria_results)
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
            criteria_results=[r.to_dict() for r in criteria_results] if criteria_results else None,
            criteria_evaluated=len(criteria_results) if criteria_results else None,
            criteria_passed=sum(1 for r in criteria_results if r.passed) if criteria_results else None,
            agentium_id=f"CR{critic.agentium_id}",  # CritiqueReview agentium_id
        )
        
        db.add(review)
        
        # 10. Update critic stats
        critic.record_review(verdict, duration_ms)
        critic.status = AgentStatus.ACTIVE
        
        # 11. Audit log
        self._log_review(db, critic, task_id, verdict, reason)
        
        db.commit()
        
        # 12. Build response
        criteria_aggregation = (
            AcceptanceCriteriaService.aggregate(criteria_results)
            if criteria_results else None
        )
        result = {
            'verdict': verdict.value,
            'review_id': review.id,
            'task_id': task_id,
            'critic_id': critic.agentium_id,
            'critic_type': critic_type.value,
            'rejection_reason': reason if verdict != CriticVerdict.PASS else None,
            'suggestions': suggestions,
            'criteria_results': [r.to_dict() for r in criteria_results] if criteria_results else [],
            'criteria_summary': criteria_aggregation,
            'retry_count': retry_count,
            'max_retries': self.DEFAULT_MAX_RETRIES,
            'review_duration_ms': round(duration_ms, 1),
            'cached': False,
            'consensus_reached': True, # By default
        }
        
        # 12.5. Critic Consensus Protocol & Case Law Indexing
        if verdict == CriticVerdict.REJECT:
            # Secondary check for consensus if this is the first rejection
            if retry_count == 0:
                secondary_critic = self._get_available_critic(db, critic_type, exclude_id=critic.id)
                if secondary_critic:
                    logger.info(f"Consensus Protocol triggered: Secondary critic {secondary_critic.agentium_id} evaluating.")
                    sec_verdict, _, _ = await self._execute_review(db, secondary_critic, task_id, output_content, critic_type)
                    if sec_verdict == CriticVerdict.PASS:
                        # Conflicting views - Escalate to Senior Critic or pass conditionally
                        logger.warning("Critic Consensus Failure: Critics disagree. Deferring to conditional pass.")
                        result['verdict'] = CriticVerdict.PASS.value
                        result['consensus_reached'] = False
                        verdict = CriticVerdict.PASS
                        
            # If it's a hard rejection, index as Constitutional Case Law
            if verdict == CriticVerdict.REJECT:
                try:
                    from backend.services.knowledge_service import get_knowledge_service
                    knowledge = get_knowledge_service()
                    case_law_content = (
                        f"REJECTED OUTPUT CASE LAW\n"
                        f"Task: {task.description if task else 'Unknown'}\n"
                        f"Reason for rejection: {reason}\n"
                        f"Critic Actionable Feedback: {suggestions}\n"
                        f"Do NOT repeat the mistakes found in this output pattern."
                    )
                    knowledge.store_or_revise_knowledge(
                        content=case_law_content,
                        collection_name="critic_case_law",
                        doc_id=f"case_law_{task_id}_{int(time.time())}",
                        metadata={"critic_type": critic_type.value, "task_id": task_id}
                    )
                    logger.info(f"Indexed Case Law for rejected task {task_id}")
                except Exception as e:
                    logger.error(f"Failed to index case law: {e}")

        # 13. Handle escalation
        if verdict == CriticVerdict.ESCALATE:
            result['escalation'] = await self._escalate_to_council(
                db, task_id, critic_type, reason
            )
        
        return result

    def _get_available_critic(
        self, db: Session, critic_type: CriticType, exclude_id: Optional[str] = None
    ) -> Optional[CriticAgent]:
        """Find an available critic agent of the specified type."""
        agent_type = CRITIC_TYPE_TO_AGENT_TYPE[critic_type]
        
        query = db.query(CriticAgent).filter(
            CriticAgent.agent_type == agent_type,
            CriticAgent.is_active == True,
            CriticAgent.status.in_([AgentStatus.ACTIVE, AgentStatus.IDLE_WORKING]),
        )
        
        if exclude_id:
            query = query.filter(CriticAgent.id != exclude_id)
            
        critic = query.order_by(
            CriticAgent.reviews_completed.asc()  # Load-balance: least busy first
        ).first()
        
        return critic
    
    # Model orthogonality: critics use a different provider/model than executors.
    # Override per critic instance via preferred_review_model.
    CRITIC_DEFAULT_MODEL = "openai:gpt-4o-mini"  # Distinct from executor default

    async def _execute_review(
        self,
        db: Session,
        critic: CriticAgent,
        task_id: str,
        output_content: str,
        critic_type: CriticType,
    ) -> tuple:
        """
        Execute the review via a dedicated AI model (orthogonal failure modes).

        Two-stage approach:
          1. Rule-based pre-flight — fast, cheap, catches obvious violations.
          2. AI model review — semantic validation against task intent.

        Returns:
            (verdict: CriticVerdict, reason: Optional[str], suggestions: Optional[str])
        """
        task = db.query(Task).filter_by(id=task_id).first()

        # Stage 1: Rule-based pre-flight (no API cost)
        preflight_verdict, preflight_reason, preflight_suggestions = self._preflight_check(
            output_content, critic_type, task
        )
        if preflight_verdict == CriticVerdict.REJECT:
            return (preflight_verdict, preflight_reason, preflight_suggestions)

        # Stage 2: AI model review (orthogonal model)
        try:
            return await self._ai_review(critic, task, output_content, critic_type)
        except Exception as exc:
            logger.warning(
                "AI review failed for task %s (%s critic): %s. "
                "Falling back to rule-based result.",
                task_id, critic_type.value, exc,
            )
            # Fall back to rule-based result rather than blocking execution
            return self._rule_based_review(output_content, critic_type, task)

    async def _ai_review(
        self,
        critic: CriticAgent,
        task: Optional[Task],
        output_content: str,
        critic_type: CriticType,
    ) -> tuple:
        """
        Call an AI model that is DIFFERENT from the executor model.
        Uses the model_provider abstraction already in the codebase.
        """
        from backend.services.model_provider import ModelService

        model_key = critic.preferred_review_model or self.CRITIC_DEFAULT_MODEL

        system_prompt = self._build_critic_system_prompt(critic_type)
        user_prompt = self._build_critic_user_prompt(critic_type, task, output_content)

        raw_response = await ModelService.generate(
            model_key=model_key,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=512,
            temperature=0.1,   # Low temperature — we want deterministic judgement
        )

        return self._parse_ai_verdict(raw_response)

    def _build_critic_system_prompt(self, critic_type: CriticType) -> str:
        """Build a tight system prompt that forces structured JSON output."""
        role_descriptions = {
            CriticType.CODE: (
                "You are a senior code reviewer with a security and correctness focus. "
                "You NEVER write code yourself — only evaluate what you are given."
            ),
            CriticType.OUTPUT: (
                "You are a quality assurance specialist. "
                "Your job is to verify that an agent's output actually satisfies the user's intent."
            ),
            CriticType.PLAN: (
                "You are an execution plan auditor. "
                "You verify that plans are sound, non-circular, and achievable."
            ),
        }
        return f"""{role_descriptions[critic_type]}

Respond ONLY with a JSON object — no markdown, no preamble:
{{
  "verdict": "pass" | "reject",
  "reason": "<one concise sentence — null if pass>",
  "suggestions": "<one actionable fix — null if pass>"
}}"""

    def _build_critic_user_prompt(
        self,
        critic_type: CriticType,
        task: Optional[Task],
        output_content: str,
    ) -> str:
        task_context = (
            f"TASK DESCRIPTION:\n{task.description}\n\n"
            if task and task.description
            else "TASK DESCRIPTION: (not available)\n\n"
        )

        criteria_map = {
            CriticType.CODE: (
                "Evaluate for: syntax correctness, security (no eval/exec/shell injection), "
                "logic soundness, and absence of obvious bugs."
            ),
            CriticType.OUTPUT: (
                "Evaluate whether the output meaningfully addresses the task description. "
                "Reject if: empty, pure error traceback, or clearly off-topic."
            ),
            CriticType.PLAN: (
                "Evaluate the plan for: completeness, absence of circular steps, "
                "and achievability within reasonable scope (< 100 steps)."
            ),
        }

        return (
            f"{task_context}"
            f"EVALUATION CRITERIA:\n{criteria_map[critic_type]}\n\n"
            f"OUTPUT TO REVIEW:\n{output_content[:6000]}"  # Cap at 6k chars
        )

    def _parse_ai_verdict(self, raw_response: str) -> tuple:
        """Parse the AI model's JSON verdict into (verdict, reason, suggestions)."""
        import json, re

        # Strip markdown fences if model wrapped output anyway
        cleaned = re.sub(r"```(?:json)?|```", "", raw_response).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Model didn't follow instructions — be lenient, log, pass
            logger.warning("Critic AI returned non-JSON: %s", raw_response[:200])
            return (CriticVerdict.PASS, None, "AI response was not valid JSON — manual review recommended")

        verdict_str = str(data.get("verdict", "pass")).lower()
        verdict = CriticVerdict.REJECT if verdict_str == "reject" else CriticVerdict.PASS
        reason = data.get("reason") or None
        suggestions = data.get("suggestions") or None

        return (verdict, reason, suggestions)

    def _preflight_check(
        self,
        content: str,
        critic_type: CriticType,
        task: Optional[Task],
    ) -> tuple:
        """Fast, cheap rule-based checks run BEFORE the AI model call."""
        if critic_type == CriticType.CODE:
            return self._review_code(content, task)
        elif critic_type == CriticType.OUTPUT:
            return self._review_output(content, task)
        elif critic_type == CriticType.PLAN:
            return self._review_plan(content, task)
        return (CriticVerdict.PASS, None, None)

    def _rule_based_review(
        self,
        content: str,
        critic_type: CriticType,
        task: Optional[Task],
    ) -> tuple:
        """Identical to preflight — used as AI fallback."""
        return self._preflight_check(content, critic_type, task)
    
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
            is_active=True,
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
            CritiqueReview.is_active == True,
        ).order_by(CritiqueReview.reviewed_at.desc()).all()
        
        return [r.to_dict() for r in reviews]
    
    def get_critic_stats(self, db: Session) -> Dict[str, Any]:
        """Get aggregate statistics for all critic agents."""
        critics = db.query(CriticAgent).filter(
            CriticAgent.is_active == True,
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