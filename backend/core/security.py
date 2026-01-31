"""
Security utilities for Agentium.
Handles API key encryption/decryption and authentication.
"""

from cryptography.fernet import Fernet
from backend.core.config import settings

def get_fernet():
    """Get Fernet instance for encryption."""
    key = settings.ENCRYPTION_KEY
    if not key:
        # Generate a key if not set (WARNING: will invalidate existing encrypted data on restart)
        # In production, ENCRYPTION_KEY must be set in environment
        key = Fernet.generate_key().decode()
    return Fernet(key.encode() if isinstance(key, str) else key)

def encrypt_api_key(plain_key: str) -> str:
    """Encrypt an API key for storage."""
    if not plain_key:
        return None
    f = get_fernet()
    return f.encrypt(plain_key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key for use."""
    if not encrypted_key:
        return None
    f = get_fernet()
    return f.decrypt(encrypted_key.encode()).decode()