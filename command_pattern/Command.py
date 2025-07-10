from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generic, Type, TypeVar, final

from .CommandLifecycle import (
    CancelResponse,
    DeferResponse,
    ExecutionResponse,
    CallbackRecord,
    LifecycleResponse,
)
from .CommandResponse import CommandResponse, ResponseStatus


@dataclass
class CommandArgs:
    pass


ArgsType = TypeVar("ArgsType", bound=CommandArgs)
ResponseType = TypeVar("ResponseType", bound=CommandResponse)

_LifecycleResponseType = TypeVar("_LifecycleResponseType", bound="LifecycleResponse")


class Command(ABC, Generic[ArgsType, ResponseType]):
    ARGS: Type[ArgsType]
    _response_type: Type[ResponseType]

    def __init__(self, args: ArgsType):
        self._args = args
        self.response = self._init_response()

        # callbacks
        self._on_defer_callbacks: list[Callable[[DeferResponse], None]] = []
        self._on_cancel_callbacks: list[Callable[[CancelResponse], None]] = []
        self._on_execute_callbacks: list[Callable[[ExecutionResponse], None]] = []

    @property
    def args(self) -> ArgsType:
        """Get the command arguments."""
        return self._args

    def _init_response(self) -> ResponseType:
        """
        Initialize the response object for the command.

        Subclasses may override this method if their response requires specific initialization logic.
        Otherwise, simply declare `_response_type` as a class variable, and it will be automatically initialized.

        Returns:
            ResponseType: An instance of the response type for this command.
        """
        return self._response_type(status=ResponseStatus.CREATED)

    def should_defer(self) -> DeferResponse:
        """
        Determine if the command should be deferred.

        By default, commands do not defer. Subclasses can override this method to provide custom deferral logic.

        Returns:
            DeferResponse: A response indicating whether to defer the command execution.
        """
        return DeferResponse.proceed()

    def should_cancel(self) -> CancelResponse:
        """
        Determine if the command should be canceled.

        By default, commands do not cancel. Subclasses can override this method to provide custom cancellation logic.

        Returns:
            CancelResponse: A response indicating whether to cancel the command execution.
        """
        return CancelResponse.proceed()

    @abstractmethod
    def execute(self) -> ExecutionResponse:
        """
        Execute the command.

        Subclasses must implement this method to perform the actual command logic.

        Returns:
            ExecutionResponse: A response indicating the status/result of the command execution.
            **Do not put your payload in the ExecutionResponse**; use a custom `self.response` class instead.
        """
        raise NotImplementedError("Subclasses must implement the execute method.")

    # Callbacks
    @final
    def _call_single_callback(
        self, callback: Callable[[_LifecycleResponseType], None], response: _LifecycleResponseType
    ) -> None:
        """
        [Private, do not override]

        Call a single callback with the given response.

        This method ensures that the callback is executed safely, and any exceptions raised are recorded.

        Args:
            callback (Callable[[_LifecycleResponseType], None]): The callback function to be called.
            response (_LifecycleResponseType): The response to pass to the callback.
        """
        try:
            callback(response)
            response.executed_callbacks.append(CallbackRecord(callback=callback, error=None))
        except Exception as e:
            response.executed_callbacks.append(CallbackRecord(callback=callback, error=e))

    @final
    def add_on_defer_callback(self, callback: Callable[[DeferResponse], None]) -> None:
        """
        Add a callback to be called when the command is deferred.

        The callback will only be called if `should_defer()` returns `DeferResponse.defer()`.

        Args:
            callback (Callable[[DeferResponse], None]): The callback function to be called.
        """
        self._on_defer_callbacks.append(callback)

    def call_on_defer_callbacks(self, response: DeferResponse) -> None:
        """
        Call all registered on-defer callbacks with the given response.

        Args:
            response (DeferResponse): The response to pass to the callbacks.
        """
        for callback in self._on_defer_callbacks:
            self._call_single_callback(callback, response)

    @final
    def add_on_cancel_callback(self, callback: Callable[[CancelResponse], None]) -> None:
        """
        Add a callback to be called when the command is canceled.

        The callback will only be called if `should_cancel()` returns `CancelResponse.cancel()`.

        Args:
            callback (Callable[[CancelResponse], None]): The callback function to be called.
        """
        self._on_cancel_callbacks.append(callback)

    def call_on_cancel_callbacks(self, response: CancelResponse) -> None:
        """
        Call all registered on-cancel callbacks with the given response.

        Args:
            response (CancelResponse): The response to pass to the callbacks.
        """
        for callback in self._on_cancel_callbacks:
            self._call_single_callback(callback, response)

    @final
    def add_on_execute_callback(self, callback: Callable[[ExecutionResponse], None]) -> None:
        """
        Add a callback to be called when the command is executed.

        The callback will always be called after `execute()` is called, regardless of the result.

        Args:
            callback (Callable[[ExecutionResponse], None]): The callback function to be called.
        """
        self._on_execute_callbacks.append(callback)

    def call_on_execute_callbacks(self, response: ExecutionResponse) -> None:
        """
        Call all registered on-execute callbacks with the given response.

        Args:
            response (ExecutionResponse): The response to pass to the callbacks.
        """
        for callback in self._on_execute_callbacks:
            self._call_single_callback(callback, response)
