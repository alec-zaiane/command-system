from dataclasses import dataclass
from enum import Enum


class ResponseStatus(Enum):
    CREATED = "created"
    PENDING = "pending"
    CANCELED = "canceled"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass
class CommandResponse:
    """
    Base class for command responses.
    """

    status: ResponseStatus

    def __repr__(self):  # pragma: no cover
        return f"CommandResponse(status={self.status})"
