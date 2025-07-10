from dataclasses import dataclass
from CommandLifecycle import ResponseStatus


@dataclass
class Response:
    status: ResponseStatus

    def __repr__(self):
        return f"Response(status={self.status})"
