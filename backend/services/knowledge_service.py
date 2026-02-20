"""
Knowledge Service for Agentium.
RAG pipeline and semantic memory management.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from sqlalchemy.orm import Session

from backend.core.vector_store import get_vector_store, VectorStore
from backend.models.entities.constitution import Constitution, Ethos
from backend.models.entities.agents import Agent, AgentType
from backend.models.entities.task import Task


class KnowledgeService:
    """
    Manages RAG (Retrieval Augmented Generation) for all agents.
    Bridges PostgreSQL structured data and ChromaDB semantic data.
    """
    
    def __init__(self, vector_store: VectorStore = None):
        self.vector_store = vector_store or get_vector_store()
    
    def embed_constitution(self, db: Session, constitution: Constitution):
        """
        Vectorize constitution articles for semantic retrieval.
        Called when new constitution is created/amended.
        """
        articles = constitution.get_articles_dict()
        
        for article_num, article_data in articles.items():
            content = f"{article_data.get('title', '')}: {article_data.get('content', '')}"
            
            self.vector_store.add_constitution_article(
                article_id=f"{constitution.version}_{article_num}",
                content=content,
                metadata={
                    "version": constitution.version,
                    "version_number": constitution.version_number,
                    "article_number": article_num,
                    "effective_date": constitution.effective_date.isoformat() if constitution.effective_date else None,
                    "replaces_version": constitution.replaces_version.version if constitution.replaces_version else None
                }
            )
    
    def embed_ethos(self, ethos: Ethos):
        """
        Vectorize agent ethos for behavioral retrieval.
        """
        # Combine mission, rules, restrictions into single searchable doc
        content_parts = [
            f"Mission: {ethos.mission_statement}",
            "Core Values: " + ", ".join(ethos.get_core_values()),
            "Behavioral Rules: " + ", ".join(ethos.get_behavioral_rules()),
            "Restrictions: " + ", ".join(ethos.get_restrictions()),
            "Capabilities: " + ", ".join(ethos.get_capabilities())
        ]
        
        full_content = "\\n\\n".join(content_parts)
        
        self.vector_store.add_ethos(
            agentium_id=ethos.agentium_id or f"E{ethos.agent_id}",
            ethos_content=full_content,
            agent_type=ethos.agent_type,
            verified_by=ethos.verified_by_agentium_id
        )
    
    def get_agent_context(self,
                         db: Session,
                         agent: Agent,
                         task_description: str = None,
                         include_constitution: bool = True) -> Dict[str, Any]:
        """
        Build RAG context for an agent based on its tier.
        Returns structured context for LLM prompting.
        """
        context = {
            "agent_tier": agent.agent_type.value,
            "agent_id": agent.agentium_id,
            "retrieval_timestamp": datetime.utcnow().isoformat(),
            "knowledge_segments": []
        }
        
        # 1. Constitution grounding (all tiers)
        if include_constitution:
            const_results = self.vector_store.query_constitution(
                task_description or agent.agent_type.value,
                n_results=3
            )
            
            if const_results['documents'] and const_results['documents'][0]:
                for i, doc in enumerate(const_results['documents'][0]):
                    context['knowledge_segments'].append({
                        "type": "constitution",
                        "content": doc,
                        "relevance": 1.0 - (const_results['distances'][0][i] if const_results['distances'] else 0.5),
                        "source": const_results['metadatas'][0][i] if const_results['metadatas'] else {}
                    })
        
        # 2. Agent\\'s own Ethos
        if agent.ethos:
            # We could query vector store, but we have the object already
            ethos_content = {
                "type": "ethos",
                "content": {
                    "mission": agent.ethos.mission_statement,
                    "rules": agent.ethos.get_behavioral_rules(),
                    "restrictions": agent.ethos.get_restrictions()
                },
                "relevance": 1.0,
                "source": {"agentium_id": agent.ethos.agentium_id, "version": agent.ethos.version}
            }
            context["knowledge_segments"].append(ethos_content)
        
        # 3. Tier-specific knowledge
        if agent.agent_type == AgentType.COUNCIL_MEMBER:
            # Council needs deliberation history
            council_context = self.vector_store.query_knowledge(
                query=task_description or "recent deliberations precedent",
                collection_keys=["council_memory"],
                n_results=3
            )
            if council_context['documents'] and council_context['documents'][0]:
                for i, doc in enumerate(council_context['documents'][0][:2]):
                    context['knowledge_segments'].append({
                        "type": "precedent",
                        "content": doc,
                        "relevance": 0.9,
                        "source": council_context['metadatas'][0][i] if council_context['metadatas'] else {}
                    })
        
        elif agent.agent_type == AgentType.LEAD_AGENT:
            # Leads need coordination patterns
            patterns = self.vector_store.get_collection("task_patterns").query(
                query_texts=[task_description or "team coordination"],
                n_results=3
            )
            if patterns['documents'] and patterns['documents'][0]:
                for i, doc in enumerate(patterns['documents'][0][:2]):
                    context['knowledge_segments'].append({
                        "type": "coordination_pattern",
                        "content": doc,
                        "relevance": 0.85,
                        "metadata": patterns['metadatas'][0][i] if patterns['metadatas'] else {}
                    })
        
        elif agent.agent_type == AgentType.TASK_AGENT:
            # Task agents need execution patterns
            patterns = self.vector_store.get_collection("task_patterns").query(
                query_texts=[task_description or "execution best practices"],
                n_results=4,
                where={"type": "execution_pattern"}
            )
            if patterns['documents'] and patterns['documents'][0]:
                for i, doc in enumerate(patterns['documents'][0][:3]):
                    context['knowledge_segments'].append({
                        "type": "execution_pattern",
                        "content": doc,
                        "relevance": 0.8,
                        "metadata": patterns['metadatas'][0][i] if patterns['metadatas'] else {}
                    })
        
        # 4. Sovereign preferences (for all tiers)
        prefs = self.vector_store.get_collection("sovereign_prefs").query(
            query_texts=[task_description or agent.agent_type.value],
            n_results=2
        )
        if prefs['documents'] and prefs['documents'][0]:
            for i, doc in enumerate(prefs['documents'][0][:1]):
                context['knowledge_segments'].append({
                    "type": "sovereign_preference",
                    "content": doc,
                    "relevance": 0.95,  # High priority
                    "source": prefs['metadatas'][0][i] if prefs['metadatas'] else {}
                })
        
        return context
    
    def store_or_revise_knowledge(self,
                                  content: str,
                                  collection_name: str,
                                  doc_id: str,
                                  metadata: Dict[str, Any] = None,
                                  similarity_threshold: float = 0.3):
        """
        Store knowledge with duplicate detection (Workflow §4 — Revision Over Duplication).

        1. Search the target collection for semantically similar entries.
        2. If a similar entry exists (distance < threshold): revise it in place.
        3. If no match: create a new entry.

        This prevents the vector DB from accumulating near-duplicate knowledge
        and ensures institutional memory stays curated.
        """
        collection = self.vector_store.get_collection(collection_name)
        if not collection:
            # Fallback to blind insert if collection doesn't exist
            self.vector_store.add_execution_pattern(
                pattern_id=doc_id,
                description=content,
                success_rate=1.0,
                task_type="general",
                tools_used=[]
            )
            return {"action": "created_fallback", "doc_id": doc_id}

        # Step 1: Search for semantically similar entries
        try:
            existing = collection.query(
                query_texts=[content],
                n_results=1
            )

            if (existing['ids'] and existing['ids'][0]
                    and existing['distances'] and existing['distances'][0]
                    and existing['distances'][0][0] < similarity_threshold):
                # Step 2: Similar entry found — revise it
                existing_id = existing['ids'][0][0]
                existing_meta = existing['metadatas'][0][0] if existing['metadatas'] and existing['metadatas'][0] else {}

                revision_count = int(existing_meta.get("revision_count", 0)) + 1
                merged_metadata = {
                    **(metadata or {}),
                    "revised_from": existing_id,
                    "revised_at": datetime.utcnow().isoformat(),
                    "revision_count": revision_count,
                    "previous_distance": existing['distances'][0][0],
                }

                # Update in place: delete old, add revised
                collection.delete(ids=[existing_id])
                collection.add(
                    documents=[content],
                    metadatas=[merged_metadata],
                    ids=[existing_id]  # Keep the same ID for continuity
                )

                return {"action": "revised", "doc_id": existing_id, "revision": revision_count}

        except Exception:
            pass  # If search fails, fall through to create new

        # Step 3: No similar entry — create new
        final_metadata = {
            **(metadata or {}),
            "created_at": datetime.utcnow().isoformat(),
            "revision_count": 0,
        }
        collection.add(
            documents=[content],
            metadatas=[final_metadata],
            ids=[doc_id]
        )

        return {"action": "created", "doc_id": doc_id}

    def record_execution_pattern(self,
                                task: Task,
                                agent: Agent,
                                result_summary: str,
                                success: bool = True):
        """
        Record a successful execution pattern for future RAG.
        Now uses store_or_revise_knowledge to avoid duplicates (Workflow §4).
        Called after task completion.
        """
        if not success:
            return  # Only record successes

        pattern_desc = (
            f"Task: {task.title}\n"
            f"Description: {task.description}\n"
            f"Result: {result_summary}\n"
            f"Executed by: {agent.agentium_id} ({agent.agent_type.value})"
        )

        doc_id = f"{agent.agentium_id}_{task.id}_{datetime.utcnow().strftime('%Y%m%d')}"

        return self.store_or_revise_knowledge(
            content=pattern_desc,
            collection_name="execution_patterns",
            doc_id=doc_id,
            metadata={
                "type": "execution_pattern",
                "agent_id": agent.agentium_id,
                "task_type": task.title.split()[0] if task.title else "general",
                "success_rate": 1.0,
            }
        )
    
    def retroactive_constitution_check(self, action_description: str) -> Dict[str, Any]:
        """
        Post-hoc check: Did an action comply with Constitution?
        Used for auditing and reincarnation decisions.
        """
        # Query constitution for relevant articles
        results = self.vector_store.query_constitution(action_description, n_results=2)
        
        compliance_notes = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                # Simple keyword matching (in production, use LLM to evaluate)
                prohibited_keywords = ["violate", "ignore", "bypass", "unauthorized"]
                if any(kw in action_description.lower() for kw in prohibited_keywords):
                    compliance_notes.append({
                        "relevant_article": doc,
                        "compliance_status": "QUESTIONABLE",
                        "keywords_triggered": [kw for kw in prohibited_keywords if kw in action_description.lower()],
                        "distance": results['distances'][0][i] if results['distances'] else None
                    })
                else:
                    compliance_notes.append({
                        "relevant_article": doc,
                        "compliance_status": "LIKELY_COMPLIANT",
                        "distance": results['distances'][0][i] if results['distances'] else None
                    })
        
        return {
            "action": action_description,
            "checked_at": datetime.utcnow().isoformat(),
            "constitution_articles_checked": compliance_notes,
            "overall_compliance_estimate": "unknown" if not compliance_notes else (
                "compliant" if all(c['compliance_status'] == "LIKELY_COMPLIANT" for c in compliance_notes) else "violation_suspected"
            )
        }
    
    def initialize_knowledge_base(self, db: Session):
        """
        Bootstrap vector DB with current Constitution and Ethos.
        Call this on system startup.
        """
        from sqlalchemy import func
        
        # Embed active constitution
        active_const = db.query(Constitution).filter_by(is_active='Y').order_by(
            Constitution.version_number.desc()
        ).first()
        
        if active_const:
            self.embed_constitution(db, active_const)
            print(f"Embedded Constitution v{active_const.version}")
        
        # Embed verified ethos (batch for efficiency)
        ethos_batch = db.query(Ethos).filter_by(is_verified=True).all()
        for ethos in ethos_batch:
            try:
                self.embed_ethos(ethos)
            except Exception as e:
                print(f"Failed to embed ethos {ethos.id}: {e}")
        
        print(f"Embedded {len(ethos_batch)} agent ethos records")
        
        return {
            "constitution_embedded": active_const.version if active_const else None,
            "ethos_count": len(ethos_batch)
        }


# Singleton
_knowledge_service: Optional[KnowledgeService] = None


def get_knowledge_service() -> KnowledgeService:
    """Get singleton knowledge service."""
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service