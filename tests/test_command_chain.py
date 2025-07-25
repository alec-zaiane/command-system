from command_system import (
    CommandChainBuilder,
    CommandQueue,
    Command,
    CommandArgs,
    CommandResponse,
    ExecutionResponse,
    CancelResponse,
    ResponseStatus,
)
from dataclasses import dataclass
import pytest


@dataclass
class AddOneArgs(CommandArgs):
    """
    Arguments for the AddOneCommand.
    """

    number: int
    should_cancel: bool = False
    should_fail: bool = False


@dataclass
class AddOneResponse(CommandResponse):
    """
    Response for the AddOneCommand.
    """

    result: int = 0


class AddOneCommand(Command[AddOneArgs, AddOneResponse]):
    ARGS = AddOneArgs
    _response_type = AddOneResponse

    def should_cancel(self) -> CancelResponse:
        if self.args.should_cancel:
            return CancelResponse.cancel("Command was cancelled")
        return CancelResponse.proceed()

    def execute(self) -> ExecutionResponse:
        if self.args.should_fail:
            return ExecutionResponse.failure("Command failed")
        self.response.result = self.args.number + 1
        return ExecutionResponse.success()


def test_command_chain_add_one():
    queue = CommandQueue()
    chain = (
        CommandChainBuilder[int, int]
        .start(
            0,
            lambda x: AddOneArgs(number=x),
            AddOneCommand,
            lambda response: response.result,
        )
        .then(
            lambda x: AddOneArgs(number=x),
            AddOneCommand,
            lambda response: response.result,
        )
        .then(
            lambda x: AddOneArgs(number=x),
            AddOneCommand,
            lambda response: response.result,
        )
        .build(queue)
    )
    queue.submit(chain)
    response = queue.process_all()
    assert chain.response.status == ResponseStatus.COMPLETED
    assert response.num_commands_processed == 4  # chain + 3 commands
    assert chain.response.output_data == 3  # 0 + 1 + 1 + 1


def test_command_chain_fail():
    queue = CommandQueue()
    chain = (
        CommandChainBuilder[int, int]
        .start(
            0,
            lambda x: AddOneArgs(number=x),
            AddOneCommand,
            lambda response: response.result,
        )
        .then(
            lambda x: AddOneArgs(number=x, should_fail=True),
            AddOneCommand,
            lambda response: response.result,
        )
        .then(
            lambda x: AddOneArgs(number=x),
            AddOneCommand,
            lambda response: response.result,
        )
        .build(queue)
    )
    queue.submit(chain)
    response = queue.process_all()
    assert chain.response.status == ResponseStatus.FAILED
    assert response.num_commands_processed == 3  # chain + good command + failed command
    assert chain.response.output_data is None  # no output data due to failure


def test_command_chain_cancel():
    queue = CommandQueue()
    chain = (
        CommandChainBuilder[int, int]
        .start(
            0,
            lambda x: AddOneArgs(number=x, should_cancel=True),
            AddOneCommand,
            lambda response: response.result,
        )
        .then(
            lambda x: AddOneArgs(number=x),
            AddOneCommand,
            lambda response: response.result,
        )
        .then(
            lambda x: AddOneArgs(number=x),
            AddOneCommand,
            lambda response: response.result,
        )
        .build(queue)
    )
    queue.submit(chain)
    response = queue.process_all()
    assert chain.response.status == ResponseStatus.FAILED
    assert response.num_commands_processed == 2  # chain + cancelled command
    assert chain.response.output_data is None  # no output data due to cancellation


def test_cannot_then_without_start():
    with pytest.raises(ValueError):
        _ = CommandChainBuilder[int, int](0, []).then(
            lambda x: AddOneArgs(number=x),
            AddOneCommand,
            lambda response: response.result,
        )
