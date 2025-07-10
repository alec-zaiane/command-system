from dataclasses import dataclass
from typing import Optional

from command_pattern import (
    CancelResponse,
    Command,
    CommandArgs,
    CommandQueue,
    DeferResponse,
    ExecutionResponse,
    CommandResponse,
    ResponseStatus,
)


@dataclass
class ExternalSystem:
    name: Optional[str] = None
    cancel: Optional[bool] = False


@dataclass
class WaitToHelloArgs(CommandArgs):
    external_system: ExternalSystem


@dataclass
class WaitToHelloResponse(CommandResponse):
    message: str = ""


class WaitToHelloCommand(Command[WaitToHelloArgs, WaitToHelloResponse]):
    ARGS = WaitToHelloArgs
    _response_type = WaitToHelloResponse

    def should_defer(self) -> DeferResponse:
        if self.args.external_system.name is None and not self.args.external_system.cancel:
            return DeferResponse.defer("Name is required to say hello.")
        return DeferResponse.proceed()

    def should_cancel(self) -> CancelResponse:
        if self.args.external_system.cancel:
            return CancelResponse.cancel("External system requested cancellation.")
        return CancelResponse.proceed()

    def execute(self) -> ExecutionResponse:
        self.response.message = f"Hello, {self.args.external_system.name}!"
        return ExecutionResponse.success()


def test_wait_to_hello_defer():
    queue = CommandQueue()
    external_system = ExternalSystem(name=None)
    response = queue.submit(WaitToHelloCommand(WaitToHelloCommand.ARGS(external_system)))
    # Since name is None, the command should defer and the reason should be set inside the queue response
    queue_response = queue.process_once()
    assert response.status == ResponseStatus.PENDING
    assert queue_response.command_log[-1].responses[-1].reason == "Name is required to say hello."
    # Name is still none; command should still be deferring
    queue.process_once()
    assert response.status == ResponseStatus.PENDING
    # Set the name, and try again. Command should now execute successfully
    external_system.name = "Alice"
    queue.process_once()
    assert response.status == ResponseStatus.COMPLETED
    assert response.message == "Hello, Alice!"


def test_wait_to_hello_cancel():
    queue = CommandQueue()
    external_system = ExternalSystem(name=None)
    response = queue.submit(WaitToHelloCommand(WaitToHelloCommand.ARGS(external_system)))
    # Request a cancellation as the external system
    external_system.cancel = True
    queue_response = queue.process_all()
    # Make sure it was cancelled, and the reason is set
    assert response.status == ResponseStatus.CANCELED
    assert (
        queue_response.command_log[-1].responses[-1].reason
        == "External system requested cancellation."
    )
