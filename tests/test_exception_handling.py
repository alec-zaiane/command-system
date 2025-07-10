from dataclasses import dataclass
from typing import Optional

from command_system import (
    Command,
    CommandArgs,
    CommandQueue,
    CancelResponse,
    DeferResponse,
    ExecutionResponse,
    CommandResponse,
    ResponseStatus,
)


@dataclass
class RaiseExceptionArgs(CommandArgs):
    defer_times: int = 0
    cancel: bool = False
    fail_when_executing: bool = True
    message: Optional[str] = None


class RaiseExceptionCommand(Command[RaiseExceptionArgs, CommandResponse]):
    ARGS = RaiseExceptionArgs
    _response_type = CommandResponse

    def execute(self) -> ExecutionResponse:
        if self.args.fail_when_executing:
            raise ValueError(self.args.message or "An error occurred in the command.")
        return ExecutionResponse.success()

    def should_cancel(self) -> CancelResponse:
        if self.args.cancel:
            return CancelResponse.cancel("Command was canceled by user request.")
        return CancelResponse.proceed()

    def should_defer(self) -> DeferResponse:
        self.args.defer_times -= 1
        if self.args.defer_times > -1:
            return DeferResponse.defer("Defer requested by command.")
        return DeferResponse.proceed()


def test_exception_handling():
    """Test that exceptions in a command's `execute` method result in a failed response."""
    queue = CommandQueue()

    # Test command that raises an exception
    command = RaiseExceptionCommand(
        RaiseExceptionCommand.ARGS(fail_when_executing=True, message="Test exception")
    )
    response = queue.submit(command)

    assert response.status == ResponseStatus.CREATED
    queue_response = queue.process_once()
    assert response.status == ResponseStatus.FAILED
    assert queue_response.command_log[-1].responses[-1].reason == "Test exception"


def test_defer_callback_exception_handling():
    """Test that exceptions in command callbacks are handled gracefully."""
    queue = CommandQueue()
    command = RaiseExceptionCommand(
        RaiseExceptionCommand.ARGS(fail_when_executing=False, defer_times=1)
    )

    def fail_defer_callback(response: DeferResponse):
        raise ValueError("Defer callback failed.")

    command.add_on_defer_callback(fail_defer_callback)
    response = queue.submit(command)
    queue_response = queue.process_once()

    assert response.status == ResponseStatus.PENDING
    assert queue_response.command_log[-1].responses[-1].executed_callbacks[-1].errored


def test_cancel_callback_exception_handling():
    """Test that exceptions in cancel callbacks are handled gracefully."""
    queue = CommandQueue()
    command = RaiseExceptionCommand(RaiseExceptionCommand.ARGS(cancel=True, defer_times=1))

    def good_defer_callback(response: DeferResponse):
        pass  # do nothing

    def fail_cancel_callback(response: CancelResponse):
        raise ValueError("Cancel callback failed.")

    command.add_on_cancel_callback(fail_cancel_callback)
    command.add_on_defer_callback(good_defer_callback)
    response = queue.submit(command)
    queue_response = queue.process_all()

    assert response.status == ResponseStatus.CANCELED
    assert queue_response.command_log[-1].responses[-1].executed_callbacks[-1].errored
    assert queue_response.command_log[-2].responses[-1].executed_callbacks[-1].succeeded


def test_execute_callback_exception_handling():
    """Test that exceptions in execute callbacks are handled gracefully."""
    queue = CommandQueue()
    command = RaiseExceptionCommand(RaiseExceptionCommand.ARGS(fail_when_executing=False))

    def fail_execute_callback(response: ExecutionResponse):
        raise ValueError("Execute callback failed.")

    command.add_on_execute_callback(fail_execute_callback)
    response = queue.submit(command)
    queue_response = queue.process_once()

    assert response.status == ResponseStatus.COMPLETED
    assert queue_response.command_log[-1].responses[-1].executed_callbacks[-1].errored
    assert response.status == ResponseStatus.COMPLETED
