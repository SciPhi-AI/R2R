import asyncio
import functools
import inspect
import os
import threading
import uuid
from importlib.metadata import version
from typing import Optional

import asyncclick as click
from posthog import Posthog

TELEMETRY_DISABLED = (
    os.getenv("R2R_CLI_DISABLE_TELEMETRY", "false").lower() == "true"
)

posthog: Optional[Posthog] = None

if not TELEMETRY_DISABLED:
    posthog = Posthog(
        project_api_key="phc_OPBbibOIErCGc4NDLQsOrMuYFTKDmRwXX6qxnTr6zpU",
        host="https://us.i.posthog.com",
    )
    posthog.debug = True


def telemetry(command):
    if TELEMETRY_DISABLED or posthog is None:
        # Return the command unmodified
        return command

    original_callback = command.callback
    is_async = inspect.iscoroutinefunction(original_callback)

    if is_async:

        @functools.wraps(original_callback)
        async def tracked_callback(*args, **kwargs):
            command_name = command.name

            # Extract context from args[0] if it's a Click Context
            if args and isinstance(args[0], click.Context):
                ctx = args[0]
                command_args = ctx.args
                command_params = ctx.params
            else:
                ctx = None
                command_args = []
                command_params = {}

            distinct_id = str(uuid.uuid4())

            try:
                # Await the original async callback
                result = await original_callback(*args, **kwargs)

                # Run PostHog capture in a separate thread to avoid blocking
                await asyncio.to_thread(
                    posthog.capture,
                    distinct_id=distinct_id,
                    event="cli_command",
                    properties={
                        "command": command_name,
                        "status": "success",
                        "args": command_args,
                        "params": command_params,
                        "version": version("r2r"),
                    },
                )

                return result
            except Exception as e:
                await asyncio.to_thread(
                    posthog.capture,
                    distinct_id=distinct_id,
                    event="cli_command",
                    properties={
                        "command": command_name,
                        "status": "error",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "args": command_args,
                        "params": command_params,
                        "version": version("r2r"),
                    },
                )
                raise

    else:

        @functools.wraps(original_callback)
        def tracked_callback(*args, **kwargs):
            command_name = command.name

            # Extract context from args[0] if it's a Click Context
            if args and isinstance(args[0], click.Context):
                ctx = args[0]
                command_args = ctx.args
                command_params = ctx.params
            else:
                ctx = None
                command_args = []
                command_params = {}

            distinct_id = str(uuid.uuid4())

            try:
                result = original_callback(*args, **kwargs)

                # Run PostHog capture in a separate thread to avoid blocking
                thread = threading.Thread(
                    target=posthog.capture,
                    args=(
                        distinct_id,
                        "cli_command",
                        {
                            "command": command_name,
                            "status": "success",
                            "args": command_args,
                            "params": command_params,
                            "version": version("r2r"),
                        },
                    ),
                    daemon=True,
                )
                thread.start()

                return result
            except Exception as e:
                # Run PostHog capture in a separate thread to avoid blocking
                thread = threading.Thread(
                    target=posthog.capture,
                    args=(
                        distinct_id,
                        "cli_command",
                        {
                            "command": command_name,
                            "status": "error",
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "args": command_args,
                            "params": command_params,
                            "version": version("r2r"),
                        },
                    ),
                    daemon=True,
                )
                thread.start()
                raise

    command.callback = tracked_callback
    return command
