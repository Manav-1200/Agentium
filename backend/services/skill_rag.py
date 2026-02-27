"""
RAG (Retrieval-Augmented Generation) integration for skills.
Combines skill retrieval with LLM generation.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.services.skill_manager import skill_manager
from backend.services.model_provider import ModelService
from backend.models.entities.agents import Agent

logger = logging.getLogger(__name__)


class SkillRAG:
    """
    RAG pipeline: Retrieve skills → Augment prompt → Generate with context.
    """
    
    def __init__(self):
        self.skill_manager = skill_manager
    
    async def execute_with_skills(
        self,
        task_description: str,
        agent: Agent,
        db: Session,
        model_config_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute task using RAG with skills.
        
        Flow:
        1. Search for relevant skills
        2. Build augmented prompt with skill context
        3. Generate response using LLM
        4. Return result with skill attribution
        """
        # Step 1: Retrieve relevant skills
        skills = self.skill_manager.search_skills(
            query=task_description,
            agent_tier=agent.agent_type.value,
            db=db,
            n_results=3,
            min_success_rate=0.7
        )
        
        # Step 2: Build RAG prompt
        rag_context = self._build_rag_context(skills, task_description)
        
        # Step 3: Generate with context
        result = await ModelService.generate_with_agent(
            agent=agent,
            user_message=rag_context["augmented_prompt"],
            config_id=model_config_id
        )
        
        # Step 4: Record skill usage
        for skill in skills:
            # Record that these skills were used (async)
            self.skill_manager.record_skill_usage(
                skill_id=skill["skill_id"],
                success=True,  # Will be updated based on critic review
                db=db
            )
        
        return {
            "content": result["content"],
            "model": result["model"],
            "tokens_used": result["tokens_used"],
            "skills_used": rag_context["skills_used"],
            "rag_context": rag_context["context_text"],
            "latency_ms": result["latency_ms"]
        }
    
    def _build_rag_context(
        self,
        skills: List[Dict],
        task_description: str
    ) -> Dict[str, Any]:
        """Build augmented prompt with skill context."""
        
        if not skills:
            # No skills found - standard prompt
            return {
                "augmented_prompt": task_description,
                "skills_used": [],
                "context_text": ""
            }
        
        # Build context from skills
        context_parts = []
        skills_used = []
        
        for i, skill in enumerate(skills, 1):
            meta = skill["metadata"]
            content = skill["content_preview"]
            
            context_parts.append(f"""
Relevant Skill {i}: {meta.get('display_name', 'Unknown')}
Type: {meta.get('skill_type')} | Domain: {meta.get('domain')} | Success Rate: {meta.get('success_rate', 0):.0%}
Description: {meta.get('description', 'N/A')}
Approach:
{content}
""")
            skills_used.append({
                "skill_id": skill["skill_id"],
                "name": meta.get("display_name"),
                "relevance_score": skill["relevance_score"]
            })
        
        # Build final augmented prompt
        augmented_prompt = f"""You are an AI agent executing a task. Use the following relevant skills from your knowledge library to inform your approach.

{chr(10).join(context_parts)}

---
TASK TO EXECUTE:
{task_description}

Instructions:
1. Follow the approaches from the relevant skills above
2. Adapt them to the specific requirements of this task
3. If multiple approaches conflict, choose the one with higher success rate
4. Document which skill approaches you used in your thinking

Begin execution:
"""
        
        return {
            "augmented_prompt": augmented_prompt,
            "skills_used": skills_used,
            "context_text": chr(10).join(context_parts)
        }
    
    async def suggest_skill_creation(
        self,
        task_description: str,
        execution_result: Dict[str, Any],
        agent: Agent,
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze if execution result should be converted to a skill.
        Returns skill draft if worthy, None otherwise.
        """
        # Check novelty - is this significantly different from existing skills?
        similar_skills = self.skill_manager.search_skills(
            query=task_description,
            agent_tier=agent.agent_type.value,
            db=db,
            n_results=1
        )
        
        if similar_skills and similar_skills[0]["relevance_score"] > 0.9:
            # Too similar to existing skill
            return None
        
        # Check quality - did execution succeed?
        if not execution_result.get("success", False):
            return None
        
        # Check reusability - is this a pattern that could be reused?
        # Use LLM to analyze
        analysis_prompt = f"""
Analyze if the following task execution should be converted to a reusable skill.

Task: {task_description}

Execution Steps:
{execution_result.get('steps_taken', 'N/A')}

Code/Output:
{execution_result.get('output', 'N/A')[:2000]}

Evaluate:
1. Is this a generalizable pattern or one-time task?
2. Would this be useful for similar future tasks?
3. Can the approach be documented as reusable steps?

Respond with JSON:
{{
    "should_create_skill": true/false,
    "reason": "explanation",
    "suggested_skill_name": "name",
    "suggested_domain": "frontend/backend/etc",
    "key_steps": ["step1", "step2"]
}}
"""
        
        analysis = await ModelService.generate_with_agent(
            agent=agent,
            user_message=analysis_prompt
        )
        
        # Parse response (simplified - would need robust JSON parsing)
        try:
            import json
            result = json.loads(analysis["content"])
            if result.get("should_create_skill"):
                return {
                    "draft_skill": {
                        "skill_name": result.get("suggested_skill_name"),
                        "domain": result.get("suggested_domain"),
                        "steps": result.get("key_steps"),
                        "description": task_description,
                        "success_rate": 0.8  # Initial estimate
                    },
                    "reason": result.get("reason")
                }
        except:
            pass
        
        return None


# Global instance
skill_rag = SkillRAG()