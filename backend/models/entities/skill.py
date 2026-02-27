"""
Skill entity for ChromaDB and PostgreSQL dual-storage.
Defines the standardized skill schema.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, String, DateTime, JSON, Float, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from backend.models.entities.base import Base, BaseEntity


class SkillSchema(BaseModel):
    """
    Pydantic schema for skill validation - used for ALL skills in ChromaDB.
    Ensures consistent format across agent-created and Council-created skills.
    """
    
    # Identity
    skill_id: str = Field(..., pattern=r"skill_[0-6]xxxx_\d{3}")
    skill_name: str = Field(..., min_length=3, max_length=100)
    display_name: str = Field(..., min_length=5, max_length=200)
    
    # Categorization
    skill_type: str = Field(..., enum=[
        "code_generation", "analysis", "integration", 
        "automation", "research", "design", "testing", "deployment",
        "debugging", "optimization", "documentation"
    ])
    domain: str = Field(..., enum=[
        "frontend", "backend", "devops", "data", "ai", 
        "security", "mobile", "desktop", "general", "database", "api"
    ])
    tags: List[str] = Field(..., min_items=1, max_items=10)
    complexity: str = Field(..., enum=["beginner", "intermediate", "advanced"])
    
    # Content
    description: str = Field(..., min_length=50, max_length=2000)
    prerequisites: List[str] = Field(default_factory=list)
    steps: List[str] = Field(..., min_items=1)
    code_template: Optional[str] = None
    examples: List[Dict[str, str]] = Field(default_factory=list)
    common_pitfalls: List[str] = Field(default_factory=list)
    validation_criteria: List[str] = Field(..., min_items=1)
    
    # Provenance
    version: str = Field(default="1.0.0", pattern=r"\d+\.\d+\.\d+")
    created_at: datetime
    updated_at: datetime
    creator_tier: str = Field(..., enum=["head", "council", "lead", "task"])
    creator_id: str = Field(..., pattern=r"[0-6]xxxx")
    parent_skill_id: Optional[str] = None
    task_origin: Optional[str] = None  # task_id that created this skill
    
    # Quality Metrics
    success_rate: float = Field(..., ge=0.0, le=1.0)
    usage_count: int = Field(default=0, ge=0)
    retrieval_count: int = Field(default=0, ge=0)
    last_retrieved: Optional[datetime] = None
    
    # Governance
    constitution_compliant: bool
    verification_status: str = Field(..., enum=["pending", "verified", "rejected"])
    verified_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    
    # ChromaDB tracking
    chroma_collection: str = Field(default="agent_skills")
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    
    @validator('tags')
    def validate_tags(cls, v):
        return [tag.lower().strip() for tag in v]
    
    @validator('skill_name')
    def validate_skill_name(cls, v):
        return v.lower().replace(" ", "_").replace("-", "_")
    
    def to_chroma_document(self) -> str:
        """Convert to standardized text format for embedding."""
        # Build sections outside f-string to avoid backslash issues
        prereq_section = "\n".join(f"- {p}" for p in self.prerequisites) if self.prerequisites else "None"
        steps_section = "\n".join(f"{i+1}. {step}" for i, step in enumerate(self.steps))
        
        examples_section = ""
        if self.examples:
            examples_section = "\n\n".join(
                f"Example {i+1}:\nInput: {ex.get('input', 'N/A')}\nOutput: {ex.get('output', 'N/A')}"
                for i, ex in enumerate(self.examples)
            )
        else:
            examples_section = "N/A"
        
        pitfalls_section = "\n".join(f"- {p}" for p in self.common_pitfalls) if self.common_pitfalls else "None"
        criteria_section = "\n".join(f"- {c}" for c in self.validation_criteria) if self.validation_criteria else "None"
        
        return f"""Skill: {self.display_name}
            Name: {self.skill_name}
            Type: {self.skill_type}
            Domain: {self.domain}
            Complexity: {self.complexity}
            Description: {self.description}

            Prerequisites:
            {prereq_section}

            Steps:
            {steps_section}

            Code Template:
            {self.code_template or "N/A"}

            Examples:
            {examples_section}

            Common Pitfalls:
            {pitfalls_section}

            Validation Criteria:
            {criteria_section}

            Tags: {', '.join(self.tags)}
            Success Rate: {self.success_rate:.2%}
            Creator: {self.creator_tier} agent {self.creator_id}
            Version: {self.version}
            """.strip()
    
    def to_chroma_metadata(self) -> Dict[str, Any]:
        """Convert to ChromaDB metadata (JSON serializable)."""
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "display_name": self.display_name,
            "skill_type": self.skill_type,
            "domain": self.domain,
            "tags": self.tags,
            "complexity": self.complexity,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "creator_tier": self.creator_tier,
            "creator_id": self.creator_id,
            "parent_skill_id": self.parent_skill_id,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "constitution_compliant": self.constitution_compliant,
            "verification_status": self.verification_status,
            "verified_by": self.verified_by,
            "chroma_collection": self.chroma_collection,
        }


class SkillDB(BaseEntity):
    """
    SQLAlchemy model for skill metadata in PostgreSQL.
    References ChromaDB for full content.
    """
    __tablename__ = "skills"
    
    skill_id = Column(String(50), unique=True, nullable=False, index=True)
    skill_name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=False)
    skill_type = Column(String(50), nullable=False)
    domain = Column(String(50), nullable=False)
    tags = Column(JSON, default=list)
    complexity = Column(String(20), nullable=False)
    
    # ChromaDB reference
    chroma_id = Column(String(100), nullable=False)  # Full ID with version
    chroma_collection = Column(String(50), default="agent_skills")
    embedding_model = Column(String(100), default="sentence-transformers/all-MiniLM-L6-v2")
    
    # Provenance
    creator_tier = Column(String(20), nullable=False)
    creator_id = Column(String(20), nullable=False)
    parent_skill_id = Column(String(50), ForeignKey("skills.skill_id"), nullable=True)
    task_origin = Column(String(50), ForeignKey("tasks.agentium_id"), nullable=True)
    
    # Quality metrics
    success_rate = Column(Float, default=0.0)
    usage_count = Column(Integer, default=0)
    retrieval_count = Column(Integer, default=0)
    last_retrieved = Column(DateTime, nullable=True)
    
    # Governance
    constitution_compliant = Column(Boolean, default=False)
    verification_status = Column(String(20), default="pending")
    verified_by = Column(String(20), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(500), nullable=True)
    
    # Relationships
    parent_skill = relationship("SkillDB", remote_side=[skill_id], backref="derived_skills")
    
    def to_dict(self):
        return {
            "id": self.id,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "display_name": self.display_name,
            "skill_type": self.skill_type,
            "domain": self.domain,
            "tags": self.tags,
            "complexity": self.complexity,
            "chroma_id": self.chroma_id,
            "creator_tier": self.creator_tier,
            "creator_id": self.creator_id,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "verification_status": self.verification_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SkillSubmission(BaseEntity):
    """
    Pending skill submissions awaiting Council review.
    """
    __tablename__ = "skill_submissions"
    
    submission_id = Column(String(50), unique=True, nullable=False)
    skill_id = Column(String(50), ForeignKey("skills.skill_id"), nullable=False)
    submitted_by = Column(String(20), nullable=False)  # agentium_id
    submitted_at = Column(DateTime, default=datetime.utcnow)
    
    # Review status
    status = Column(String(20), default="pending")  # pending, under_review, approved, rejected
    council_vote_id = Column(String(50), nullable=True)  # Reference to voting record
    reviewed_by = Column(String(20), nullable=True)  # Council member who processed
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(String(1000), nullable=True)
    
    # Skill data snapshot (for review)
    skill_data = Column(JSON, nullable=False)