from command_system import (
    CancelResponse,
    CommandQueue,
    DeferResponse,
    ExecutionResponse,
    ResponseStatus,
    ReasonByCommandMethod,
)

from test_defer_cancel import WaitToHelloCommand, ExternalSystem


def test_defer_callback():
    external_system = ExternalSystem(name=None, cancel=False)
    defer_callback_called = False

    def sample_defer_callback(response: DeferResponse):
        nonlocal defer_callback_called
        defer_callback_called = True
        assert response.reason == "Name is required to say hello."

    queue = CommandQueue()
    command = WaitToHelloCommand(WaitToHelloCommand.ARGS(external_system))
    command.add_on_defer_callback(sample_defer_callback)
    response = queue.submit(command)
    queue.process_all()
    assert defer_callback_called is True
    assert response.status == ResponseStatus.PENDING


def test_cancel_callback():
    external_system = ExternalSystem(name="Alice", cancel=True)
    cancel_callback_called = False

    def sample_cancel_callback(response: CancelResponse):
        nonlocal cancel_callback_called
        cancel_callback_called = True
        assert response.reason == ReasonByCommandMethod("External system requested cancellation.")

    queue = CommandQueue()
    command = WaitToHelloCommand(WaitToHelloCommand.ARGS(external_system))
    command.add_on_cancel_callback(sample_cancel_callback)
    response = queue.submit(command)
    queue_response = queue.process_all()
    assert cancel_callback_called is True
    assert response.status == ResponseStatus.CANCELED
    assert queue_response.command_log[-1].responses[-1].reason == ReasonByCommandMethod(
        "External system requested cancellation."
    )


def test_execute_callback():
    external_system = ExternalSystem(name="Alice", cancel=False)
    execute_callback_called = False

    def sample_execute_callback(response: ExecutionResponse):
        nonlocal execute_callback_called
        execute_callback_called = True
        assert response.should_proceed is True

    queue = CommandQueue()
    command = WaitToHelloCommand(WaitToHelloCommand.ARGS(external_system))
    command.add_on_execute_callback(sample_execute_callback)
    response = queue.submit(command)
    queue.process_all()
    assert execute_callback_called is True
    assert response.status == ResponseStatus.COMPLETED
    assert response.message == "Hello, Alice!"
