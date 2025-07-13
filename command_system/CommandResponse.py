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

    def set_canceled(self) -> None:
        """
        Set the response status to CANCELED.
        """
        self.status = ResponseStatus.CANCELED

    def set_failed(self) -> None:
        """
        Set the response status to FAILED.
        """
        self.status = ResponseStatus.FAILED

    def set_completed(self) -> None:
        """
        Set the response status to COMPLETED.
        """
        self.status = ResponseStatus.COMPLETED
