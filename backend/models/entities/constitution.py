"""
Constitution and Ethos management for Agentium.
The Constitution is the supreme law, while Ethos defines individual agent behavior.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Enum, Boolean, event, Index
from sqlalchemy.orm import relationship, validates
from backend.models.entities.base import BaseEntity
from sqlalchemy.orm import remote
from sqlalchemy.orm import remote, foreign
import enum

class DocumentType(str, enum.Enum):
    """Types of governance documents."""
    CONSTITUTION = "constitution"
    ETHOS = "ethos"



class Constitution(BaseEntity):
    """
    The Supreme Law of Agentium.
    - Only Head of Council (0xxxx) can modify
    - Updated daily via voting process
    - Read-only for all other entities
    - Supports amendment chaining via replaces_version_id
    """
    
    __tablename__ = 'constitutions'
    
    # Document metadata
    version = Column(String(10), nullable=False, unique=True)  # v1.0.0 format (display)
    version_number = Column(Integer, nullable=False, unique=True)  # Sequential: 1, 2, 3...
    document_type = Column(Enum(DocumentType), default=DocumentType.CONSTITUTION, nullable=False)
    
    # Content sections
    preamble = Column(Text, nullable=True)
    articles = Column(Text, nullable=False)  # JSON string of articles
    prohibited_actions = Column(Text, nullable=False)  # JSON array
    sovereign_preferences = Column(Text, nullable=False)  # JSON object - User's preferences
    changelog = Column(Text, nullable=True)  # JSON array documenting changes from previous version
    
    effective_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    amendment_date = Column(DateTime, nullable=True)
    archived_date = Column(DateTime, nullable=True)
    # Authority
    created_by_agentium_id = Column(String(10), nullable=False)  # Usually 00001 (Head of Council)
    
    amendment_of = Column(String(36), ForeignKey('constitutions.id'), nullable=True)
    replaces_version_id = Column(String(36), ForeignKey('constitutions.id'), nullable=True)
    amended_from = relationship(
        "Constitution",
        foreign_keys=[amendment_of],
        remote_side=lambda: Constitution.id,  # Use lambda for deferred evaluation
        back_populates="amendments",
    )

    # Amendments that amend this constitution (one-to-many side) - parent pointing to children
    amendments = relationship(
        "Constitution",
        foreign_keys=[amendment_of],
        back_populates="amended_from",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Version replacement relationships
    # This constitution replaces a previous version (many-to-one)
    replaces_version = relationship(
        "Constitution",
        foreign_keys=[replaces_version_id],
        remote_side=lambda: Constitution.id,  # Use lambda for deferred evaluation
        back_populates="replaced_by",
    )

    # Newer versions that replace this one (one-to-many)
    replaced_by = relationship(
        "Constitution",
        foreign_keys=[replaces_version_id],
        back_populates="replaces_version",
        lazy="dynamic",
    )

    voting_sessions = relationship("AmendmentVoting", back_populates="amendment")
    
    def __init__(self, **kwargs):
        # Auto-generate version strings if not provided
        if 'version' not in kwargs and 'version_number' in kwargs:
            kwargs['version'] = f"v{kwargs['version_number']}.0.0"
        elif 'version' not in kwargs:
            kwargs['version'] = f"v{datetime.utcnow().strftime('%Y.%m.%d.%H%M')}"
        
        # Auto-generate version_number if not provided (get next sequential)
        if 'version_number' not in kwargs:
            # This should be handled by service layer, but default to 1
            kwargs['version_number'] = 1
            
        super().__init__(**kwargs)
    
    @validates('version')
    def validate_version(self, key, version):
        if not version.startswith('v'):
            raise ValueError("Version must start with 'v'")
        return version
    
    @validates('version_number')
    def validate_version_number(self, key, version_number):
        if version_number < 1:
            raise ValueError("Version number must be positive integer")
        return version_number
    
    def get_articles_dict(self) -> Dict[str, Any]:
        """Parse articles JSON to dictionary with normalized article structure."""
        import json
        try:
            articles = json.loads(self.articles) if self.articles else {}
        except json.JSONDecodeError:
            return {}
        
        # Normalize: ensure all article values are {title, content} dicts, not strings
        normalized = {}
        for key, val in articles.items():
            if isinstance(val, str):
                # Convert string content to proper structure
                pretty_title = key.replace("_", " ").title()
                normalized[key] = {"title": pretty_title, "content": val}
            elif isinstance(val, dict):
                # Already a dict, ensure it has required keys
                normalized[key] = {
                    "title": val.get("title", key.replace("_", " ").title()),
                    "content": val.get("content", "")
                }
            else:
                # Unknown type, create empty structure
                normalized[key] = {"title": key.replace("_", " ").title(), "content": str(val) if val else ""}
        
        return normalized
    
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
    
    def get_changelog(self) -> List[Dict[str, Any]]:
        """Parse changelog to list of changes."""
        import json
        try:
            return json.loads(self.changelog) if self.changelog else []
        except json.JSONDecodeError:
            return []
    
    def get_amendment_chain(self) -> List['Constitution']:
        """Get chain of constitutions leading to this one (oldest first)."""
        chain = []
        current = self
        while current.replaces_version:
            chain.insert(0, current.replaces_version)
            current = current.replaces_version
        chain.append(self)
        return chain
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'version': self.version,
            'version_number': self.version_number,
            'document_type': self.document_type.value,
            'preamble': self.preamble,
            'articles': self.get_articles_dict(),
            'prohibited_actions': self.get_prohibited_actions_list(),
            'sovereign_preferences': self.get_sovereign_preferences(),
            'changelog': self.get_changelog(),
            'created_by': self.created_by_agentium_id,
            'amendment_date': self.amendment_date.isoformat() if self.amendment_date else None,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'replaces_version': self.replaces_version.version if self.replaces_version else None,
            'is_archived': self.archived_date is not None,
            'is_active': self.is_active
        })
        return base
    
    def archive(self):
        """Archive this constitution version when new one takes effect."""
        self.archived_date = datetime.utcnow()
        self.is_active = False

        # Table indexes for Phase 0 verification
    __table_args__ = (
        Index('idx_constitution_version', 'version'),           # Quick version lookup
        Index('idx_constitution_version_number', 'version_number'),  # Chronological sorting
        Index('idx_constitution_active', 'is_active'),          # Active constitution queries
        Index('idx_constitution_effective', 'effective_date'),  # Effective date queries
    )


class Ethos(BaseEntity):
    """
    Individual Agent Ethos — the agent's working memory.

    A dynamic, minimal, continuously updated internal state containing:
      - Core identity (mission, values, rules, restrictions, capabilities)
      - Current objective and active plan
      - Relevant constitutional references
      - Temporary reasoning artifacts
      - Task progress markers
      - Outcome summaries and lessons learned

    Created by higher authority, updated by the agent itself, verified by lead.
    Ethos is short-term working cognition; ChromaDB is long-term institutional memory.
    """
    
    __tablename__ = 'ethos'
    
    # Identification
    agent_type = Column(String(20), nullable=False)  # head_of_council, council_member, lead_agent, task_agent
    # agentium_id inherited from BaseEntity (NOT NULL). Format: E0xxxx, E1xxxx for ethos
    
    # Core Identity Content
    mission_statement = Column(Text, nullable=False)
    core_values = Column(Text, nullable=False)  # JSON array
    behavioral_rules = Column(Text, nullable=False)  # JSON array of do's
    restrictions = Column(Text, nullable=False)  # JSON array of don'ts
    capabilities = Column(Text, nullable=False)  # JSON array of what this agent can do
    
    # Working Memory Fields (Workflow §1-§5)
    current_objective = Column(Text, nullable=True)               # Active task objective
    active_plan = Column(Text, nullable=True)                     # JSON: structured execution plan
    constitutional_references = Column(Text, nullable=True)       # JSON: relevant constitutional sections/summary
    task_progress_markers = Column(Text, nullable=True)           # JSON: sub-step progress tracking
    reasoning_artifacts = Column(Text, nullable=True)             # JSON: temporary reasoning notes
    outcome_summary = Column(Text, nullable=True)                 # Last task outcome summary
    lessons_learned = Column(Text, nullable=True)                 # JSON: accumulated lessons
    
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
    
    # --- Working Memory Accessors (Workflow §1-§5) ---
    
    def get_active_plan(self) -> Optional[Dict[str, Any]]:
        """Get the current structured execution plan."""
        import json
        try:
            return json.loads(self.active_plan) if self.active_plan else None
        except json.JSONDecodeError:
            return None
    
    def set_active_plan(self, plan: Dict[str, Any]):
        """Write a structured execution plan into the Ethos."""
        import json
        self.active_plan = json.dumps(plan)
        self.increment_version()
    
    def get_constitutional_references(self) -> List[Dict[str, Any]]:
        """Get relevant constitutional section references."""
        import json
        try:
            return json.loads(self.constitutional_references) if self.constitutional_references else []
        except json.JSONDecodeError:
            return []
    
    def set_constitutional_references(self, references: List[Dict[str, Any]]):
        """Update constitutional references in the Ethos."""
        import json
        self.constitutional_references = json.dumps(references)
    
    def get_task_progress(self) -> Dict[str, Any]:
        """Get task progress markers."""
        import json
        try:
            return json.loads(self.task_progress_markers) if self.task_progress_markers else {}
        except json.JSONDecodeError:
            return {}
    
    def set_task_progress(self, progress: Dict[str, Any]):
        """Update task progress markers."""
        import json
        self.task_progress_markers = json.dumps(progress)
    
    def get_reasoning_artifacts(self) -> List[str]:
        """Get temporary reasoning artifacts."""
        import json
        try:
            return json.loads(self.reasoning_artifacts) if self.reasoning_artifacts else []
        except json.JSONDecodeError:
            return []
    
    def get_lessons_learned(self) -> List[Dict[str, Any]]:
        """Get accumulated lessons learned."""
        import json
        try:
            return json.loads(self.lessons_learned) if self.lessons_learned else []
        except json.JSONDecodeError:
            return []
    
    def add_lesson_learned(self, lesson: Dict[str, Any]):
        """Append a lesson learned entry."""
        import json
        lessons = self.get_lessons_learned()
        lessons.append(lesson)
        # Keep only the last 20 lessons to prevent unbounded growth
        self.lessons_learned = json.dumps(lessons[-20:])
    
    def compress(self):
        """
        Compress the Ethos by removing obsolete working state.
        Retains core identity (mission, values, rules, restrictions, capabilities)
        and outcome/lessons. Clears transient execution artifacts.
        Called after task completion (Workflow §5).
        """
        self.active_plan = None
        self.task_progress_markers = None
        self.reasoning_artifacts = None
        self.current_objective = None
        self.increment_version()
    
    def clear_working_state(self):
        """
        Fully reset the working state for a fresh task cycle.
        Preserves: mission, values, rules, restrictions, capabilities,
                   constitutional_references, lessons_learned, outcome_summary.
        Clears: objective, plan, progress, reasoning artifacts.
        Called during post-task recalibration (Workflow §5.4).
        """
        self.current_objective = None
        self.active_plan = None
        self.task_progress_markers = None
        self.reasoning_artifacts = None

    # -----------------------------------------------------------------------
    # Idle-time Ethos Compression (Workflow §IDLE)
    # -----------------------------------------------------------------------

    def _build_activity_snapshot(self) -> Dict[str, Any]:
        """
        Build a structured snapshot of what this agent is currently doing.
        Captures the 25% 'what is happening now' summary written to outcome_summary
        during idle compression.
        """
        active_plan = self.get_active_plan()
        progress = self.get_task_progress()
        lessons = self.get_lessons_learned()
        artifacts = self.get_reasoning_artifacts()
        refs = self.get_constitutional_references()

        # Summarise active plan at a high level
        plan_summary = None
        if active_plan:
            plan_summary = {
                "title": active_plan.get("title") or active_plan.get("objective"),
                "step_count": len(active_plan.get("steps", [])),
                "status": active_plan.get("status"),
            }

        # Collapse progress markers into a lightweight overview
        progress_overview = {
            "total_steps": len(progress),
            "completed": sum(1 for v in progress.values() if v in (True, "done", "completed")),
            "step_keys": list(progress.keys()),
        } if progress else None

        # Extract the most recent lesson key points (last 3 raw, rest as count)
        recent_lesson_points = []
        for lesson in lessons[-3:]:
            point = lesson.get("key_point") or lesson.get("lesson") or lesson.get("summary")
            if point:
                recent_lesson_points.append(str(point)[:120])

        # Summarise constitutional references (section titles only)
        ref_titles = list({
            ref.get("title") or ref.get("section_id") or str(ref)[:40]
            for ref in refs
            if ref
        })

        return {
            "snapshot_at": datetime.utcnow().isoformat(),
            "agent_type": self.agent_type,
            "current_objective": self.current_objective,
            "active_plan": plan_summary,
            "progress": progress_overview,
            "reasoning_artifact_count": len(artifacts),
            "total_lessons": len(lessons),
            "recent_lesson_points": recent_lesson_points,
            "constitutional_refs": ref_titles,
            "ethos_version": self.version,
        }

    def _compress_reasoning_artifacts(self) -> None:
        """
        Compress reasoning artifacts: collapse the oldest 75% into a single
        compressed entry, keep the newest 25% raw.
        Minimum threshold: only compress if more than 4 artifacts exist.
        """
        import json

        artifacts = self.get_reasoning_artifacts()
        if len(artifacts) <= 4:
            return

        # Split: oldest 75% get compressed, newest 25% stay raw
        keep_raw_count = max(1, len(artifacts) * 25 // 100)
        old_artifacts = artifacts[:-keep_raw_count]
        recent_artifacts = artifacts[-keep_raw_count:]

        # Merge old ones into a single compressed entry
        compressed_entry = {
            "type": "compressed_reasoning",
            "compressed_at": datetime.utcnow().isoformat(),
            "original_count": len(old_artifacts),
            # Truncate each to 100 chars and join as a readable digest
            "digest": " | ".join(str(a)[:100] for a in old_artifacts),
        }

        self.reasoning_artifacts = json.dumps([compressed_entry] + recent_artifacts)

    def _compress_lessons_learned(self) -> None:
        """
        Compress lessons learned: collapse the oldest 75% into a consolidated
        entry extracting unique key patterns, keep the newest 25% raw.
        Minimum threshold: only compress if more than 4 lessons exist.
        """
        import json

        lessons = self.get_lessons_learned()
        if len(lessons) <= 4:
            return

        # Split: oldest 75% get consolidated, newest 25% stay raw
        keep_raw_count = max(1, len(lessons) * 25 // 100)
        old_lessons = lessons[:-keep_raw_count]
        recent_lessons = lessons[-keep_raw_count:]

        # Extract unique key patterns from old lessons
        key_patterns = list({
            l.get("key_point") or l.get("lesson") or l.get("summary") or str(l)[:80]
            for l in old_lessons
            if l
        })

        consolidated_entry = {
            "type": "consolidated_lessons",
            "compressed_at": datetime.utcnow().isoformat(),
            "source_count": len(old_lessons),
            "key_patterns": key_patterns,
        }

        self.lessons_learned = json.dumps([consolidated_entry] + recent_lessons)

    def _deduplicate_constitutional_references(self) -> None:
        """
        Deduplicate constitutional references, keeping the most recent occurrence
        of each unique section. Preserves order (most recently seen wins).
        """
        import json

        refs = self.get_constitutional_references()
        if not refs:
            return

        seen: Dict[str, Any] = {}
        for ref in refs:
            key = ref.get("section_id") or ref.get("title") or str(ref)[:60]
            seen[key] = ref  # last occurrence wins, deduplicates cleanly

        self.constitutional_references = json.dumps(list(seen.values()))

    def prune_obsolete_content(self, completed_steps: List[str] = None):
        """
        Idle-time ethos compression using a 75/25 strategy:

          75% — Compress historical data:
            - Collapse oldest 75% of reasoning_artifacts into a compressed digest
            - Consolidate oldest 75% of lessons_learned into key patterns
            - Deduplicate constitutional_references
            - Remove explicitly completed progress markers

          25% — Summarise current activity:
            - Build a structured snapshot of what the agent is doing right now
            - Write it to outcome_summary so higher-tier agents and future task
              cycles have readable context on this agent's recent state

        Called during idle ETHOS_OPTIMIZATION task (Workflow §IDLE).
        Also called after sub-steps when completed_steps is provided (Workflow §3).
        """
        import json

        # ── Step 1: Remove explicitly completed progress markers ────────────────
        if completed_steps and self.task_progress_markers:
            progress = self.get_task_progress()
            for step in completed_steps:
                progress.pop(step, None)
            self.task_progress_markers = json.dumps(progress) if progress else None

        # ── Step 2 (75%): Compress reasoning artifacts ──────────────────────────
        self._compress_reasoning_artifacts()

        # ── Step 3 (75%): Consolidate lessons learned ───────────────────────────
        self._compress_lessons_learned()

        # ── Step 4 (75%): Deduplicate constitutional references ─────────────────
        self._deduplicate_constitutional_references()

        # ── Step 5 (25%): Write activity snapshot to outcome_summary ────────────
        # Only build the snapshot during true idle compression (no specific steps
        # were passed), so we don't overwrite outcome_summary mid-task.
        if not completed_steps:
            snapshot = self._build_activity_snapshot()
            self.outcome_summary = json.dumps(snapshot)

        # ── Bump version to record the compression ───────────────────────────────
        self.increment_version()

    def get_outcome_snapshot(self) -> Optional[Dict[str, Any]]:
        """
        Parse outcome_summary as a snapshot dict if it was written by
        prune_obsolete_content. Falls back to returning the raw string
        wrapped in a dict if it's plain text from an older format.
        """
        import json
        if not self.outcome_summary:
            return None
        try:
            parsed = json.loads(self.outcome_summary)
            if isinstance(parsed, dict):
                return parsed
            return {"raw": self.outcome_summary}
        except (json.JSONDecodeError, TypeError):
            return {"raw": self.outcome_summary}

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'agent_type': self.agent_type,
            'agentium_id': self.agentium_id,
            'mission_statement': self.mission_statement,
            'core_values': self.get_core_values(),
            'behavioral_rules': self.get_behavioral_rules(),
            'restrictions': self.get_restrictions(),
            'capabilities': self.get_capabilities(),
            'current_objective': self.current_objective,
            'active_plan': self.get_active_plan(),
            'constitutional_references': self.get_constitutional_references(),
            'task_progress': self.get_task_progress(),
            'outcome_summary': self.get_outcome_snapshot(),
            'lessons_learned': self.get_lessons_learned(),
            'version': self.version,
            'created_by': self.created_by_agentium_id,
            'verified': self.is_verified,
            'verified_by': self.verified_by_agentium_id,
            'agent_id': self.agent_id
        })
        return base


@event.listens_for(Constitution, 'after_insert')
def log_constitution_creation(mapper, connection, target):
    """Log when a new constitution is created."""
    from backend.models.entities.audit import AuditLog, AuditLevel, AuditCategory
    # Create audit log entry
    audit = AuditLog(
        level=AuditLevel.INFO,
        category=AuditCategory.GOVERNANCE,
        actor_type="system",
        actor_id=target.created_by_agentium_id,
        action="constitution_created",
        target_type="constitution",
        target_id=target.agentium_id,
        description=f"Constitution v{target.version} (revision {target.version_number}) created",  # FIXED
        after_state={
            'version': target.version,
            'version_number': target.version_number,
            'effective_date': target.effective_date.isoformat() if target.effective_date else None
        },
        created_at=datetime.utcnow()
    )
    # Note: In actual implementation, you'd add this to the session
    # But in event listeners, we use connection.execute or similar

@event.listens_for(Ethos, 'after_update')
def log_ethos_update(mapper, connection, target):
    """Log when an ethos is modified."""
    if target.last_updated_by_agent:
        target.last_updated_by_agent = False  # Reset for next time