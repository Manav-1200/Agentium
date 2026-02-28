import uuid
import hashlib
import base64

from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.orm import Session, relationship
from passlib.context import CryptContext

from backend.models.entities.base import Base


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _new_uuid() -> str:
    """Generate a new UUID4 string. Used as the default for User.id."""
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    # String UUID primary key — matches the VARCHAR(36) column created by
    # migration 001. The default= ensures Python always supplies a value so
    # SQLAlchemy never sends NULL in the INSERT.
    id = Column(String(36), primary_key=True, default=_new_uuid, index=True)

    username         = Column(String(50),  unique=True, index=True, nullable=False)
    email            = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password  = Column(String(255), nullable=False)
    is_active        = Column(Boolean, default=False,  nullable=False)
    is_admin         = Column(Boolean, default=False,  nullable=False)
    is_pending       = Column(Boolean, default=True,   nullable=False)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    chat_messages = relationship(
        "ChatMessage",
        back_populates="user",
        order_by="ChatMessage.created_at.desc()",
    )
    conversations = relationship(
        "Conversation",
        back_populates="user",
        order_by="Conversation.updated_at.desc()",
    )

    # ------------------------------------------------------------------ #
    #  Password helpers                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _prehash_password(password: str) -> str:
        """
        Pre-hash with SHA-256 before bcrypt to support passwords > 72 bytes
        without silently truncating entropy.
        """
        sha256_hash = hashlib.sha256(password.encode("utf-8")).digest()
        return base64.b64encode(sha256_hash).decode("ascii")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against its stored bcrypt hash."""
        prehashed = User._prehash_password(plain_password)
        return pwd_context.verify(prehashed, hashed_password)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password for storage (SHA-256 pre-hash + bcrypt)."""
        prehashed = User._prehash_password(password)
        return pwd_context.hash(prehashed)

    # ------------------------------------------------------------------ #
    #  Class-level DB helpers                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def create_user(
        cls,
        db: Session,
        username: str,
        email: str,
        password: str,
        is_admin: bool = False,
        is_active: bool = False,
        is_pending: bool = True,
    ) -> "User":
        """Create a new user with a hashed password and commit."""
        user = cls(
            username=username,
            email=email,
            hashed_password=cls.hash_password(password),
            is_active=is_active,
            is_admin=is_admin,
            is_pending=is_pending,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @classmethod
    def authenticate(cls, db: Session, username: str, password: str) -> "User | None":
        """Return the user if credentials are valid, else None."""
        user = db.query(cls).filter(cls.username == username).first()
        if not user:
            return None
        if not cls.verify_password(password, user.hashed_password):
            return None
        return user

    # ------------------------------------------------------------------ #
    #  Serialisation                                                       #
    # ------------------------------------------------------------------ #

    def to_dict(self, include_sensitive: bool = False) -> dict:
        data = {
            "id":         self.id,
            "username":   self.username,
            "email":      self.email,
            "is_active":  self.is_active,
            "is_admin":   self.is_admin,
            "is_pending": self.is_pending,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_sensitive:
            data["hashed_password"] = self.hashed_password
        return data

    def __repr__(self) -> str:
        return f"<User {self.username!r} id={self.id}>"