from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar, Type

from Response import Response, ResponseStatus
from CommandLifecycle import DeferResponse, CancelResponse, ExecutionResponse


@dataclass
class CommandArgs:
    pass


ArgsType = TypeVar("ArgsType", bound=CommandArgs)
ResponseType = TypeVar("ResponseType", bound=Response)


class Command(ABC, Generic[ArgsType, ResponseType]):
    _response_type: Type[ResponseType]

    def __init__(self, args: ArgsType):
        self.args = args
        self.response = self._init_response()

    def _init_response(self) -> ResponseType:
        """Initialize the response object. Subclasses may want to override this if their response has specific initialization logic.

        **Otherwise, simply declare `_response_type` as a class variable and it will be automatically initialized, no need to override this**

        Returns:
            ResponseType: An instance of the response type for this command.
        """
        return self._response_type(status=ResponseStatus.CREATED)

    def should_defer(self) -> DeferResponse:
        """
        Determine if the command should be deferred.

        By default, commands do not defer. Subclasses can override this if they would like.

        Returns:
            DeferResponse: A response indicating whether to defer the command execution.
        """
        return DeferResponse.proceed()

    def should_cancel(self) -> CancelResponse:
        """
        Determine if the command should be canceled.

        By default, commands do not cancel. Subclasses can override this if they would like.

        Returns:
            CancelResponse: A response indicating whether to cancel the command execution.
        """
        return CancelResponse.proceed()

    @abstractmethod
    def execute(self) -> ExecutionResponse:
        """
        Execute the command.

        Subclasses must implement this to perform the actual command logic.

        Returns:
            ExecutionResponse: A response indicating the status/result of the command execution. **Do not put your payload in the ExecutionResponse**, use a custom `self.response` class instead.
        """
        raise NotImplementedError("Subclasses must implement the execute method.")
