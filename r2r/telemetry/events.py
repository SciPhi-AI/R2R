import uuid
from typing import Any, Dict


class BaseTelemetryEvent:
    def __init__(self, event_type: str, properties: Dict[str, Any]):
        self.event_type = event_type
        self.properties = properties
        self.event_id = str(uuid.uuid4())


class DailyActiveUserEvent(BaseTelemetryEvent):
    def __init__(self, user_id: str):
        super().__init__("DailyActiveUser", {"user_id": user_id})


class FeatureUsageEvent(BaseTelemetryEvent):
    def __init__(self, user_id: str, feature: str):
        super().__init__(
            "FeatureUsage", {"user_id": user_id, "feature": feature}
        )


class ErrorEvent(BaseTelemetryEvent):
    def __init__(self, user_id: str, endpoint: str, error_message: str):
        super().__init__(
            "Error",
            {
                "user_id": user_id,
                "endpoint": endpoint,
                "error_message": error_message,
            },
        )


class RequestLatencyEvent(BaseTelemetryEvent):
    def __init__(self, endpoint: str, latency: float):
        super().__init__(
            "RequestLatency", {"endpoint": endpoint, "latency": latency}
        )


class GeographicDistributionEvent(BaseTelemetryEvent):
    def __init__(self, user_id: str, country: str):
        super().__init__(
            "GeographicDistribution", {"user_id": user_id, "country": country}
        )


class SessionDurationEvent(BaseTelemetryEvent):
    def __init__(self, user_id: str, duration: float):
        super().__init__(
            "SessionDuration", {"user_id": user_id, "duration": duration}
        )


class UserPathEvent(BaseTelemetryEvent):
    def __init__(self, user_id: str, path: str):
        super().__init__("UserPath", {"user_id": user_id, "path": path})
