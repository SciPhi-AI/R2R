import asyncio
import random
import statistics
import time
from dataclasses import dataclass
from glob import glob

from r2r import R2RAsyncClient

# Configuration
NUM_USERS = 25
QUERIES_PER_SECOND = 5
TEST_DURATION_SECONDS = 30
RAMP_UP_SECONDS = 5
STEADY_STATE_SECONDS = 20
RAMP_DOWN_SECONDS = 5

# Adjust timeouts as needed
REQUEST_TIMEOUT = 10  # seconds
LOGIN_TIMEOUT = 5
REGISTER_TIMEOUT = 5
DOC_UPLOAD_TIMEOUT = 10

# Test queries
QUERIES = [
    "Aristotle",
    "Plato",
    "Socrates",
    "Confucius",
    "Kant",
    "Nietzsche",
    "Descartes",
    "Hume",
    "Hegel",
    "Aquinas",
]


@dataclass
class Metrics:
    start_time: float
    end_time: float
    status: str
    duration_ms: float


class LoadTester:

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.metrics: list[Metrics] = []
        self.users: list[dict] = []
        self.running = True
        print("making an async client...")
        self.client = R2RAsyncClient(base_url)

    async def safe_call(self, coro, timeout, operation_desc="operation"):
        """Safely call an async function with a timeout and handle
        exceptions."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            print(
                f"[TIMEOUT] {operation_desc} took longer than {timeout} seconds"
            )
        except Exception as e:
            print(f"[ERROR] Exception during {operation_desc}: {e}")
        return None

    async def register_login_ingest_user(self, user_email: str, password: str):
        """Register and login a single user with robust error handling."""
        # Register user
        reg_result = await self.safe_call(
            self.client.users.create(user_email, password),
            timeout=REGISTER_TIMEOUT,
            operation_desc=f"register user {user_email}",
        )
        if reg_result is None:
            print(
                f"Registration may have failed or user {user_email} already exists."
            )

        # Login user
        login_result = await self.safe_call(
            self.client.users.login(user_email, password),
            timeout=LOGIN_TIMEOUT,
            operation_desc=f"login user {user_email}",
        )
        user = ({
            "email": user_email,
            "password": password
        } if login_result else None)

        # Ingest documents for user
        files = glob("core/examples/data/*")
        for file in files:
            with open(file, "r"):
                try:
                    pass
                    # await self.client.documents.create(file_path=file)
                    # await self.safe_call(
                    #     self.client.documents.create(file_path=file, run_with_orchestration=False),
                    #     timeout=DOC_UPLOAD_TIMEOUT,
                    #     operation_desc=f"document ingestion {file} for {user_email}"
                    # )
                except:
                    pass

        return user

    async def setup_users(self):
        """Initialize users and their documents."""
        print("Setting up users...")
        setup_tasks = []

        for i in range(NUM_USERS):
            user_email = f"user_{i}@test.com"
            password = "password"
            task = self.register_login_ingest_user(user_email, password)
            setup_tasks.append(task)

        # Wait for all user setups to complete
        user_results = await asyncio.gather(*setup_tasks)
        self.users = [user for user in user_results if user is not None]

        print(f"Setup complete! Successfully set up {len(self.users)} users")

    async def run_user_queries(self, user: dict):
        """Run queries for a single user, with timeouts and error handling."""
        while self.running:
            # Login before query
            login_res = await self.safe_call(
                self.client.users.login(user["email"], user["password"]),
                timeout=LOGIN_TIMEOUT,
                operation_desc=f"login for querying {user['email']}",
            )
            if login_res is None:
                # Could not login, wait and try again
                await asyncio.sleep(1)
                continue

            # Perform random search
            query_1 = random.choice(QUERIES)
            query_2 = random.choice(QUERIES)
            query_3 = random.choice(QUERIES)
            query = f"{query_1} {query_2} {query_3}"

            start_time = time.time()

            search_res = await self.safe_call(
                self.client.retrieval.search(query),
                timeout=REQUEST_TIMEOUT,
                operation_desc=f"search '{query}' for {user['email']}",
            )

            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            if search_res is not None:
                status = "success"
            else:
                status = "error"

            # Record metrics
            self.metrics.append(
                Metrics(
                    start_time=start_time,
                    end_time=end_time,
                    status=status,
                    duration_ms=duration_ms,
                ))

            # Wait according to queries per second rate
            await asyncio.sleep(max(0, 1 / QUERIES_PER_SECOND))

    def calculate_statistics(self):
        """Calculate and print test statistics."""
        durations = [m.duration_ms for m in self.metrics]
        successful_requests = len(
            [m for m in self.metrics if m.status == "success"])
        failed_requests = len([m for m in self.metrics if m.status == "error"])

        print("\nTest Results:")
        print(f"Total Requests: {len(self.metrics)}")
        print(f"Successful Requests: {successful_requests}")
        print(f"Failed Requests: {failed_requests}")

        if durations:
            print("\nLatency Statistics (ms):")
            print(f"Min: {min(durations) / 1000.0:.2f}")
            print(f"Max: {max(durations) / 1000.0:.2f}")
            print(f"Mean: {statistics.mean(durations) / 1000.0:.2f}")
            print(f"Median: {statistics.median(durations) / 1000.0:.2f}")
            try:
                print(
                    f"95th Percentile: {statistics.quantiles(durations, n=20)[-1] / 1000.0:.2f}"
                )
            except Exception:
                pass

        print(
            f"\nRequests per second: {len(self.metrics) / TEST_DURATION_SECONDS:.2f}"
        )

    async def run_load_test(self):
        """Main load test execution."""
        await self.setup_users()

        if not self.users:
            print("No users were successfully set up. Exiting test.")
            return

        print(f"Starting load test with {len(self.users)} users...")
        print(f"Ramp up: {RAMP_UP_SECONDS}s")
        print(f"Steady state: {STEADY_STATE_SECONDS}s")
        print(f"Ramp down: {RAMP_DOWN_SECONDS}s")

        tasks = [
            asyncio.create_task(self.run_user_queries(user))
            for user in self.users
        ]

        # Run for specified duration
        await asyncio.sleep(TEST_DURATION_SECONDS)
        self.running = False

        # Give tasks some time to exit gracefully
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=20)
        except asyncio.TimeoutError:
            print(
                "[WARNING] Not all tasks finished promptly after stopping. Cancelling tasks."
            )
            for t in tasks:
                if not t.done():
                    t.cancel()
            # Wait again for tasks to cancel
            await asyncio.gather(*tasks, return_exceptions=True)

        self.calculate_statistics()


def main():
    load_tester = LoadTester("http://localhost:7280")
    asyncio.run(load_tester.run_load_test())


if __name__ == "__main__":
    main()
