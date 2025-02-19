import uuid
from typing import Any, Optional


class BaseTelemetryEvent:

    def __init__(self, event_type: str, properties: dict[str, Any]):
        self.event_type = event_type
        self.properties = properties
        self.event_id = str(uuid.uuid4())


class FeatureUsageEvent(BaseTelemetryEvent):

    def __init__(
        self,
        user_id: str,
        feature: str,
        properties: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            "FeatureUsage",
            {
                "user_id": user_id,
                "feature": feature,
                "properties": properties or {},
            },
        )


class ErrorEvent(BaseTelemetryEvent):

    def __init__(
        self,
        user_id: str,
        endpoint: str,
        error_message: str,
        properties: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            "Error",
            {
                "user_id": user_id,
                "endpoint": endpoint,
                "error_message": error_message,
                "properties": properties or {},
            },
        )
