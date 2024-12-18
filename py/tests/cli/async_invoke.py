from typing import Any, Tuple, Type, cast
from types import TracebackType
import asyncclick as click
from click.testing import CliRunner, Result
from click import Abort


async def async_invoke(
    runner: CliRunner, cmd: click.Command, *args: str, **kwargs: Any
) -> Result:
    """Helper function to invoke async Click commands in tests."""
    exit_code = 0
    exception: BaseException | None = None
    exc_info: (
        Tuple[Type[BaseException], BaseException, TracebackType] | None
    ) = None

    with runner.isolation() as out_err:
        stdout, stderr = out_err
        try:
            return_value = await cmd.main(
                args=args, standalone_mode=False, **kwargs
            )
        except Abort as e:
            exit_code = 1
            exception = cast(BaseException, e)
            if e.__traceback__:
                exc_info = (BaseException, exception, e.__traceback__)
            return_value = None
        except Exception as e:
            exit_code = 1
            exception = cast(BaseException, e)
            if e.__traceback__:
                exc_info = (BaseException, exception, e.__traceback__)
            return_value = None

        # Always ensure we have bytes objects, not None
        stdout_bytes = stdout.getvalue() or b""
        stderr_bytes = stderr.getvalue() if stderr else b""

        return Result(
            runner=runner,
            stdout_bytes=stdout_bytes,
            stderr_bytes=stderr_bytes,
            return_value=return_value,
            exit_code=exit_code,
            exception=exception,
            exc_info=exc_info,
        )
