"""Tests for ConfirmationManager token-based API (D2.6).

CONFIRMATION MANAGER OVERVIEW:
==============================
The ConfirmationManager provides human-in-the-loop confirmation for dangerous
operations like arming and takeoff. It supports two modes:

1. INTERACTIVE MODE (auto_confirm=False):
   - Operations wait for external confirmation via submit()
   - External systems (CLI, web UI, MCP tools) call submit() with approval
   - Operations timeout if no response within TTL

2. AUTO-CONFIRM MODE (auto_confirm=True):
   - All operations are automatically approved
   - Used for testing or fully autonomous operation (not recommended for production)

TOKEN-BASED API:
================
The D2.6 API uses tokens for correlation:

1. require() returns a ConfirmationToken
2. External system calls submit() with token and approval status
3. require() unblocks and returns when submit() is called
4. Caller checks get_pending() for approval status

KEY TEST SCENARIOS:
===================
1. AUTO-CONFIRM: Verify operations proceed immediately when auto_confirm=True
2. MANUAL APPROVE: Verify approved operations proceed
3. MANUAL REJECT: Verify rejected operations return error
4. TIMEOUT: Verify operations timeout when no response
5. UNKNOWN TOKEN: Verify submit() handles invalid tokens gracefully
6. TTL EXPIRATION: Verify operations timeout at configured TTL
7. NOTE CAPTURE: Verify notes from operator are captured
"""

import asyncio
import time

import pytest

from avatar.mcp_server.confirmation import (
    ConfirmationToken,
    PendingConfirmation,
    ConfirmationManager,
    ConfirmationConfig,
    ConfirmationResponse,
    ExceptionType,
    MissionPlan,
    TelemetrySnapshot,
)


class TestConfirmationToken:
    """Test ConfirmationToken dataclass."""

    def test_token_creation(self):
        """ConfirmationToken can be created with required fields."""
        token = ConfirmationToken(token="abc123", action="arm_and_takeoff")
        assert token.token == "abc123"
        assert token.action == "arm_and_takeoff"

    def test_token_is_frozen(self):
        """ConfirmationToken is immutable (frozen=True)."""
        token = ConfirmationToken(token="abc123", action="test")
        with pytest.raises(AttributeError):
            token.token = "new_token"  # type: ignore

    def test_auto_confirm_token(self):
        """Auto-confirm token has special __auto__ value."""
        token = ConfirmationToken(token="__auto__", action="test")
        assert token.token == "__auto__"


class TestPendingConfirmation:
    """Test PendingConfirmation internal dataclass."""

    def test_pending_creation(self):
        """PendingConfirmation can be created with event."""
        event = asyncio.Event()
        pending = PendingConfirmation(
            event=event,
            action="test_action",
            summary="Test summary",
            payload={"key": "value"},
            destructive=True,
        )
        assert pending.event is event
        assert pending.action == "test_action"
        assert pending.summary == "Test summary"
        assert pending.payload == {"key": "value"}
        assert pending.destructive is True
        assert pending.response is None
        assert pending.created_at > 0

    def test_pending_default_values(self):
        """PendingConfirmation has correct defaults."""
        event = asyncio.Event()
        pending = PendingConfirmation(event=event)
        assert pending.action == ""
        assert pending.summary == ""
        assert pending.payload == {}
        assert pending.destructive is False


class TestConfirmationManagerInit:
    """Test ConfirmationManager initialization."""

    def test_default_init(self):
        """ConfirmationManager initializes with defaults."""
        manager = ConfirmationManager()
        assert manager.config is not None
        assert manager.config.timeout_s == 10.0
        assert manager.auto_confirm is False
        assert manager.default_ttl_s == 60.0

    def test_custom_config_init(self):
        """ConfirmationManager accepts custom config."""
        config = ConfirmationConfig(timeout_s=20.0, show_telemetry_details=False)
        manager = ConfirmationManager(config=config)
        assert manager.config.timeout_s == 20.0
        assert manager.config.show_telemetry_details is False

    def test_auto_confirm_flag(self):
        """ConfirmationManager auto_confirm flag can be set."""
        manager = ConfirmationManager()
        manager.auto_confirm = True
        assert manager.auto_confirm is True


class TestConfirmationManagerRequire:
    """Test ConfirmationManager.require() method."""

    @pytest.mark.asyncio
    async def test_require_auto_confirm(self):
        """require() returns immediately in auto-confirm mode."""
        manager = ConfirmationManager()
        manager.auto_confirm = True

        token = await manager.require(
            action="test_action",
            destructive=True,
            summary="Test summary",
            payload={"key": "value"}
        )

        assert token.token == "__auto__"
        assert token.action == "test_action"

    @pytest.mark.asyncio
    async def test_require_creates_pending(self):
        """require() creates a pending confirmation entry."""
        manager = ConfirmationManager()
        manager.default_ttl_s = 60.0

        # Start require in background
        task = asyncio.create_task(
            manager.require(
                action="test_action",
                destructive=True,
                summary="Test",
                payload={}
            )
        )

        # Give it a moment to create the pending entry
        await asyncio.sleep(0.01)

        # There should be a pending entry
        assert len(manager._pending) == 1

        # Get the token and submit approval
        token_str = list(manager._pending.keys())[0]
        await manager.submit(token_str, approved=True)

        # Wait for require to complete
        token = await task

        assert token.action == "test_action"
        assert token.token == token_str

    @pytest.mark.asyncio
    async def test_require_timeout(self):
        """require() raises TimeoutError when TTL expires."""
        manager = ConfirmationManager()
        manager.default_ttl_s = 0.1  # Very short TTL

        with pytest.raises(asyncio.TimeoutError):
            await manager.require(
                action="test_action",
                destructive=True,
                summary="Test",
                payload={}
            )

    @pytest.mark.asyncio
    async def test_require_custom_ttl(self):
        """require() respects custom TTL parameter."""
        manager = ConfirmationManager()
        manager.default_ttl_s = 60.0  # Long default TTL

        # Use very short custom TTL
        with pytest.raises(asyncio.TimeoutError):
            await manager.require(
                action="test_action",
                destructive=True,
                summary="Test",
                payload={},
                ttl_s=0.05  # 50ms TTL
            )


class TestConfirmationManagerSubmit:
    """Test ConfirmationManager.submit() method."""

    @pytest.mark.asyncio
    async def test_submit_approval(self):
        """submit() with approved=True sets correct response."""
        manager = ConfirmationManager()

        # Create a pending confirmation via require
        task = asyncio.create_task(
            manager.require(
                action="test_action",
                destructive=True,
                summary="Test",
                payload={}
            )
        )

        await asyncio.sleep(0.01)
        token_str = list(manager._pending.keys())[0]

        # Submit approval
        await manager.submit(token_str, approved=True, note="Operator approved")

        # Wait for require to complete
        await task

        # Check response
        response = manager.get_pending(token_str)
        assert response is not None
        assert response["approved"] is True
        assert response["note"] == "Operator approved"

    @pytest.mark.asyncio
    async def test_submit_rejection(self):
        """submit() with approved=False sets correct response."""
        manager = ConfirmationManager()

        task = asyncio.create_task(
            manager.require(
                action="test_action",
                destructive=True,
                summary="Test",
                payload={}
            )
        )

        await asyncio.sleep(0.01)
        token_str = list(manager._pending.keys())[0]

        # Submit rejection
        await manager.submit(token_str, approved=False, note="Battery too low")

        await task

        response = manager.get_pending(token_str)
        assert response is not None
        assert response["approved"] is False
        assert response["note"] == "Battery too low"

    @pytest.mark.asyncio
    async def test_submit_unknown_token(self):
        """submit() handles unknown token gracefully."""
        manager = ConfirmationManager()

        # Submit to non-existent token - should not raise
        await manager.submit("nonexistent_token", approved=True)

        # Verify no error occurred
        assert True

    @pytest.mark.asyncio
    async def test_submit_auto_confirm_token(self):
        """submit() handles __auto__ token gracefully."""
        manager = ConfirmationManager()

        # Submit to auto-confirm token - should not raise
        await manager.submit("__auto__", approved=True)

        assert True


class TestConfirmationManagerGetPending:
    """Test ConfirmationManager.get_pending() method."""

    def test_get_pending_auto_confirm(self):
        """get_pending() returns auto-approved for __auto__ token."""
        manager = ConfirmationManager()

        response = manager.get_pending("__auto__")
        assert response is not None
        assert response["approved"] is True
        assert response["note"] == "auto"

    def test_get_pending_nonexistent(self):
        """get_pending() returns None for nonexistent token."""
        manager = ConfirmationManager()

        response = manager.get_pending("nonexistent_token")
        assert response is None

    @pytest.mark.asyncio
    async def test_get_pending_after_submit(self):
        """get_pending() returns response after submit."""
        manager = ConfirmationManager()

        task = asyncio.create_task(
            manager.require(action="test", destructive=True, summary="Test", payload={})
        )

        await asyncio.sleep(0.01)
        token_str = list(manager._pending.keys())[0]
        await manager.submit(token_str, approved=True, note="Test note")
        await task

        response = manager.get_pending(token_str)
        assert response == {"approved": True, "note": "Test note", "timestamp": response["timestamp"]}


class TestConfirmationManagerClearPending:
    """Test ConfirmationManager.clear_pending() method."""

    def test_clear_pending_auto_confirm(self):
        """clear_pending() returns True for __auto__ token."""
        manager = ConfirmationManager()

        result = manager.clear_pending("__auto__")
        assert result is True

    @pytest.mark.asyncio
    async def test_clear_pending_existing(self):
        """clear_pending() removes existing token."""
        manager = ConfirmationManager()

        task = asyncio.create_task(
            manager.require(action="test", destructive=True, summary="Test", payload={})
        )

        await asyncio.sleep(0.01)
        token_str = list(manager._pending.keys())[0]
        await manager.submit(token_str, approved=True)
        await task

        # Token should still exist
        assert manager.get_pending(token_str) is not None

        # Clear it
        result = manager.clear_pending(token_str)
        assert result is True

        # Now it should be gone
        assert manager.get_pending(token_str) is None

    def test_clear_pending_nonexistent(self):
        """clear_pending() returns False for nonexistent token."""
        manager = ConfirmationManager()

        result = manager.clear_pending("nonexistent_token")
        assert result is False


class TestConfirmationManagerIntegration:
    """Integration tests for full confirmation flow."""

    @pytest.mark.asyncio
    async def test_full_approval_flow(self):
        """Test complete flow from require to approval."""
        manager = ConfirmationManager()
        manager.default_ttl_s = 5.0

        async def approver():
            # Wait for confirmation to be created
            await asyncio.sleep(0.05)
            # Find the pending token
            token_str = list(manager._pending.keys())[0]
            # Approve it
            await manager.submit(token_str, approved=True, note="Looks good")

        # Start both tasks
        approver_task = asyncio.create_task(approver())
        require_task = asyncio.create_task(
            manager.require(
                action="arm_and_takeoff",
                destructive=True,
                summary="Arm motors and takeoff to 15m",
                payload={"altitude_m": 15.0}
            )
        )

        # Wait for both to complete
        token = await require_task
        await approver_task

        # Verify result
        assert token.action == "arm_and_takeoff"
        response = manager.get_pending(token.token)
        assert response["approved"] is True
        manager.clear_pending(token.token)

    @pytest.mark.asyncio
    async def test_full_rejection_flow(self):
        """Test complete flow from require to rejection."""
        manager = ConfirmationManager()
        manager.default_ttl_s = 5.0

        async def rejector():
            await asyncio.sleep(0.05)
            token_str = list(manager._pending.keys())[0]
            await manager.submit(token_str, approved=False, note="Battery too low")

        rejector_task = asyncio.create_task(rejector())
        require_task = asyncio.create_task(
            manager.require(
                action="arm_and_takeoff",
                destructive=True,
                summary="Takeoff",
                payload={"altitude_m": 10.0}
            )
        )

        token = await require_task
        await rejector_task

        assert token.action == "arm_and_takeoff"
        response = manager.get_pending(token.token)
        assert response["approved"] is False
        assert response["note"] == "Battery too low"
        manager.clear_pending(token.token)


class TestLegacyConfirmationMethods:
    """Test legacy pre-D2.6 methods still work."""

    def test_submit_response(self):
        """submit_response() still works for backward compatibility."""
        manager = ConfirmationManager()
        manager.submit_response("yes")
        # Should not raise
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
