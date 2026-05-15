from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class MessageType(str, Enum):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    ERROR = "ERROR"


@dataclass
class Message:
    sender: str
    recipient: str
    type: MessageType
    payload: dict
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_response(self, payload: dict) -> Message:
        """Create a RESPONSE message correlated to this REQUEST."""
        return Message(
            sender=self.recipient,
            recipient=self.sender,
            type=MessageType.RESPONSE,
            payload=payload,
            correlation_id=self.id,
        )

    def to_error(self, error_message: str) -> Message:
        """Create an ERROR message correlated to this REQUEST."""
        return Message(
            sender=self.recipient,
            recipient=self.sender,
            type=MessageType.ERROR,
            payload={"error": error_message},
            correlation_id=self.id,
        )
