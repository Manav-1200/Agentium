
import sys
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Mock redis before importing modules that use it
sys.modules["redis"] = MagicMock()
sys.modules["redis.asyncio"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["chromadb.config"] = MagicMock()
sys.modules["chromadb.api"] = MagicMock()
sys.modules["chromadb.api.types"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["psycopg2"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["docker"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["httpx"] = MagicMock()
sys.modules["jose"] = MagicMock()
sys.modules["passlib"] = MagicMock()
sys.modules["passlib.context"] = MagicMock()
sys.modules["multipart"] = MagicMock()

from backend.services.agent_orchestrator import AgentOrchestrator
from backend.core.constitutional_guard import Verdict, ConstitutionalDecision, ViolationSeverity

async def test_constitutional_block():
    print("TEST: Constitutional Guard Integration (Block)")
    
    # Mock dependencies
    db = MagicMock()
    mock_bus = AsyncMock()
    
    # Init orchestrator
    orchestrator = AgentOrchestrator(db, mock_bus)
    
    # Mock Guard (we don't want to rely on real DB/Redis for unit test)
    orchestrator.guard = AsyncMock()
    orchestrator.guard.check_action.return_value = ConstitutionalDecision(
        verdict=Verdict.BLOCK,
        severity=ViolationSeverity.CRITICAL,
        explanation="Forbidden action detected"
    )
    
    # Mock get_agent to return something
    orchestrator._get_agent = MagicMock(return_value={"id": "30001", "role": "task"})
    orchestrator._get_parent_id = MagicMock(return_value="20001")
    orchestrator._check_circuit_breaker = MagicMock(return_value=None)
    
    # Execute
    result = await orchestrator.process_intent("rm -rf /", "30001")
    
    # Assert
    print(f"Result success: {result.success}")
    print(f"Result error: {result.error}")
    
    assert not result.success
    assert "Constitutional Violation" in result.error
    print("TEST PASSED: Action was blocked by Constitution.")

async def test_constitutional_allow():
    print("\nTEST: Constitutional Guard Integration (Allow)")
    
    # Mock dependencies
    db = MagicMock()
    mock_bus = AsyncMock()
    
    # Init orchestrator
    orchestrator = AgentOrchestrator(db, mock_bus)
    
    # Mock Guard to ALLOW
    orchestrator.guard = AsyncMock()
    orchestrator.guard.check_action.return_value = ConstitutionalDecision(
        verdict=Verdict.ALLOW,
        severity=ViolationSeverity.LOW
    )
    
    # Mock internals
    orchestrator._get_agent = MagicMock(return_value={"id": "30001", "role": "task"})
    orchestrator._get_parent_id = MagicMock(return_value="20001")
    orchestrator._check_circuit_breaker = MagicMock(return_value=None)
    orchestrator._detect_tool_intent = MagicMock(return_value={"is_tool_command": False})
    orchestrator._detect_tool_creation_intent = MagicMock(return_value=False)
    orchestrator._get_direction = MagicMock(return_value="up")
    orchestrator.enrich_with_context = AsyncMock(return_value=MagicMock())
    orchestrator._route_up_with_tools = AsyncMock(return_value=MagicMock(success=True))
    
    # Mock HierarchyValidator
    from backend.services.message_bus import HierarchyValidator
    HierarchyValidator.can_route = MagicMock(return_value=True)

    # Execute
    result = await orchestrator.process_intent("Hello world", "30001")
    
    # Assert
    # We expect the mock _route_up_with_tools to return success, so process_intent should succeed
    # Note: process_intent returns whatever _route_up_with_tools returns
    print(f"Result success: {result.success}")
    
    assert result.success
    print("TEST PASSED: Action was allowed by Constitution.")

if __name__ == "__main__":
    asyncio.run(test_constitutional_block())
    asyncio.run(test_constitutional_allow())
