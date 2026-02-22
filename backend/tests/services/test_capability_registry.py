import pytest
import json
from unittest.mock import MagicMock
from backend.services.capability_registry import CapabilityRegistry, Capability, TIER_CAPABILITIES
from backend.models.entities.agents import Agent
from backend.models.entities.audit import AuditLog

@pytest.fixture
def mock_db():
    db = MagicMock()
    return db

@pytest.fixture
def mock_agent_head():
    agent = MagicMock(spec=Agent)
    agent.agentium_id = "00001"
    agent.custom_capabilities = None
    return agent

@pytest.fixture
def mock_agent_council():
    agent = MagicMock(spec=Agent)
    agent.agentium_id = "10001"
    agent.custom_capabilities = None
    return agent

@pytest.fixture
def mock_agent_task():
    agent = MagicMock(spec=Agent)
    agent.agentium_id = "30001"
    agent.custom_capabilities = None
    return agent

class TestCapabilityRegistry:
    
    def test_get_agent_tier(self):
        assert CapabilityRegistry.get_agent_tier("00001") == "0"
        assert CapabilityRegistry.get_agent_tier("10001") == "1"
        assert CapabilityRegistry.get_agent_tier("20001") == "2"
        assert CapabilityRegistry.get_agent_tier("30001") == "3"

    def test_get_agent_tier_invalid(self):
        with pytest.raises(ValueError):
            CapabilityRegistry.get_agent_tier("")
        with pytest.raises(ValueError):
            CapabilityRegistry.get_agent_tier(None)

    def test_get_base_capabilities(self):
        caps_0 = CapabilityRegistry.get_base_capabilities("00001")
        assert Capability.VETO in caps_0
        assert Capability.EXECUTE_TASK in caps_0

        caps_3 = CapabilityRegistry.get_base_capabilities("30001")
        assert Capability.EXECUTE_TASK in caps_3
        assert Capability.VETO not in caps_3

    def test_can_agent_base_true(self, mock_agent_head, mock_db):
        assert CapabilityRegistry.can_agent(mock_agent_head, Capability.VETO, mock_db) == True

    def test_can_agent_base_false(self, mock_agent_task, mock_db):
        AuditLog.log = MagicMock()
        assert CapabilityRegistry.can_agent(mock_agent_task, Capability.VETO, mock_db) == False
        AuditLog.log.assert_called_once()
        
    def test_can_agent_exception_on_deny(self, mock_agent_task, mock_db):
        with pytest.raises(PermissionError) as exc:
            CapabilityRegistry.can_agent(mock_agent_task, Capability.VETO, mock_db, raise_on_deny=True)
        assert "lacks capability: veto" in str(exc.value)

    def test_custom_capabilities_granted(self, mock_agent_task, mock_db):
        mock_agent_task.custom_capabilities = json.dumps({"granted": [Capability.ADMIN_VECTOR_DB.value], "revoked": []})
        assert CapabilityRegistry.can_agent(mock_agent_task, Capability.ADMIN_VECTOR_DB, mock_db) == True

    def test_custom_capabilities_revoked(self, mock_agent_head, mock_db):
        mock_agent_head.custom_capabilities = json.dumps({"granted": [], "revoked": [Capability.VETO.value]})
        AuditLog.log = MagicMock()
        assert CapabilityRegistry.can_agent(mock_agent_head, Capability.VETO, mock_db) == False

    def test_grant_capability_success(self, mock_agent_head, mock_agent_task, mock_db):
        AuditLog.log = MagicMock()
        
        CapabilityRegistry.grant_capability(
            agent=mock_agent_task,
            capability=Capability.ADMIN_VECTOR_DB,
            granted_by=mock_agent_head,
            reason="Temporary grant for maintenance",
            db=mock_db
        )
        
        custom_caps = json.loads(mock_agent_task.custom_capabilities)
        assert Capability.ADMIN_VECTOR_DB.value in custom_caps["granted"]
        AuditLog.log.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_grant_capability_no_permission(self, mock_agent_task, mock_agent_council, mock_db):
        with pytest.raises(PermissionError) as exc:
            CapabilityRegistry.grant_capability(
                agent=mock_agent_task,
                capability=Capability.ADMIN_VECTOR_DB,
                granted_by=mock_agent_council,
                reason="Should fail",
                db=mock_db
            )
        assert "cannot grant capabilities" in str(exc.value)

    def test_revoke_capability_success(self, mock_agent_head, mock_agent_council, mock_db):
        AuditLog.log = MagicMock()
        
        CapabilityRegistry.revoke_capability(
            agent=mock_agent_council,
            capability=Capability.ALLOCATE_RESOURCES,
            revoked_by=mock_agent_head,
            reason="Violation of resource policy",
            db=mock_db
        )
        
        custom_caps = json.loads(mock_agent_council.custom_capabilities)
        assert Capability.ALLOCATE_RESOURCES.value in custom_caps["revoked"]
        mock_db.flush.assert_called_once()

    def test_revoke_capability_no_permission(self, mock_agent_task, mock_agent_council, mock_db):
        with pytest.raises(PermissionError) as exc:
            CapabilityRegistry.revoke_capability(
                agent=mock_agent_council,
                capability=Capability.ALLOCATE_RESOURCES,
                revoked_by=mock_agent_task,
                reason="Should fail",
                db=mock_db
            )
        assert "cannot revoke capabilities" in str(exc.value)

    def test_revoke_all_capabilities(self, mock_agent_council, mock_db):
        AuditLog.log = MagicMock()
        
        CapabilityRegistry.revoke_all_capabilities(mock_agent_council, "Agent liquidated", mock_db)
        
        custom_caps = json.loads(mock_agent_council.custom_capabilities)
        assert len(custom_caps["revoked"]) > 0
        assert Capability.ALLOCATE_RESOURCES.value in custom_caps["revoked"]
        assert len(custom_caps["granted"]) == 0
        mock_db.flush.assert_called_once()

    def test_get_agent_capabilities(self, mock_agent_task):
        mock_agent_task.custom_capabilities = json.dumps({
            "granted": [Capability.ADMIN_VECTOR_DB.value],
            "revoked": [Capability.EXECUTE_TASK.value]
        })
        
        profile = CapabilityRegistry.get_agent_capabilities(mock_agent_task)
        
        assert profile["tier"] == "3"
        assert Capability.ADMIN_VECTOR_DB.value in profile["granted_capabilities"]
        assert Capability.EXECUTE_TASK.value in profile["revoked_capabilities"]
        
        assert Capability.ADMIN_VECTOR_DB.value in profile["effective_capabilities"]
        assert Capability.EXECUTE_TASK.value not in profile["effective_capabilities"]
