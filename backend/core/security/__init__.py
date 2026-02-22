"""Security modules for Agentium."""

from backend.core.security.execution_guard import ExecutionGuard, execution_guard, SecurityCheckResult
from cryptography.fernet import Fernet
from backend.core.config import settings


def get_fernet():
    """Get Fernet instance for encryption."""
    key = settings.ENCRYPTION_KEY
    if key:
        if isinstance(key, str):
            key = key.encode()
    else:
        key = Fernet.generate_key()
    return Fernet(key)


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


__all__ = [
    "ExecutionGuard", "execution_guard", "SecurityCheckResult",
    "get_fernet", "encrypt_api_key", "decrypt_api_key",
]