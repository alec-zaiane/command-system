from dataclasses import dataclass

from command_system import (
    CancelResponse,
    Command,
    CommandArgs,
    CommandQueue,
    CommandResponse,
    DeferResponse,
    DependencyAction,
    DependencyEntry,
    ExecutionResponse,
    ReasonByDependencyCheck,
    ResponseStatus,
)


@dataclass
class DoAnythingCommandArgs(CommandArgs):
    defer_times: int = 0
    cancel: bool = False
    fail: bool = False


class DoAnythingCommand(Command[DoAnythingCommandArgs, CommandResponse]):
    ARGS = DoAnythingCommandArgs
    _response_type = CommandResponse

    def should_defer(self) -> DeferResponse:
        if self.args.defer_times > 0:
            self.args.defer_times -= 1
            return DeferResponse.defer(f"Deferred with {self.args.defer_times} times remaining.")
        return DeferResponse.proceed()

    def should_cancel(self) -> CancelResponse:
        if self.args.cancel:
            return CancelResponse.cancel("Command was canceled.")
        return CancelResponse.proceed()

    def execute(self) -> ExecutionResponse:
        if self.args.fail:
            return ExecutionResponse.failure("Command execution failed.")
        return ExecutionResponse.success()


def test_created_dependencies():
    """
    Test that a command can properly report dependency actions when the dependency's status is CREATED.
    """
    previous_command = DoAnythingCommand(DoAnythingCommandArgs())
    new_command = DoAnythingCommand(
        DoAnythingCommandArgs(), dependencies=[DependencyEntry(previous_command)]
    )
    check_response = new_command.check_dependencies()
    assert check_response.status == DependencyAction.DEFER

    new_command = DoAnythingCommand(
        DoAnythingCommandArgs(),
        dependencies=[DependencyEntry(previous_command, on_pending="cancel")],
    )
    check_response = new_command.check_dependencies()
    assert check_response.status == DependencyAction.CANCEL

    new_command = DoAnythingCommand(
        DoAnythingCommandArgs(),
        dependencies=[DependencyEntry(previous_command, on_pending="proceed")],
    )
    check_response = new_command.check_dependencies()
    assert check_response.status == DependencyAction.PROCEED


def test_deferred_dependencies():
    """
    Test that a command can properly report dependency actions when the dependency's status is DEFERRED.
    """
    previous_command = DoAnythingCommand(DoAnythingCommandArgs(defer_times=1))
    queue = CommandQueue()
    queue.submit(previous_command)
    queue.process_once()
    assert previous_command.response.status == ResponseStatus.PENDING
    new_command = DoAnythingCommand(
        DoAnythingCommandArgs(), dependencies=[DependencyEntry(previous_command)]
    )
    check_response = new_command.check_dependencies()
    assert check_response.status == DependencyAction.DEFER


def test_cancelled_dependencies():
    """
    Test that a command can properly report dependency actions when the dependency's status is CANCELED.
    """
    previous_command = DoAnythingCommand(DoAnythingCommandArgs(cancel=True))
    queue = CommandQueue()
    queue.submit(previous_command)
    queue.process_once()
    assert previous_command.response.status == ResponseStatus.CANCELED
    new_command = DoAnythingCommand(
        DoAnythingCommandArgs(), dependencies=[DependencyEntry(previous_command)]
    )
    check_response = new_command.check_dependencies()
    assert check_response.status == DependencyAction.CANCEL


def test_failed_dependencies():
    """
    Test that a command can properly report dependency actions when the dependency's status is FAILED.
    """
    previous_command = DoAnythingCommand(DoAnythingCommandArgs(fail=True))
    queue = CommandQueue()
    queue.submit(previous_command)
    queue.process_once()
    assert previous_command.response.status == ResponseStatus.FAILED
    new_command = DoAnythingCommand(
        DoAnythingCommandArgs(), dependencies=[DependencyEntry(previous_command)]
    )
    check_response = new_command.check_dependencies()
    assert check_response.status == DependencyAction.CANCEL


def test_completed_dependencies():
    """
    Test that a command can properly report dependency actions when the dependency's status is COMPLETED.
    """
    previous_command = DoAnythingCommand(DoAnythingCommandArgs())
    queue = CommandQueue()
    queue.submit(previous_command)
    queue.process_once()
    assert previous_command.response.status == ResponseStatus.COMPLETED
    new_command = DoAnythingCommand(
        DoAnythingCommandArgs(), dependencies=[DependencyEntry(previous_command)]
    )
    check_response = new_command.check_dependencies()
    assert check_response.status == DependencyAction.PROCEED


def test_reason_generation():
    """
    Test that the reason for a dependency check is generated correctly.
    """
    previous_command = DoAnythingCommand(DoAnythingCommandArgs(defer_times=1))
    new_command = DoAnythingCommand(
        DoAnythingCommandArgs(), dependencies=[DependencyEntry(previous_command)]
    )
    queue = CommandQueue()
    queue.submit(previous_command)
    queue.submit(new_command)
    queue_response = queue.process_once()
    assert previous_command.response.status == ResponseStatus.PENDING
    assert new_command.response.status == ResponseStatus.PENDING
    assert isinstance(queue_response.command_log[-1].responses[-1].reason, ReasonByDependencyCheck)


def test_multiple_dependencies():
    """
    Test that a command can handle multiple dependencies correctly.

    Importantly, the severity of the dependency actions should be respected.
    """
    previous_command1 = DoAnythingCommand(DoAnythingCommandArgs(defer_times=1))
    previous_command2 = DoAnythingCommand(DoAnythingCommandArgs(cancel=True))
    previous_command3 = DoAnythingCommand(DoAnythingCommandArgs(defer_times=1))
    queue = CommandQueue()
    new_command = DoAnythingCommand(
        DoAnythingCommandArgs(),
        dependencies=[
            previous_command1,
            previous_command2,
            previous_command3,
        ],
    )
    queue.submit_many(previous_command1, previous_command2, previous_command3, new_command)
    queue_response = queue.process_once()
    assert previous_command1.response.status == ResponseStatus.PENDING
    assert previous_command2.response.status == ResponseStatus.CANCELED
    assert new_command.response.status == ResponseStatus.CANCELED
    final_log_response = queue_response.command_log[-1].responses[-1]
    assert isinstance(final_log_response.reason, ReasonByDependencyCheck)
    assert final_log_response.reason.reason.startswith("Canceled due to dependency:")
