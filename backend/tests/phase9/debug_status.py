"""Debug script to test _get_key_status with MagicMock."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from unittest.mock import MagicMock
from datetime import datetime, timedelta
from backend.services.api_key_manager import APIKeyManager, APIKeyHealthStatus

mgr = APIKeyManager()

# Test 1: Disabled key
key = MagicMock()
key.is_active = False
result = mgr._get_key_status(key)
print(f"Test disabled: result={result}, expected={APIKeyHealthStatus.DISABLED}")
print(f"  key.is_active={key.is_active}, type={type(key.is_active)}")
print(f"  not key.is_active={not key.is_active}")
print(f"  key.is_active is False={key.is_active is False}")

# Test 2: Cooldown key
key2 = MagicMock()
key2.is_active = True
key2.cooldown_until = datetime.utcnow() + timedelta(minutes=5)
result2 = mgr._get_key_status(key2)
print(f"\nTest cooldown: result={result2}, expected={APIKeyHealthStatus.COOLDOWN}")
print(f"  key2.cooldown_until={key2.cooldown_until}")
print(f"  now < cooldown_until={datetime.utcnow() < key2.cooldown_until}")
