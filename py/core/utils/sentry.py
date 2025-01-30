import contextlib
import os

import sentry_sdk


def init_sentry():
    dsn = os.getenv("R2R_SENTRY_DSN")
    if not dsn:
        return

    with contextlib.suppress(Exception):
        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("R2R_SENTRY_ENVIRONMENT", "not_set"),
            traces_sample_rate=float(
                os.getenv("R2R_SENTRY_TRACES_SAMPLE_RATE", 1.0)
            ),
            profiles_sample_rate=float(
                os.getenv("R2R_SENTRY_PROFILES_SAMPLE_RATE", 1.0)
            ),
        )
