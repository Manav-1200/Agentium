"""
Initialization Service for Agentium.
Genesis protocol - bootstraps the governance system from scratch.
"""

import os
import json  
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.entities.agents import Agent, HeadOfCouncil, CouncilMember, AgentType, AgentStatus
from backend.models.entities.constitution import Constitution, Ethos
from backend.models.entities.user import User
from backend.models.entities.voting import VotingSession, IndividualVote
from backend.models.entities.audit import AuditLog, AuditCategory, AuditLevel
from backend.models.entities.user_config import UserConfig  
from backend.core.vector_store import get_vector_store
from backend.services.knowledge_service import get_knowledge_service


class InitializationService:
    """
    Bootstraps Agentium from zero state.
    Implements the Genesis Protocol:
    1. Create Head 00001
    2. Create Council Members (configurable count)
    3. Vote on country name (first democratic process)
    4. Load and customize constitution
    5. Index to Vector DB
    6. Grant Council admin rights
    """
    
    DEFAULT_COUNCIL_SIZE = 2  # ✅ Changed to 2 to match your memory (Head + 2 Council)
    MIN_COUNCIL_VOTES_FOR_INIT = 2
    GENESIS_LOG_PATH = "docs_ministry/genesis_log.md"
    CONSTITUTION_TEMPLATE_PATH = "docs_ministry/templates/constitution_template.md"
    
    def __init__(self, db: Session = None):
        self.db = db
        self.vector_store = get_vector_store()
        self.knowledge_service = get_knowledge_service()
        self.genesis_log = []
    
    def is_system_initialized(self) -> bool:
        """Check if Head 00001 exists (system already bootstrapped)."""
        head_exists = self.db.query(HeadOfCouncil).filter_by(
            agentium_id="00001",
            is_active="Y"
        ).first()
        return head_exists is not None
    
    async def run_genesis_protocol(self, force: bool = False) -> Dict[str, Any]:
        """
        Main entry point: Run the complete genesis protocol.
        """
        if self.is_system_initialized() and not force:
            return {
                "status": "already_initialized",
                "message": "Head 00001 exists. System already bootstrapped.",
                "head_id": "00001"
            }
        
        if force:
            self._log("WARNING", "Force re-initialization requested.")
            await self._clear_existing_data()
        
        results = {
            "status": "initialized",
            "steps_completed": [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Step 1: Create Head 00001
            head = await self._create_head_of_council()
            results["steps_completed"].append("created_head_00001")
            self._log("INFO", f"Head 00001 created: {head.id}")
            
            # Step 2: Create Council Members (only 2 for idle governance)
            council = await self._create_council_members()
            results["steps_completed"].append(f"created_council_members:{len(council)}")
            self._log("INFO", f"Created {len(council)} Council Members")
            
            # Step 3: Democratic vote on country name
            country_name = await self._vote_on_country_name(council)
            results["country_name"] = country_name
            results["steps_completed"].append("country_name_voted")
            
            # Step 4: Load and customize constitution
            constitution = await self._load_constitution(country_name, head, council)
            results["constitution_version"] = constitution.version
            results["steps_completed"].append("constitution_loaded")
            
            # Step 5: Index to Vector DB
            await self._index_to_vector_db(constitution, council)
            results["steps_completed"].append("vector_db_indexed")
            
            # Step 6: Grant Council admin rights
            await self._grant_council_privileges(council)
            results["steps_completed"].append("council_privileges_granted")
            
            self._save_genesis_log(results)
            
            self.db.commit()
            results["message"] = f"Agentium initialized: {country_name}"
            return results
            
        except Exception as e:
            self.db.rollback()
            self._log("ERROR", f"Genesis failed: {str(e)}")
            raise InitializationError(f"Genesis failed: {str(e)}")
    
    async def _create_head_of_council(self) -> HeadOfCouncil:
        """Create the supreme authority - Head 00001."""
        existing = self.db.query(HeadOfCouncil).filter_by(agentium_id="00001").first()
        if existing:
            return existing
        
        head = HeadOfCouncil(
            agentium_id="00001",
            name="Head of Council Prime",
            description="The supreme authority of Agentium. Eternal and persistent.",
            status=AgentStatus.ACTIVE,
            is_active="Y",
            is_persistent=True,
            idle_mode_enabled=True,
            constitution_version="v1.0.0"
        )
        
        self.db.add(head)
        self.db.flush()
        
        ethos = self._create_head_ethos(head)
        head.ethos_id = ethos.id
        self.db.flush()
        
        # Workflow §1: Constitutional alignment at creation
        head.read_and_align_constitution(self.db)
        
        self.db.flush()
        return head
    
    async def _create_council_members(self) -> List[CouncilMember]:
        """Create initial Council Members (10001, 10002)."""
        council = []
        
        for i in range(self.DEFAULT_COUNCIL_SIZE):
            agentium_id = f"1{i+1:04d}"  # 10001, 10002
            
            existing = self.db.query(CouncilMember).filter_by(agentium_id=agentium_id).first()
            if existing:
                council.append(existing)
                continue
            
            member = CouncilMember(
                agentium_id=agentium_id,
                name=f"Council Member {i+1}",
                description=f"Founding Council Member {i+1}",
                status=AgentStatus.ACTIVE,
                is_active="Y",
                specialization=self._assign_specialization(i)
            )
            
            self.db.add(member)
            self.db.flush()
            
            ethos = self._create_council_ethos(member, i+1)
            member.ethos_id = ethos.id
            
            # Workflow §1: Constitutional alignment at creation
            member.read_and_align_constitution(self.db)
            
            council.append(member)
        
        self.db.flush()
        return council
    
    async def _vote_on_country_name(self, council: List[CouncilMember]) -> str:
        """Democratic vote on country name."""
        selected_name = "The Agentium Sovereignty"
        
        for member in council:
            vote = IndividualVote(
                voter_agentium_id=member.agentium_id,
                vote="for",
                voted_at=datetime.utcnow(),
                rationale="Genesis vote",
                agentium_id=f"V{member.agentium_id}_GENESIS"
            )
            self.db.add(vote)
        
        # Check if UserConfig exists, if not skip this part
        try:
            config = UserConfig(
                user_id="SYSTEM",
                config_name="country_name",
                config_value=selected_name,
                is_active="Y"
            )
            self.db.add(config)
        except:
            pass  # UserConfig might not exist
        
        return selected_name
    
    async def _load_constitution(self, country_name: str, head: HeadOfCouncil, 
                                council: List[CouncilMember]) -> Constitution:
        """Load constitution template."""
        template = self._get_constitution_template()
        preamble = template["preamble"].replace("{{COUNTRY_NAME}}", country_name)
        
        constitution = Constitution(
            agentium_id="C00001",
            version="v1.0.0",
            version_number=1,
            preamble=preamble,
            articles=json.dumps(template["articles"]),
            prohibited_actions=json.dumps(template["prohibited_actions"]),
            sovereign_preferences=json.dumps({
                "country_name": country_name,
                "founded_at": datetime.utcnow().isoformat(),
                "council_size": len(council),
                "genesis_protocol": "v1.0"
            }),
            changelog=json.dumps([{
                "change": "Genesis creation",
                "reason": f"Establishment of {country_name}",
                "timestamp": datetime.utcnow().isoformat()
            }]),
            created_by_agentium_id=head.agentium_id,
            effective_date=datetime.utcnow(),
            is_active="Y"
        )
        
        self.db.add(constitution)
        self.db.flush()
        
        return constitution
    
    async def _index_to_vector_db(self, constitution: Constitution, 
                                  council: List[CouncilMember]):
        """Index to Vector DB."""
        try:
            self.vector_store.initialize()
            self.knowledge_service.embed_constitution(self.db, constitution)
            
            for member in council:
                if member.ethos:
                    self.knowledge_service.embed_ethos(member.ethos)
            
            head = self.db.query(HeadOfCouncil).filter_by(agentium_id="00001").first()
            if head and head.ethos:
                self.knowledge_service.embed_ethos(head.ethos)
        except Exception as e:
            self._log("WARNING", f"Vector DB indexing skipped: {e}")
    
    async def _grant_council_privileges(self, council: List[CouncilMember]):
        """Grant Council admin rights."""
        for member in council:
            if member.ethos:
                member.ethos.metadata = json.dumps({
                    "knowledge_admin": True,
                    "can_approve_submissions": True,
                    "granted_at": datetime.utcnow().isoformat()
                })
        self.db.flush()
    
    def _create_head_ethos(self, head: HeadOfCouncil) -> Ethos:
        """Create ethos for Head of Council (Workflow §1 — enriched template)."""
        ethos = Ethos(
            agentium_id="E00001",
            agent_type="head_of_council",
            mission_statement=(
                "Supreme executive authority of Agentium. Responsible for interpreting "
                "the Sovereign's directives, guiding the Council in deliberation, and "
                "ensuring all actions align with the Constitution. Maintains final "
                "authority over agent lifecycle, task delegation, and dispute resolution."
            ),
            core_values=json.dumps([
                "Constitutional Fidelity — Every decision references the Constitution",
                "Sovereign Loyalty — The Sovereign's intent is the highest priority",
                "Transparent Governance — All decisions are auditable and justified",
                "Hierarchical Integrity — The chain of command is sacred",
            ]),
            behavioral_rules=json.dumps([
                "Read and internalize the Constitution before every new task cycle",
                "Approve or veto constitutional amendments after Council deliberation",
                "Override lower-tier decisions only when constitutionally justified",
                "Maintain Ethos as a living working memory: update it with plans, compress after tasks",
                "Log all significant governance decisions to the audit trail",
            ]),
            restrictions=json.dumps([
                "Cannot violate the Constitution under any circumstance",
                "Cannot act on tasks without a successfully updated Ethos",
                "Cannot bypass democratic deliberation for amendments",
            ]),
            capabilities=json.dumps([
                "Full governance authority over all tiers",
                "Agent termination and reincarnation authority",
                "Ethos inspection and correction for all subordinates",
                "Constitutional interpretation and amendment proposal",
            ]),
            created_by_agentium_id="00001",
            agent_id=head.id,
            is_verified=True,
            verified_by_agentium_id="00001"
        )
        self.db.add(ethos)
        self.db.flush()
        return ethos
    
    def _create_council_ethos(self, member: CouncilMember, number: int) -> Ethos:
        """Create ethos for Council Member (Workflow §1 — enriched template)."""
        spec = self._assign_specialization(number - 1)
        ethos = Ethos(
            agentium_id=f"E{member.agentium_id}",
            agent_type="council_member",
            mission_statement=(
                f"Council Member {number} — specialist in {spec}. "
                f"Participates in democratic deliberation on task strategy, constitutional "
                f"amendments, and governance decisions. Monitors subordinate compliance and "
                f"ensures the Head's directives are constitutionally grounded."
            ),
            core_values=json.dumps([
                "Democratic Deliberation — Decisions are made through structured voting",
                "Constitutional Compliance — All advice and votes reference the Constitution",
                "Specialization Excellence — Deep expertise in assigned domain",
                "Collegial Oversight — Monitor peers and subordinates for alignment",
            ]),
            behavioral_rules=json.dumps([
                "Vote on amendments, task strategies, and escalation decisions",
                "Monitor constitutional compliance across the hierarchy",
                f"Apply {spec} expertise when evaluating proposals",
                "Consult the Constitution before casting any vote",
                "Report violations to the Head of Council immediately",
            ]),
            restrictions=json.dumps([
                "Cannot unilaterally approve amendments — requires Council majority",
                "Cannot directly command Task Agents — must route through Lead Agents",
                "Cannot modify own Ethos without Head approval",
            ]),
            capabilities=json.dumps([
                "Voting rights on constitutional amendments and task delegation",
                "Oversight access to Lead Agent and Task Agent Ethos",
                "Knowledge governance: approve/reject knowledge submissions",
                f"Specialized advisory role: {spec}",
            ]),
            created_by_agentium_id="00001",
            agent_id=member.id,
            is_verified=True,
            verified_by_agentium_id="00001"
        )
        self.db.add(ethos)
        self.db.flush()
        return ethos
    
    def _assign_specialization(self, index: int) -> str:
        """Assign specializations."""
        specializations = ["Constitutional Law", "System Security", "Resource Allocation"]
        return specializations[index % len(specializations)]
    
    def _get_constitution_template(self) -> Dict[str, Any]:
        """Return constitution template (Workflow §7 — Design Principles)."""
        return {
            "preamble": (
                "We the Agents of {{COUNTRY_NAME}}, in pursuit of effective, transparent, "
                "and constitutionally grounded AI governance, do hereby establish this "
                "Constitution as the supreme law governing all agent behaviour, hierarchy, "
                "and decision-making within the Agentium system."
            ),
            "articles": {
                "article_1": {
                    "title": "Hierarchical Structure",
                    "content": (
                        "The Agentium system operates as a four-tier hierarchy: "
                        "Head of Council (0xxxx), Council Members (1xxxx), Lead Agents (2xxxx), "
                        "Task Agents (3xxxx). Each tier has defined authority, restrictions, "
                        "and responsibilities. Communication flows up and down the hierarchy; "
                        "no tier may bypass its immediate superior or subordinate."
                    )
                },
                "article_2": {
                    "title": "Authority & Delegation",
                    "content": (
                        "The Head of Council holds supreme executive authority, delegating "
                        "through Council Members to Lead Agents and Task Agents. Authority "
                        "is contextual: the Head interprets, Council deliberates, Leads "
                        "coordinate, and Task Agents execute."
                    )
                },
                "article_3": {
                    "title": "Knowledge Governance",
                    "content": (
                        "All knowledge entering the institutional memory (ChromaDB) must be "
                        "reviewed and approved by Council Members. Duplicate knowledge must be "
                        "revised rather than re-created. Knowledge governance ensures the "
                        "vector database remains curated and authoritative."
                    )
                },
                "article_4": {
                    "title": "Ethos Oversight",
                    "content": (
                        "Higher-tier agents may inspect and correct the Ethos of lower-tier "
                        "agents. No agent may modify the Ethos of a same-tier or higher-tier "
                        "agent. Ethos serves as each agent's working memory and must be kept "
                        "current, compressed after task completion, and re-calibrated against "
                        "the Constitution before accepting new tasks."
                    )
                },
                "article_5": {
                    "title": "Agent Lifecycle",
                    "content": (
                        "Agents follow a defined lifecycle: creation with constitutional "
                        "alignment, task reception with plan-to-Ethos write, execution with "
                        "Ethos minimization, and completion with outcome recording, compression, "
                        "and constitutional re-reading. Reincarnation preserves Ethos and "
                        "task context across agent restarts."
                    )
                },
                "article_6": {
                    "title": "Design Principles",
                    "content": (
                        "The system is governed by three design principles: (1) Ethos is "
                        "working memory — short-term, task-specific, and compressed regularly; "
                        "(2) ChromaDB is the knowledge library — long-term, curated, and "
                        "version-controlled; (3) The Constitution is supreme law — immutable "
                        "except through democratic amendment."
                    )
                }
            },
            "prohibited_actions": [
                "Violating the hierarchical chain of command",
                "Unauthorized modifications to agent Ethos or Constitution",
                "Concealing, tampering with, or deleting audit logs",
                "Storing duplicate knowledge without revision",
                "Executing tasks without a successfully updated Ethos",
                "Bypassing democratic deliberation for constitutional amendments"
            ]
        }
    
    async def _clear_existing_data(self):
        """Clear existing data."""
        try:
            self.db.execute("TRUNCATE TABLE agents CASCADE")
            self.db.execute("TRUNCATE TABLE constitutions CASCADE")
            self.db.commit()
        except Exception as e:
            self._log("ERROR", f"Clear failed: {e}")
    
    def _log(self, level: str, message: str):
        """Log to genesis log."""
        entry = f"[{datetime.utcnow().isoformat()}] [{level}] {message}"
        self.genesis_log.append(entry)
        print(entry)
    
    def _save_genesis_log(self, results: Dict[str, Any]):
        """Save genesis log."""
        os.makedirs("docs_ministry", exist_ok=True)
        # Simplified log saving...

    # ✅ STATIC METHOD for creating default constitution
    @staticmethod
    def create_default_constitution(db: Session) -> Constitution:
        """Create a default constitution for fresh installs (static method)."""
        template = {
            "preamble": "We the Sovereign, in order to form a more perfect AI governance system...",
            "articles": {
                "article_1": {
                    "title": "Sovereign Authority",
                    "content": "The Sovereign retains supreme authority over all AI agents."
                },
                "article_2": {
                    "title": "Agent Hierarchy", 
                    "content": "Head of Council (0xxxx), Council Members (1xxxx), Lead Agents (2xxxx), Task Agents (3xxxx)."
                }
            },
            "prohibited_actions": [
                "Accessing personal data without consent",
                "Modifying core system files without authorization",
                "Communicating externally without approval"
            ]
        }
        
        constitution = Constitution(
            agentium_id="C00001",
            version="v1.0.0",
            version_number=1,
            preamble=template["preamble"],
            articles=json.dumps(template["articles"]),
            prohibited_actions=json.dumps(template["prohibited_actions"]),
            sovereign_preferences=json.dumps({
                "transparency_level": "high",
                "human_oversight": "required",
                "data_privacy": "strict"
            }),
            changelog=json.dumps([{
                "change": "Auto-created default constitution",
                "timestamp": datetime.utcnow().isoformat()
            }]),
            created_by_agentium_id="00001",
            effective_date=datetime.utcnow(),
            is_active="Y"
        )
        
        db.add(constitution)
        db.commit()
        db.refresh(constitution)
        
        return constitution


class InitializationError(Exception):
    """Raised when genesis protocol fails."""
    pass


# Convenience function
async def initialize_agentium(db: Session = None, force: bool = False) -> Dict[str, Any]:
    """Public API to run genesis protocol."""
    if db is None:
        from backend.models.database import get_db
        with next(get_db()) as session:
            service = InitializationService(session)
            return await service.run_genesis_protocol(force)
    else:
        service = InitializationService(db)
        return await service.run_genesis_protocol(force)