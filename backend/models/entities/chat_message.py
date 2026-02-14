"""
Chat message entity for persistent conversation history.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import uuid

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, JSON, Integer, Index
from sqlalchemy.orm import relationship

from backend.models.entities.base import Base   


class ChatMessage(Base):
    """Persistent chat message storage."""
    
    __tablename__ = "chat_messages"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Conversation grouping
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=True)
    
    # User who sent/received the message – CHANGED to Integer
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Message metadata
    role = Column(String(50), nullable=False)  # 'sovereign', 'head_of_council', 'system'
    content = Column(Text, nullable=False)
    
    # Optional attachments (files, images, etc.)
    attachments = Column(JSON, nullable=True)
    
    # Additional metadata
    message_metadata = Column(JSON, nullable=True)
    
    # Agent that generated the response
    agent_id = Column(String(50), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    # Soft delete
    is_deleted = Column(String(1), default='N')
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    user = relationship("User", back_populates="chat_messages")
    
    # Indexes ...
    __table_args__ = (
        Index('idx_chat_user_created', 'user_id', 'created_at'),
        Index('idx_chat_conversation', 'conversation_id', 'created_at'),
        Index('idx_chat_role', 'role'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "attachments": self.attachments,
            "metadata": self.message_metadata,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def create_user_message(
        cls,
        user_id: str,
        content: str,
        conversation_id: Optional[str] = None,
        attachments: Optional[list] = None
    ) -> "ChatMessage":
        """Factory method for user messages."""
        return cls(
            user_id=user_id,
            role="sovereign",
            content=content,
            conversation_id=conversation_id,
            attachments=attachments,
            message_metadata={"source": "web"}
        )
    
    @classmethod
    def create_agent_message(
        cls,
        user_id: str,
        content: str,
        agent_id: str,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> "ChatMessage":
        """Factory method for agent messages."""
        return cls(
            user_id=user_id,
            role="head_of_council",
            content=content,
            agent_id=agent_id,
            conversation_id=conversation_id,
            message_metadata=metadata
        )
    
    @classmethod
    def create_system_message(
        cls,
        user_id: str,
        content: str,
        conversation_id: Optional[str] = None
    ) -> "ChatMessage":
        """Factory method for system messages."""
        return cls(
            user_id=user_id,
            role="system",
            content=content,
            conversation_id=conversation_id,
            message_metadata={"source": "system"}
        )


class Conversation(Base):
    """Conversation session grouping."""
    
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # CHANGED to Integer to match users.id
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Conversation metadata
    title = Column(String(200), nullable=True)  # Auto-generated or user-set
    context = Column(Text, nullable=True)  # Summary of conversation purpose
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, default=datetime.utcnow)
    
    # Soft delete
    is_deleted = Column(String(1), default='N')
    is_archived = Column(String(1), default='N')
    
    # Relationships
    messages = relationship("ChatMessage", back_populates="conversation", order_by="ChatMessage.created_at")
    user = relationship("User", back_populates="conversations")
    
    # Indexes
    __table_args__ = (
        Index('idx_conv_user_updated', 'user_id', 'updated_at'),
        Index('idx_conv_last_message', 'last_message_at'),
    )
    
    def to_dict(self, include_messages: bool = False) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "message_count": len(self.messages) if self.messages else 0,
        }
        
        if include_messages and self.messages:
            result["messages"] = [m.to_dict() for m in self.messages if m.is_deleted == 'N']
        
        return result
    
    def update_last_message_time(self):
        """Update the last message timestamp."""
        self.last_message_at = datetime.utcnow()