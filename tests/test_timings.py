from dataclasses import dataclass
from typing import Optional
import time

from command_system import (
    Command,
    CommandArgs,
    CommandQueue,
    CommandResponse,
    CancelResponse,
    DeferResponse,
    ExecutionResponse,
    ResponseStatus,
)


@dataclass
class SleepArgs(CommandArgs):
    defer_sleep_ms: Optional[int] = None
    cancel_sleep_ms: Optional[int] = None
    execute_sleep_ms: Optional[int] = None


class SleepCommand(Command[SleepArgs, CommandResponse]):
    ARGS = SleepArgs
    _response_type = CommandResponse

    def should_defer(self) -> DeferResponse:
        if self.args.defer_sleep_ms is not None:
            time.sleep(self.args.defer_sleep_ms / 1000)
        return DeferResponse.proceed()

    def should_cancel(self) -> CancelResponse:
        if self.args.cancel_sleep_ms is not None:
            time.sleep(self.args.cancel_sleep_ms / 1000)
        return CancelResponse.proceed()

    def execute(self) -> ExecutionResponse:
        if self.args.execute_sleep_ms is not None:
            time.sleep(self.args.execute_sleep_ms / 1000)
        return ExecutionResponse.success()


def test_sleep_command_timing():
    queue = CommandQueue(timing_queue_length=10)
    DEFER_TIME_MS = 100
    CANCEL_TIME_MS = 50
    EXECUTE_TIME_MS = 200
    response = queue.submit(
        SleepCommand(
            SleepCommand.ARGS(
                defer_sleep_ms=DEFER_TIME_MS,
                cancel_sleep_ms=CANCEL_TIME_MS,
                execute_sleep_ms=EXECUTE_TIME_MS,
            )
        )
    )
    assert response.status == ResponseStatus.CREATED
    queue_response = queue.process_once()
    assert queue_response.num_commands_processed == 1
    assert response.status == ResponseStatus.COMPLETED
    timing_data = queue.get_timing_data()
    assert timing_data.keys() == {SleepCommand}
    sleep_data = timing_data[SleepCommand]
    assert abs(sleep_data.should_defer_timing.avg_elapsed_ms - DEFER_TIME_MS) < 10
    assert abs(sleep_data.should_cancel_timing.avg_elapsed_ms - CANCEL_TIME_MS) < 10
    assert abs(sleep_data.execute_timing.avg_elapsed_ms - EXECUTE_TIME_MS) < 10


def test_sleep_command_timing_no_timing():
    queue = CommandQueue(timing_queue_length=0)
    DEFER_TIME_MS = 100
    CANCEL_TIME_MS = 50
    EXECUTE_TIME_MS = 200
    response = queue.submit(
        SleepCommand(
            SleepCommand.ARGS(
                defer_sleep_ms=DEFER_TIME_MS,
                cancel_sleep_ms=CANCEL_TIME_MS,
                execute_sleep_ms=EXECUTE_TIME_MS,
            )
        )
    )
    assert response.status == ResponseStatus.CREATED
    queue_response = queue.process_once()
    assert queue_response.num_commands_processed == 1
    assert response.status == ResponseStatus.COMPLETED
    timing_data = queue.get_timing_data()
    assert timing_data == {}


def test_sleep_command_timing_many():
    queue = CommandQueue(timing_queue_length=10)
    DEFER_TIME_MS = 20
    CANCEL_TIME_MS = 30
    EXECUTE_TIME_MS = 40
    for _ in range(15):
        queue.submit(
            SleepCommand(
                SleepCommand.ARGS(
                    defer_sleep_ms=DEFER_TIME_MS,
                    cancel_sleep_ms=CANCEL_TIME_MS,
                    execute_sleep_ms=EXECUTE_TIME_MS,
                )
            )
        )
    queue_response = queue.process_all()
    assert queue_response.num_commands_processed == 15
    timing_data = queue.get_timing_data()
    assert timing_data.keys() == {SleepCommand}
    sleep_data = timing_data[SleepCommand]
    assert sleep_data.should_defer_timing.count == 10  # because of queue length
    assert sleep_data.should_cancel_timing.count == 10
    assert sleep_data.execute_timing.count == 10
    assert abs(sleep_data.should_defer_timing.avg_elapsed_ms - DEFER_TIME_MS) < 10
    assert abs(sleep_data.should_cancel_timing.avg_elapsed_ms - CANCEL_TIME_MS) < 10
    assert abs(sleep_data.execute_timing.avg_elapsed_ms - EXECUTE_TIME_MS) < 10
    assert 0 < sleep_data.should_defer_timing.std_dev_elapsed_ms < 10
    assert 0 < sleep_data.should_cancel_timing.std_dev_elapsed_ms < 10
    assert 0 < sleep_data.execute_timing.std_dev_elapsed_ms < 10
