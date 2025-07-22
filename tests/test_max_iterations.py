from dataclasses import dataclass
from typing import Callable, Optional

from command_system import (
    Command,
    CommandArgs,
    CommandQueue,
    CommandResponse,
    ExecutionResponse,
    ResponseStatus,
)


@dataclass
class RunFunctionArgs(CommandArgs):
    function: Optional[Callable[[], None]] = None


class RunFunctionCommand(Command[RunFunctionArgs, CommandResponse]):
    ARGS = RunFunctionArgs
    _response_type = CommandResponse

    def execute(self) -> ExecutionResponse:
        if self.args.function is not None:
            self.args.function()
        return ExecutionResponse.success()


def test_max_iterations_process_once():
    # Test max iterations with queue.process_once()
    queue = CommandQueue()
    responses: list[CommandResponse] = []
    for _ in range(111):
        responses.append(queue.submit(RunFunctionCommand(RunFunctionCommand.ARGS())))

    queue_response = queue.process_once(max_iterations=100)
    assert queue_response.num_commands_processed == 100
    assert queue_response.reached_max_iterations is True

    assert len([r for r in responses if r.status == ResponseStatus.COMPLETED]) == 100
    assert responses[100].status == ResponseStatus.CREATED


def test_max_iterations_process_all():
    # Test max iterations with queue.process_all()
    queue = CommandQueue()
    responses: list[CommandResponse] = []

    def add_to_queue():
        # Add a dummy command to the queue
        queue.submit(RunFunctionCommand(RunFunctionCommand.ARGS()))

    for _ in range(75):
        # These commands will add one more command to the queue each (total of 150 commands will need processing)
        responses.append(
            queue.submit(RunFunctionCommand(RunFunctionCommand.ARGS(function=add_to_queue)))
        )

    queue_response = queue.process_all(max_total_iterations=100)
    assert queue_response.num_commands_processed == 100
    assert len(queue) == 50  # 50 remaining commands in the queue
