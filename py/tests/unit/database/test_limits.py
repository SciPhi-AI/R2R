import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from core.base import LimitSettings
from core.providers.database.postgres import PostgresLimitsHandler
from shared.abstractions import User


@pytest.mark.asyncio
async def test_log_request_and_count(limits_handler):
    """Test that when we log requests, the count increments, and rate-limits
    are enforced.

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
            route_count = await limits_handler._count_requests(
                user_id, route, one_min_ago)
            print(f"Route count after request {i + 1}: {route_count}")

            # This should pass for all 5 requests
            await limits_handler.check_limits(test_user, route)
            print(f"Check limits passed after request {i + 1}")

        # Log the 6th request (over limit)
        await limits_handler.log_request(user_id, route)
        route_count = await limits_handler._count_requests(
            user_id, route, one_min_ago)
        print(f"Route count after request 6: {route_count}")

        # This check should fail as we've exceeded route_per_min=5
        with pytest.raises(ValueError,
                           match="Per-route per-minute rate limit exceeded"):
            await limits_handler.check_limits(test_user, route)

    finally:
        limits_handler.config.route_limits = old_route_limits


@pytest.mark.asyncio
async def test_global_limit(limits_handler):
    """Test global limit using the configured limit of 10 requests per
    minute."""
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
    limits_handler.config.limits = LimitSettings(global_per_min=10,
                                                 monthly_limit=20)

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
        global_count = await limits_handler._count_requests(
            user_id, None, one_min_ago)
        print(f"Global count after 10 requests: {global_count}")

        # This should fail as we've hit global_per_min=10
        with pytest.raises(ValueError,
                           match="Global per-minute rate limit exceeded"):
            await limits_handler.check_limits(test_user, route)

    finally:
        limits_handler.config.limits = old_limits


@pytest.mark.asyncio
async def test_monthly_limit(limits_handler):
    """Test monthly limit using the configured limit of 20 requests per
    month."""
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
        first_of_month = now.replace(day=1,
                                     hour=0,
                                     minute=0,
                                     second=0,
                                     microsecond=0)
        monthly_count = await limits_handler._count_requests(
            user_id, None, first_of_month)
        print(f"Monthly count after 20 requests: {monthly_count}")

        # This should fail as we've hit monthly_limit=20
        with pytest.raises(ValueError, match="Monthly rate limit exceeded"):
            await limits_handler.check_limits(test_user, route)

    finally:
        limits_handler.config.limits = old_limits


@pytest.mark.asyncio
async def test_user_level_override(limits_handler):
    """Test user-specific override limits with debug logging."""
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
            },
        },
    )

    # Set default limits that should be overridden
    old_limits = limits_handler.config.limits
    limits_handler.config.limits = LimitSettings(global_per_min=10,
                                                 monthly_limit=20)

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
        global_count = await limits_handler._count_requests(
            user_id, None, one_min_ago)
        route_count = await limits_handler._count_requests(
            user_id, route, one_min_ago)
        print("\nAfter first request:")
        print(f"Global count: {global_count}")
        print(f"Route count: {route_count}")

        # Log second request
        await limits_handler.log_request(user_id, route)

        # This check should fail as we've hit route_per_min=1
        with pytest.raises(ValueError,
                           match="Per-route per-minute rate limit exceeded"):
            await limits_handler.check_limits(test_user, route)

    finally:
        # Cleanup
        limits_handler.config.limits = old_limits


@pytest.mark.asyncio
async def test_determine_effective_limits(limits_handler):
    """Test that user-level overrides > route-level overrides > global
    defaults.

    This is a pure logic test of the 'determine_effective_limits' method.
    """
    # Setup global/base defaults
    old_limits = limits_handler.config.limits
    limits_handler.config.limits = LimitSettings(global_per_min=10,
                                                 route_per_min=5,
                                                 monthly_limit=50)

    # Setup route-level override
    route = "/some-route"
    old_route_limits = limits_handler.config.route_limits
    limits_handler.config.route_limits = {
        route: LimitSettings(global_per_min=8,
                             route_per_min=3,
                             monthly_limit=30)
    }

    # Setup user-level override
    test_user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        limits_overrides={
            "global_per_min": 6,  # should override
            "route_overrides": {
                route: {
                    "route_per_min": 2
                }  # should override
            },
        },
    )

    try:
        effective = limits_handler.determine_effective_limits(test_user, route)

        # Check final / effective limits
        # Global limit overridden to 6
        assert effective.global_per_min == 6, (
            "User-level global override not applied")

        # route_per_min should be overridden to 2 (not the route-level 3)
        assert effective.route_per_min == 2, (
            "User-level route override not applied")

        # monthly_limit from route-level override is 30, user didn't override it, so it should stay 30
        assert effective.monthly_limit == 30, (
            "Route-level monthly override not applied")
    finally:
        # revert changes
        limits_handler.config.limits = old_limits
        limits_handler.config.route_limits = old_route_limits


@pytest.mark.asyncio
async def test_separate_route_usage_is_isolated(limits_handler):
    """Confirm that calls to /routeA do NOT increment the per-route usage for
    /routeB, and vice-versa."""
    # 1) Clear existing logs
    clear_query = f"DELETE FROM {limits_handler._get_table_name(limits_handler.TABLE_NAME)}"
    await limits_handler.connection_manager.execute_query(clear_query)

    # 2) Setup user & routes
    import uuid

    from shared.abstractions import User

    user_id = uuid.uuid4()
    routeA = "/v3/retrieval/rag"
    routeB = "/v3/retrieval/search"

    test_user = User(
        id=user_id,
        email="test@example.com",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        limits_overrides=None,
    )

    # 3) Insert some logs for routeA only
    for _ in range(3):
        await limits_handler.log_request(user_id, routeA)

    # 4) Check usage for routeA → Should be 3 in last minute
    now = datetime.now(timezone.utc)
    one_min_ago = now - timedelta(minutes=1)
    routeA_count = await limits_handler._count_requests(
        user_id, routeA, one_min_ago)
    assert routeA_count == 3, f"Expected 3 for routeA, got {routeA_count}"

    # 5) Check usage for routeB → Should be 0
    routeB_count = await limits_handler._count_requests(
        user_id, routeB, one_min_ago)
    assert routeB_count == 0, f"Expected 0 for routeB, got {routeB_count}"

    # 6) Insert some logs for routeB only
    for _ in range(2):
        await limits_handler.log_request(user_id, routeB)

    # 7) Recheck usage
    routeA_count_after = await limits_handler._count_requests(
        user_id, routeA, one_min_ago)
    routeB_count_after = await limits_handler._count_requests(
        user_id, routeB, one_min_ago)
    assert routeA_count_after == 3, (
        f"RouteA usage changed unexpectedly: {routeA_count_after}")
    assert routeB_count_after == 2, (
        f"RouteB usage is wrong: {routeB_count_after}")


# @pytest.mark.asyncio
# async def test_check_limits_multiple_routes(limits_handler):
#     """
#     Demonstrates that routeA calls do not count against routeB's per-minute limit.
#     """
#     # Clear logs
#     clear_query = f"DELETE FROM {limits_handler._get_table_name(limits_handler.TABLE_NAME)}"
#     await limits_handler.connection_manager.execute_query(clear_query)

#     import uuid
#     from shared.abstractions import User
#     user_id = uuid.uuid4()
#     routeA = "/v3/retrieval/rag"
#     routeB = "/v3/retrieval/search"

#     # Suppose routeA has a limit of 2/min, routeB has a limit of 3/min
#     # (You can do this by setting config.route_limits[routeA].route_per_min, etc.)
#     # Or just rely on your global config if needed.

#     test_user = User(
#         id=user_id,
#         email="test@example.com",
#         is_active=True,
#         is_verified=True,
#         is_superuser=False,
#         limits_overrides=None,
#     )

#     # 1) Make 2 calls to routeA
#     await limits_handler.check_limits(test_user, routeA)
#     await limits_handler.log_request(user_id, routeA)

#     await limits_handler.check_limits(test_user, routeA)
#     await limits_handler.log_request(user_id, routeA)
#     await limits_handler.check_limits(test_user, routeA)
#     await limits_handler.log_request(user_id, routeA)

#     # 2) Confirm next call to routeA fails if the limit is 2/min
#     with pytest.raises(ValueError, match="Per-route per-minute rate limit exceeded"):
#         await limits_handler.check_limits(test_user, routeA)

#     # 3) Meanwhile, routeB usage should be unaffected
#     #    We can still do 3 calls to routeB (assuming route_per_min=3).
#     await limits_handler.check_limits(test_user, routeB)
#     await limits_handler.log_request(user_id, routeB)
#     await limits_handler.check_limits(test_user, routeB)
#     await limits_handler.log_request(user_id, routeB)
#     await limits_handler.check_limits(test_user, routeB)
#     await limits_handler.log_request(user_id, routeB)


@pytest.mark.asyncio
async def test_route_specific_monthly_usage(limits_handler):
    """Confirm that monthly usage is tracked per-route and doesn't get
    incremented by calls to other routes."""
    # 1) Clear existing logs
    clear_query = f"DELETE FROM {limits_handler._get_table_name(limits_handler.TABLE_NAME)}"
    await limits_handler.connection_manager.execute_query(clear_query)

    # 2) Setup
    user_id = uuid.uuid4()
    routeA = "/v3/retrieval/rag"
    routeB = "/v3/retrieval/search"
    test_user = User(
        id=user_id,
        email="test_monthly_routes@example.com",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        limits_overrides=None,
    )

    # 3) Log 5 requests for routeA
    for _ in range(5):
        await limits_handler.log_request(user_id, routeA)

    # 4) Check monthly usage for routeA => should be 5
    routeA_monthly = await limits_handler._count_monthly_requests(
        user_id, routeA)
    assert routeA_monthly == 5, f"Expected 5 for routeA, got {routeA_monthly}"

    # routeB => should still be 0
    routeB_monthly = await limits_handler._count_monthly_requests(
        user_id, routeB)
    assert routeB_monthly == 0, f"Expected 0 for routeB, got {routeB_monthly}"

    # 5) Now log 3 requests for routeB
    for _ in range(3):
        await limits_handler.log_request(user_id, routeB)

    # Re-check usage
    routeA_monthly_after = await limits_handler._count_monthly_requests(
        user_id, routeA)
    routeB_monthly_after = await limits_handler._count_monthly_requests(
        user_id, routeB)
    assert routeA_monthly_after == 5, (
        f"RouteA usage changed unexpectedly: {routeA_monthly_after}")
    assert routeB_monthly_after == 3, (
        f"RouteB usage is wrong: {routeB_monthly_after}")

    # Additionally confirm total usage across all routes
    global_monthly = await limits_handler._count_monthly_requests(user_id,
                                                                  route=None)
    assert global_monthly == 8, (
        f"Expected total of 8 monthly requests, got {global_monthly}")
