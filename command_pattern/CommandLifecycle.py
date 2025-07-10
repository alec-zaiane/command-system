"""Helper classes for command lifecycle management."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LifecycleResponse:
    should_proceed: bool
    reason: Optional[str] = None


class DeferResponse(LifecycleResponse):
    """
    Response indicating whether to defer command execution.

    Use `DeferResponse.defer()` to defer the command execution, or `DeferResponse.proceed()` to continue.
    """

    @classmethod
    def defer(cls, reason: Optional[str]) -> "DeferResponse":
        """Defer the command execution, optionally providing a reason."""
        return cls(should_proceed=False, reason=reason)

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
        """Cancel the command execution, optionally providing a reason."""
        return cls(should_proceed=False, reason=reason)

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
        """Indicate failed command execution, optionally providing a reason."""
        return cls(should_proceed=False, reason=reason)
