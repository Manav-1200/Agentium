"""
Phase 9 shared fixtures — mock DB, mocked services for unit testing.
All Phase 9 tests are designed to run without Docker by mocking DB and external deps.
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
import pytest_asyncio

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    """Mocked SQLAlchemy session."""
    session = MagicMock()
    session.query.return_value = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture
def mock_settings():
    """Mock application settings with Phase 9 defaults."""
    settings = MagicMock()
    settings.AUDIT_LOG_RETENTION_DAYS = 90
    settings.TASK_ARCHIVE_DAYS = 30
    settings.CONSTITUTION_MAX_VERSIONS = 10
    settings.TOKEN_EXPIRY_DAYS = 7
    settings.MAX_CONCURRENT_SESSIONS = 5
    settings.API_RATE_LIMIT_PER_MINUTE = 100
    settings.SMTP_HOST = None
    settings.SMTP_PORT = 587
    settings.SMTP_USER = None
    settings.SMTP_PASSWORD = None
    settings.ALERT_EMAIL_TO = None
    settings.WEBHOOK_ALERT_URL = None
    settings.CHROMA_PERSIST_DIR = "./chroma_data"
    settings.SECRET_KEY = "test-secret-key"
    return settings
