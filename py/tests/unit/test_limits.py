import pytest
import uuid
from uuid import UUID
from datetime import datetime, timezone, timedelta

from core.base import LimitSettings
from shared.abstractions import User
from core.database.postgres import PostgresLimitsHandler

@pytest.mark.asyncio
async def test_log_request_and_count(limits_handler):
    """
    Test that when we log requests, the count increments, and rate-limits are enforced.
    Route-specific test using the /v3/retrieval/search endpoint limits.
    """
    # Clear existing logs first
    clear_query = f"DELETE FROM {limits_handler._get_table_name(PostgresLimitsHandler.TABLE_NAME)}"
    await limits_handler.connection_manager.execute_query(clear_query)

    user_id = uuid.uuid4()
    route = "/v3/retrieval/search"  # Using actual route from config
    test_user = User(
        id=user_id,
        email="test@example.com",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        limits_overrides=None,
    )

    # Set route limit to match config: 5 requests per minute
    old_route_limits = limits_handler.config.route_limits
    new_route_limits = {
        route: LimitSettings(route_per_min=5, monthly_limit=10)
    }
    limits_handler.config.route_limits = new_route_limits
    
    print(f"\nTesting with route limits: {new_route_limits}")
    print(f"Route settings: {limits_handler.config.route_limits[route]}")

    try:
        # Initial check should pass (no requests yet)
        await limits_handler.check_limits(test_user, route)
        print("Initial check passed (no requests)")

        # Log 5 requests (exactly at limit)
        for i in range(5):
            await limits_handler.log_request(user_id, route)
            now = datetime.now(timezone.utc)
            one_min_ago = now - timedelta(minutes=1)
            route_count = await limits_handler._count_requests(user_id, route, one_min_ago)
            print(f"Route count after request {i+1}: {route_count}")

            # This should pass for all 5 requests
            await limits_handler.check_limits(test_user, route)
            print(f"Check limits passed after request {i+1}")

        # Log the 6th request (over limit)
        await limits_handler.log_request(user_id, route)
        route_count = await limits_handler._count_requests(user_id, route, one_min_ago)
        print(f"Route count after request 6: {route_count}")

        # This check should fail as we've exceeded route_per_min=5
        with pytest.raises(ValueError, match="Per-route per-minute rate limit exceeded"):
            await limits_handler.check_limits(test_user, route)

    finally:
        limits_handler.config.route_limits = old_route_limits

@pytest.mark.asyncio
async def test_global_limit(limits_handler):
    """
    Test global limit using the configured limit of 10 requests per minute
    """
    # Clear existing logs
    clear_query = f"DELETE FROM {limits_handler._get_table_name(PostgresLimitsHandler.TABLE_NAME)}"
    await limits_handler.connection_manager.execute_query(clear_query)

    user_id = uuid.uuid4()
    route = "/global-test"
    test_user = User(
        id=user_id,
        email="globaltest@example.com",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        limits_overrides=None,
    )

    # Set global limit to match config: 10 requests per minute
    old_limits = limits_handler.config.limits
    limits_handler.config.limits = LimitSettings(global_per_min=10, monthly_limit=20)

    try:
        # Initial check should pass (no requests)
        await limits_handler.check_limits(test_user, route)
        print("Initial global check passed (no requests)")

        # Log 10 requests (hits the limit)
        for i in range(11):
            await limits_handler.log_request(user_id, route)
            
        # Debug counts
        now = datetime.now(timezone.utc)
        one_min_ago = now - timedelta(minutes=1)
        global_count = await limits_handler._count_requests(user_id, None, one_min_ago)
        print(f"Global count after 10 requests: {global_count}")

        # This should fail as we've hit global_per_min=10
        with pytest.raises(ValueError, match="Global per-minute rate limit exceeded"):
            await limits_handler.check_limits(test_user, route)

    finally:
        limits_handler.config.limits = old_limits


@pytest.mark.asyncio
async def test_monthly_limit(limits_handler):
    """
    Test monthly limit using the configured limit of 20 requests per month
    """
    # Clear existing logs
    clear_query = f"DELETE FROM {limits_handler._get_table_name(PostgresLimitsHandler.TABLE_NAME)}"
    await limits_handler.connection_manager.execute_query(clear_query)

    user_id = uuid.uuid4()
    route = "/monthly-test"
    test_user = User(
        id=user_id,
        email="monthly@example.com",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        limits_overrides=None,
    )

    old_limits = limits_handler.config.limits
    limits_handler.config.limits = LimitSettings(monthly_limit=20)

    try:
        # Initial check should pass (no requests)
        await limits_handler.check_limits(test_user, route)
        print("Initial monthly check passed (no requests)")

        # Log 20 requests (hits the monthly limit)
        for i in range(21):
            await limits_handler.log_request(user_id, route)

        # Get current month's count
        now = datetime.now(timezone.utc)
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_count = await limits_handler._count_requests(user_id, None, first_of_month)
        print(f"Monthly count after 20 requests: {monthly_count}")

        # This should fail as we've hit monthly_limit=20
        with pytest.raises(ValueError, match="Monthly rate limit exceeded"):
            await limits_handler.check_limits(test_user, route)

    finally:
        limits_handler.config.limits = old_limits

@pytest.mark.asyncio
async def test_user_level_override(limits_handler):
    """
    Test user-specific override limits with debug logging
    """
    user_id = UUID("47e53676-b478-5b3f-a409-234ca2164de5")
    route = "/test-route"
    
    # Clear existing logs first
    clear_query = f"DELETE FROM {limits_handler._get_table_name(PostgresLimitsHandler.TABLE_NAME)}"
    await limits_handler.connection_manager.execute_query(clear_query)
    
    test_user = User(
        id=user_id,
        email="override@example.com",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        limits_overrides={
            "global_per_min": 2,
            "route_per_min": 1,
            "route_overrides": {
                "/test-route": {
                    "route_per_min": 1
                }
            }
        },
    )

    # Set default limits that should be overridden
    old_limits = limits_handler.config.limits
    limits_handler.config.limits = LimitSettings(
        global_per_min=10,
        monthly_limit=20
    )

    # Debug: Print current limits
    print(f"\nDefault limits: {limits_handler.config.limits}")
    print(f"User overrides: {test_user.limits_overrides}")

    try:
        # First check limits (should pass as no requests yet)
        await limits_handler.check_limits(test_user, route)
        print("Initial check passed (no requests yet)")

        # Log first request
        await limits_handler.log_request(user_id, route)

        # Debug: Get current counts
        now = datetime.now(timezone.utc)
        one_min_ago = now - timedelta(minutes=1)
        global_count = await limits_handler._count_requests(user_id, None, one_min_ago)
        route_count = await limits_handler._count_requests(user_id, route, one_min_ago)
        print(f"\nAfter first request:")
        print(f"Global count: {global_count}")
        print(f"Route count: {route_count}")
        
        # Log second request
        await limits_handler.log_request(user_id, route)

        # This check should fail as we've hit route_per_min=1
        with pytest.raises(ValueError, match="Per-route per-minute rate limit exceeded"):
            await limits_handler.check_limits(test_user, route)
            
    finally:
        # Cleanup
        limits_handler.config.limits = old_limits