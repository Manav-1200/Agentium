
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock redis modules before imports
sys.modules["redis"] = MagicMock()
sys.modules["redis.asyncio"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["chromadb.api"] = MagicMock()
sys.modules["chromadb.api.types"] = MagicMock()
sys.modules["chromadb.config"] = MagicMock()
sys.modules["chromadb.config"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()

# Create a mock for database module
mock_db_module = MagicMock()
sys.modules["backend.models.database"] = mock_db_module

# Mock sqlalchemy to avoid "Column expression expected" error
mock_sqlalchemy = MagicMock()
sys.modules["sqlalchemy"] = mock_sqlalchemy

from backend.services.message_bus import MessageBus

from types import SimpleNamespace

class TestMessageBusLookup(unittest.TestCase):
    
    def test_get_parent_id_sync(self):
        bus = MessageBus()
        
        # Mock dependencies - standard context manager pattern
        mock_session = MagicMock(name="active_session")
        mock_cm = MagicMock(name="ctx_manager")
        mock_cm.__enter__.return_value = mock_session
        mock_cm.__exit__.return_value = None
        
        mock_db_module.get_db_context = MagicMock(return_value=mock_cm)
        
        mock_query = MagicMock()
        mock_sqlalchemy.select.return_value = mock_query

        # Use SimpleNamespace to avoid MagicMock property creation
        agent_obj = SimpleNamespace(agentium_id="30001", parent_id="uuid-123", id="uuid-30001", parent=None)
        parent_obj = SimpleNamespace(agentium_id="20001", parent_id="uuid-456", id="uuid-123", parent=None)
        
        mock_result1 = MagicMock(name="result1")
        mock_result1.scalars.return_value.first.return_value = agent_obj
        
        mock_result2 = MagicMock(name="result2")
        mock_result2.scalars.return_value.first.return_value = parent_obj
        
        mock_session.execute.side_effect = [mock_result1, mock_result2]
        
        with patch.dict(sys.modules, {"backend.models.entities.agents": MagicMock()}):
             result = bus._get_parent_id_sync("30001")
        
        print(f"Result: {result}")
        self.assertEqual(result, "20001")
        print("TEST PASSED: _get_parent_id_sync found parent from DB")

    def test_get_parent_id_sync_no_parent(self):
        bus = MessageBus()
        
        mock_session = MagicMock(name="active_session")
        mock_cm = MagicMock(name="ctx_manager")
        mock_cm.__enter__.return_value = mock_session
        mock_cm.__exit__.return_value = None
        
        mock_db_module.get_db_context = MagicMock(return_value=mock_cm)
        
        mock_query = MagicMock()
        mock_sqlalchemy.select.return_value = mock_query

        # Agent has parent_id = None
        agent_obj = SimpleNamespace(agentium_id="30001", parent_id=None, id="uuid-30001", parent=None)
        
        mock_result = MagicMock(name="result1")
        mock_result.scalars.return_value.first.return_value = agent_obj
        
        mock_session.execute.return_value = mock_result
        
        with patch.dict(sys.modules, {"backend.models.entities.agents": MagicMock()}):
            result = bus._get_parent_id_sync("30001")
        
        print(f"Result: {result}")
        self.assertIsNone(result)
        print("TEST PASSED: _get_parent_id_sync handled missing parent")

if __name__ == "__main__":
    unittest.main()
