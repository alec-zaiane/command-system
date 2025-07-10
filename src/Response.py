from dataclasses import dataclass

from enum import Enum


class ResponseStatus(Enum):
    CREATED = "created"
    PENDING = "pending"
    CANCELED = "canceled"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass
class Response:
    status: ResponseStatus

    def __repr__(self):
        return f"Response(status={self.status})"
