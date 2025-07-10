from dataclasses import dataclass
from typing import Optional

from command_pattern import (
    Command,
    CommandArgs,
    CommandQueue,
    ExecutionResponse,
    CommandResponse,
    ResponseStatus,
)


@dataclass
class SayHelloArgs(CommandArgs):
    name: Optional[str]


@dataclass
class SayHelloResponse(CommandResponse):
    message: str = ""


class SayHelloCommand(Command[SayHelloArgs, SayHelloResponse]):
    ARGS = SayHelloArgs
    _response_type = SayHelloResponse

    def execute(self) -> ExecutionResponse:
        if self.args.name is None:
            return ExecutionResponse.failure("Cannot say hello to no one.")
        self.response.message = f"Hello, {self.args.name}!"
        return ExecutionResponse.success()


def test_say_hello_success():
    queue = CommandQueue()
    response = queue.submit(SayHelloCommand(SayHelloCommand.ARGS(name="Alice")))
    assert isinstance(response, SayHelloResponse)
    assert response.status == ResponseStatus.CREATED
    queue_response = queue.process_once()
    assert response.status == ResponseStatus.COMPLETED
    assert queue_response.num_commands_processed == 1
    assert queue_response.num_ingested == 1
    assert queue_response.num_deferrals == 0
    assert queue_response.num_cancellations == 0
    assert queue_response.num_successes == 1
    assert queue_response.num_failures == 0
    assert queue_response.reached_max_iterations is False
    assert response.message == "Hello, Alice!"
    queue_response = queue.process_once()
    assert queue_response.num_commands_processed == 0
    assert len(queue) == 0


def test_say_hello_failure():
    queue = CommandQueue()
    response = queue.submit(SayHelloCommand(SayHelloCommand.ARGS(name=None)))
    assert isinstance(response, SayHelloResponse)
    assert response.status == ResponseStatus.CREATED
    queue_response = queue.process_once()
    assert response.status == ResponseStatus.FAILED
    assert queue_response.command_log[-1].responses[-1].reason == "Cannot say hello to no one."


def test_re_add_completed_command():
    queue = CommandQueue()
    command = SayHelloCommand(SayHelloCommand.ARGS(name="Bob"))
    response = queue.submit(command)
    queue.process_once()
    assert response.status == ResponseStatus.COMPLETED
    queue.submit(command)  # Re-add the same command
    queue_response = queue.process_once()
    assert queue_response.num_commands_processed == 1
    assert (
        queue_response.num_failures + queue_response.num_successes == 0
    )  # nothing actually executed
