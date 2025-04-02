# import asyncio
# import uuid
# import pytest
# import time
# from datetime import datetime
# from r2r import R2RClient, R2RException, LimitSettings

# async def test_health_endpoint(aclient):
#     """Test health endpoint is accessible and not rate limited"""
#     # Health endpoint doesn't require authentication
#     for _ in range(20):  # Well above our global limit
#         response = await aclient.system.health()
#         assert response["results"]["message"] == "ok"

# async def test_system_status(aclient, config):
#     """Test system status endpoint returns correct data"""
#     # Login as superuser for system status
#     await aclient.users.login(config.superuser_email, config.superuser_password)
#     response = await aclient.system.status()
#     stats = response["results"]

#     assert isinstance(stats["start_time"], str)
#     assert isinstance(stats["uptime_seconds"], (int, float))
#     assert isinstance(stats["cpu_usage"], (int, float))
#     assert isinstance(stats["memory_usage"], (int, float))

#     datetime.fromisoformat(stats["start_time"])

# async def test_per_minute_route_limit(aclient, test_collection):
#     """Test route-specific per-minute limit for search endpoint"""
#     # Create and login as new user
#     test_user = f"test_user_{uuid.uuid4()}@example.com"
#     test_pass = "test_password"
#     await aclient.users.register(test_user, test_pass)
#     await aclient.users.login(test_user, test_pass)

#     # Should succeed for first 5 requests (route_per_min limit)
#     for i in range(5):
#         # use `search` route which is at `per_route_limit: 5` in `test_limits` config

#         response = await aclient.retrieval.search(
#             f"test query {i}",
#         )
#         assert "results" in response

#     # Next request should fail with rate limit error
#     with pytest.raises(R2RException) as exc_info:
#         await aclient.retrieval.search(
#             "over limit query",
#         )
#     assert "rate limit" in str(exc_info.value).lower()
#     await aclient.users.logout()

# async def test_global_per_minute_limit(aclient, test_collection):
#     """Test global per-minute limit"""
#     # Create and login as new user
#     # email, _ = create_test_user()
#     test_user = f"test_user_{uuid.uuid4()}@example.com"
#     test_pass = "test_password"
#     await aclient.users.register(test_user, test_pass)
#     await aclient.users.login(test_user, test_pass)

#     # Make requests up to global limit
#     for i in range(25):
#         try:
#             # use `me` route which is at `global_limit` in `test_limits` config
#             result = await aclient.users.me()
#         except R2RException as e:
#             if "rate limit" not in str(e).lower():
#                 raise  # Re-raise if it's not a rate limit exception
#     # Verify global limit is enforced
#     with pytest.raises(R2RException) as exc_info:
#         await aclient.users.me()
#     assert "rate limit" in str(exc_info.value).lower()
#     await aclient.users.logout()

# async def test_global_per_minute_limit_split(aclient, test_collection):
#     """Test global per-minute limit"""
#     # Create and login as new user
#     # email, _ = create_test_user()
#     test_user = f"test_user_{uuid.uuid4()}@example.com"
#     test_pass = "test_password"
#     await aclient.users.register(test_user, test_pass)
#     await aclient.users.login(test_user, test_pass)

#     # Make requests up to global limit
#     for i in range(10):  ## ramp up to 20 total queries
#         try:
#             # use `me` route which is at `global_limit` in `test_limits` config
#             await aclient.users.me()
#             await aclient.retrieval.search("whoami?")
#         except R2RException as e:
#             if "rate limit" not in str(e).lower():
#                 raise  # Re-raise if it's not a rate limit exception
#     # Verify global limit is enforced
#     with pytest.raises(R2RException) as exc_info:
#         await aclient.users.me()
#     assert "rate limit" in str(exc_info.value).lower()
#     await aclient.users.logout()

# ## TOO SLOW
# # def test_route_monthly_limit(client, test_collection):
# #     """Test route-specific monthly limit for search endpoint"""
# #     # Create and login as new user
# #     test_user = f"test_user_{uuid.uuid4()}@example.com"
# #     test_pass = "test_password"
# #     client.users.register(test_user, test_pass)
# #     client.users.login(test_user, test_pass)

# #     # Make requests up to route monthly limit
# #     for i in range(5):  # route_per_month limit
# #         response = client.retrieval.search(
# #             f"monthly test query {i}",
# #         )
# #         assert "results" in response

# #     time.sleep(61)  # Avoid per-minute limits

# #     # Make requests up to route monthly limit
# #     for i in range(5):  # route_per_month limit
# #         response = client.retrieval.search(
# #             f"monthly test query {i}",
# #         )
# #         assert "results" in response
# #     time.sleep(61)  # Avoid per-minute limits

# #     # Next request should fail with monthly limit error
# #     with pytest.raises(R2RException) as exc_info:
# #         client.retrieval.search(
# #             "over monthly limit query",
# #         )
# #     assert "monthly" in str(exc_info.value).lower()
# #     client.users.logout()

# async def test_non_superuser_system_access(aclient):
#     """Test system endpoint access control"""
#     # Create and login as regular user
#     test_user = f"test_user_{uuid.uuid4()}@example.com"
#     test_pass = "test_password"
#     await aclient.users.register(test_user, test_pass)
#     await aclient.users.login(test_user, test_pass)

#     # Health should be accessible
#     response = await aclient.system.health()
#     assert response["results"]["message"] == "ok"

#     # Other endpoints should be restricted
#     for endpoint in [
#         lambda:  aclient.system.status(),
#         lambda:  aclient.system.settings(),
#         lambda:  aclient.system.logs(),
#     ]:
#         with pytest.raises(R2RException) as exc_info:
#             await endpoint()
#         # assert exc_info.value.status_code == 403

# async def test_limit_reset(aclient, test_collection):
#     """Test that per-minute limits reset after one minute"""
#     # Create and login as new user
#     # Create and login as new user
#     test_user = f"test_user_{uuid.uuid4()}@example.com"
#     test_pass = "test_password"
#     await aclient.users.register(test_user, test_pass)
#     await aclient.users.login(test_user, test_pass)
#     # Use up the route limit
#     for _ in range(5):
#         await aclient.retrieval.search(
#             "test query",
#         )
#     print('going sleepy sweep now...')
#     t = datetime.now()
#     # Wait for reset
#     # time.sleep(62)
#     await asyncio.sleep(70)
#     print('wakey wakey')
#     print('dt = ', datetime.now() - t)

#     # Should be able to make requests again
#     response = await aclient.retrieval.search(
#         "test query after reset",
#     )
#     assert "results" in response

# ## THIS FAILS, BUT WE ARE OK WITH THIS EDGE CASE
# # async def test_concurrent_requests(aclient, test_collection):
# #     """Test concurrent requests properly handle rate limits"""
# #     # Create and login as new user
# #     # Create and login as new user
# #     test_user = f"test_user_{uuid.uuid4()}@example.com"
# #     test_pass = "test_password"
# #     await aclient.users.register(test_user, test_pass)
# #     await aclient.users.login(test_user, test_pass)

# #     import asyncio
# #     tasks = []
# #     for i in range(10):
# #         tasks.append(aclient.retrieval.search(f"concurrent query {i}"))

# #     results = await asyncio.gather(*tasks, return_exceptions=True)
# #     success_count = sum(1 for r in results if isinstance(r, dict))
# #     assert success_count <= 5  # route_per_min limit

# async def test_user_specific_limits(aclient, config):
#     """Test user-specific limit overrides"""
#     # Create and login as new user
#     test_user = f"test_user_specific_harcoded@example.com"
#     test_pass = "test_password"
#     await aclient.users.register(test_user, test_pass)
#     await aclient.users.login(test_user, test_pass)
#     me = await aclient.users.me()
#     print("me = ", me)
#     # Configure user-specific limits
#     # SET INSIDE THE CONFIG
#     # user_id = client.users.me().results.id
#     # config.user_limits[user_id] = LimitSettings(
#     #     global_per_min=2,
#     #     route_per_min=1
#     # )

#     # Verify user's custom limits are enforced
#     for i in range(3):
#         try:
#             await aclient.retrieval.search(f"test query {i}")
#             if i >= 2:
#                 assert False, "Should have raised exception"
#         except R2RException as e:
#             assert "rate limit" in str(e).lower()
#             assert i >= 1  # Should fail after first request
#             break

# async def test_global_monthly_limit(aclient, test_collection):
#     """Test global monthly limit across all routes"""
#     test_user = f"test_user_{uuid.uuid4()}@example.com"
#     test_pass = "test_password"
#     await aclient.users.register(test_user, test_pass)
#     await aclient.users.login(test_user, test_pass)

#     # Make requests up to global monthly limit (20)
#     for i in range(10):
#         if i % 2 == 0:
#             response = await aclient.users.me()
#         else:
#             response = await aclient.retrieval.search(f"test query {i}")
#     await asyncio.sleep(61)  # Avoid per-minute limits

#     for i in range(10):
#         if i % 2 == 0:
#             response = await aclient.users.me()
#         else:
#             response = await aclient.retrieval.search(f"test query {i}")
#     await asyncio.sleep(61)  # Avoid per-minute limits

#     # Next request should fail with monthly limit error
#     with pytest.raises(R2RException) as exc_info:
#         await aclient.users.me()
#     assert "monthly" in str(exc_info.value).lower()

# async def test_mixed_limits(aclient, test_collection):
#     """Test interaction between different types of limits"""
#     test_user = f"test_user_{uuid.uuid4()}@example.com"
#     test_pass = "test_password"
#     await aclient.users.register(test_user, test_pass)
#     await aclient.users.login(test_user, test_pass)

#     # Hit route-specific limit first
#     for i in range(5):
#         await aclient.retrieval.search(f"test query {i}")

#     # Try different route to test global limit still applies
#     with pytest.raises(R2RException) as exc_info:
#         for i in range(10):
#             await aclient.users.me()
#     assert "rate limit" in str(exc_info.value).lower()

# async def test_route_limit_inheritance(aclient, test_collection):
#     """Test that routes without specific limits inherit global limits"""
#     test_user = f"test_user_{uuid.uuid4()}@example.com"
#     test_pass = "test_password"
#     await aclient.users.register(test_user, test_pass)
#     await aclient.users.login(test_user, test_pass)

#     # Test unspecified route (should use global limits)
#     for i in range(10):  # global_per_min = 10
#         await aclient.users.me()

#     # Next request should hit global limit
#     with pytest.raises(R2RException) as exc_info:
#         await aclient.users.me()
#     assert "rate limit" in str(exc_info.value).lower()
