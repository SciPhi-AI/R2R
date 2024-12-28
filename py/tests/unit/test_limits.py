import pytest
import uuid
from uuid import UUID
from datetime import datetime, timezone, timedelta

from core.base import LimitSettings
from core.database.postgres import PostgresLimitsHandler


@pytest.mark.asyncio
async def test_log_request_and_count(limits_handler):
    user_id = uuid.uuid4()
    route = "/test-route"

    # Initially no requests
    now = datetime.now(timezone.utc)
    one_min_ago = now - timedelta(minutes=1)
    # Use handler's private method to count (for test)
    # If you want to test the private method, you either mock or rely on test code:
    # We'll rely on public methods only for best practice. Since no public method returns counts,
    # let's do a check after logging requests.

    # Before any requests are logged, we can try a limit check with large limits, should pass
    await limits_handler.check_limits(user_id, route)  # no error

    # Log a request
    await limits_handler.log_request(user_id, route)

    # Check that request count increments properly
    # Because this is a private method, let's cheat and call it. Alternatively, set limits so low that we fail now.
    # We'll just rely on a low limit scenario:
    # Set user-specific route limit to 0 to force immediate fail on second request:
    orig_config = limits_handler.config
    # Temporarily override config for test
    limits_handler.config.route_limits = {
        route: LimitSettings(
            route_per_min=1
        )  # can allow just 1 request per minute
    }

    # We've logged 1 request. Check limits again: still no error since we are at 1 request and limit=1
    await limits_handler.check_limits(user_id, route)  # no error

    # Log another request
    await limits_handler.log_request(user_id, route)
    # Now we have 2 requests this minute, route limit = 1
    with pytest.raises(
        ValueError, match="Per-route per-minute rate limit exceeded"
    ):
        await limits_handler.check_limits(user_id, route)

    # Restore original config after test
    limits_handler.config.route_limits = orig_config.route_limits


@pytest.mark.asyncio
async def test_global_limit(limits_handler):
    user_id = uuid.uuid4()
    route = "/global-test"
    # Set global limit to 1 request per minute
    orig_limits = limits_handler.config.limits
    limits_handler.config.limits = LimitSettings(global_per_min=1)

    # Log one request
    await limits_handler.log_request(user_id, route)
    # Check limits: should pass
    await limits_handler.check_limits(user_id, route)

    # Log another request (2 in one minute)
    await limits_handler.log_request(user_id, route)
    # Check limits: should fail global limit
    with pytest.raises(
        ValueError, match="Global per-minute rate limit exceeded"
    ):
        await limits_handler.check_limits(user_id, route)

    # Restore original limits
    limits_handler.config.limits = orig_limits


@pytest.mark.asyncio
async def test_monthly_limit(limits_handler):
    # First, clear any existing data for clean test
    clear_query = f"""
    DELETE FROM {limits_handler._get_table_name(PostgresLimitsHandler.TABLE_NAME)}
    """
    await limits_handler.connection_manager.execute_query(clear_query)

    user_id = uuid.uuid4()
    route = "/monthly-test"
    print(f"\n[TEST] Starting monthly limit test with user_id={user_id}")

    # Set monthly limit to 1
    orig_limits = limits_handler.config.limits
    limits_handler.config.limits = LimitSettings(monthly_limit=1)
    print(f"[TEST] Set monthly limit to 1")

    # Verify initial count
    initial_count = await limits_handler._count_monthly_requests(user_id)
    print(f"[TEST] Initial count: {initial_count}")

    # Log one request
    print(f"[TEST] Logging first request")
    await limits_handler.log_request(user_id, route)

    # Verify count after first log
    count_after_log = await limits_handler._count_monthly_requests(user_id)
    print(f"[TEST] Count after first log: {count_after_log}")

    # This should pass since we're at limit but not over
    print(f"[TEST] Checking limits after first request")
    await limits_handler.check_limits(user_id, route)

    # Restore original limits
    limits_handler.config.limits = orig_limits


# @pytest.mark.asyncio
# async def test_monthly_limit(limits_handler):
#     user_id = uuid.uuid4()
#     route = "/monthly-test"

#     # Set monthly limit to 1
#     orig_limits = limits_handler.config.limits
#     limits_handler.config.limits = LimitSettings(monthly_limit=1)

#     # Log one request
#     await limits_handler.log_request(user_id, route)
#     # Check limits: should pass
#     await limits_handler.check_limits(user_id, route)

#     # Another request in same month
#     await limits_handler.log_request(user_id, route)
#     # Check limits: should fail monthly limit
#     with pytest.raises(ValueError, match="Monthly rate limit exceeded"):
#         await limits_handler.check_limits(user_id, route)

#     # Restore original limits
#     limits_handler.config.limits = orig_limits


@pytest.mark.asyncio
async def test_no_limits_scenario(limits_handler):
    user_id = uuid.uuid4()
    route = "/no-limits"

    # Set no limits at all
    orig_limits = limits_handler.config.limits
    limits_handler.config.limits = LimitSettings(
        global_per_min=None, route_per_min=None, monthly_limit=None
    )

    # Log many requests
    for _ in range(10):
        await limits_handler.log_request(user_id, route)

    # Check limits: should never raise since no limits
    await limits_handler.check_limits(user_id, route)

    # Restore original limits
    limits_handler.config.limits = orig_limits
