"""Helper classes for command lifecycle management."""

from dataclasses import dataclass, field
from typing import Callable, Generic, Optional, Self, TypeVar, cast

LifecycleResponseType = TypeVar("LifecycleResponseType", bound="LifecycleResponse")


@dataclass
class CallbackRecord(Generic[LifecycleResponseType]):
    """
    Record of a callback's execution.

    Attributes:
        callback (Callable[[LifecycleResponseType], None]): The callback function that was executed.
        error (Optional[Exception]): The exception raised during the callback execution, if any.
    """

    callback: Callable[[LifecycleResponseType], None]
    error: Optional[Exception] = None

    @property
    def succeeded(self) -> bool:
        """Check if the callback executed successfully (i.e., no exception was raised)."""
        return self.error is None

    @property
    def errored(self) -> bool:
        """Check if the callback raised an exception."""
        return self.error is not None


@dataclass
class LifecycleResponseReason:
    reason: str

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.reason == other.reason


@dataclass
class ReasonByCommandMethod(LifecycleResponseReason):
    """A reason for a lifecycle response that was created by a command function (e.g., `should_defer`, `should_cancel`, etc.)."""

    pass


@dataclass
class LifecycleResponse:
    """
    Base class for lifecycle responses.

    Attributes:
        should_proceed (bool): Whether the command should proceed to the next lifecycle step.
        reason (Optional[str]): The reason for failing to proceed, must be set if `should_proceed` is `False`.
        executed_callbacks (list[CallbackRecord[Self]]): List of callback records for callbacks executed during this response.
    """

    should_proceed: bool
    reason: Optional[LifecycleResponseReason] = None
    executed_callbacks: list[CallbackRecord[Self]] = cast(
        list[CallbackRecord[Self]], field(default_factory=list)
    )


class DeferResponse(LifecycleResponse):
    """
    Response indicating whether to defer command execution.

    Use `DeferResponse.defer()` to defer the command execution, or `DeferResponse.proceed()` to continue.
    """

    @classmethod
    def defer(cls, reason: Optional[str]) -> "DeferResponse":
        """Defer the command execution, optionally providing a reason.

        The reason will be wrapped in a `ReasonByCommandMethod` instance.
        """
        return cls(
            should_proceed=False,
            reason=ReasonByCommandMethod(reason) if reason else None,
        )

    @classmethod
    def proceed(cls) -> "DeferResponse":
        """Do not defer, proceed to the next lifecycle step."""
        return cls(should_proceed=True)


class CancelResponse(LifecycleResponse):
    """
    Response indicating whether to cancel command execution.

    Use `CancelResponse.cancel()` to cancel the command execution, or `CancelResponse.proceed()` to continue.
    """

    @classmethod
    def cancel(cls, reason: Optional[str]) -> "CancelResponse":
        """Cancel the command execution, optionally providing a reason.

        The reason will be wrapped in a `ReasonByCommandMethod` instance.
        """
        return cls(
            should_proceed=False,
            reason=ReasonByCommandMethod(reason) if reason else None,
        )

    @classmethod
    def proceed(cls) -> "CancelResponse":
        """Do not cancel, proceed to the next lifecycle step."""
        return cls(should_proceed=True)


class ExecutionResponse(LifecycleResponse):
    """
    Response indicating the result of command execution.

    Use `ExecutionResponse.success()` to indicate successful execution, or `ExecutionResponse.fail()` to indicate failure.
    """

    @classmethod
    def success(cls) -> "ExecutionResponse":
        """Indicate successful command execution."""
        return cls(should_proceed=True)

    @classmethod
    def failure(cls, reason: Optional[str]) -> "ExecutionResponse":
        """Indicate failed command execution, optionally providing a reason.

        The reason will be wrapped in a `ReasonByCommandMethod` instance.
        """
        return cls(
            should_proceed=False,
            reason=ReasonByCommandMethod(reason) if reason else None,
        )
