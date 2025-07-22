from dataclasses import dataclass
from logging import getLogger
from typing import Any, Optional, Type
from collections import deque, defaultdict
import statistics
from time import perf_counter
from .Command import Command, CommandArgs, ResponseType
from .CommandLifecycle import (
    CancelResponse,
    DeferResponse,
    ExecutionResponse,
    LifecycleResponse,
)
from .CommandResponse import CommandResponse, ResponseStatus
from .Dependencies import (
    DependencyAction,
    DependencyCheckResponse,
    ReasonByDependencyCheck,
)


@dataclass
class CommandLogEntry:
    """
    Represents a single command log entry.

    Contains the command and the responses from its lifecycle actions.

    Attributes:
        command (Command[Any, Any]): The command that was processed.
        responses (list[LifecycleResponse]): List of responses from the lifecycle actions of the command.
        dependency_response (DependencyCheckResponse): The response from the dependency check of the command.
    """

    command: Command[Any, Any]
    responses: list[LifecycleResponse]
    dependency_response: Optional[DependencyCheckResponse]


@dataclass
class QueueProcessResponse:
    """
    Response type of `CommandQueue.process_once()` and `CommandQueue.process_all()`.

    Contains information about the processing of commands in the queue.

    Attributes:
        command_log (list[CommandLogEntry]): List of all commands processed, along with all responses from their lifecycle actions.
        num_commands_processed (int): Total number of commands processed in this run.
        num_ingested (int): Number of commands that turned from `CREATED` to `PENDING` status.
        num_deferrals (int): Number of times a command was deferred.
        num_cancellations (int): Number of times a command was canceled.
        num_successes (int): Number of times a command executed and succeeded.
        num_failures (int): Number of times a command executed and failed.
        reached_max_iterations (bool): True if the maximum number of iterations was reached, false otherwise.
    """

    command_log: list[CommandLogEntry]
    num_commands_processed: int = 0
    num_ingested: int = 0
    num_deferrals: int = 0
    num_cancellations: int = 0
    num_successes: int = 0
    num_failures: int = 0
    reached_max_iterations: bool = False

    def __add__(self, other: "QueueProcessResponse") -> "QueueProcessResponse":
        """
        Add two QueueProcessResponse objects together.

        Args:
            other (QueueProcessResponse): The other QueueProcessResponse to add.

        Returns:
            QueueProcessResponse: A new QueueProcessResponse object with combined values.
        """
        return QueueProcessResponse(
            num_commands_processed=self.num_commands_processed + other.num_commands_processed,
            num_ingested=self.num_ingested + other.num_ingested,
            num_deferrals=self.num_deferrals + other.num_deferrals,
            num_cancellations=self.num_cancellations + other.num_cancellations,
            num_successes=self.num_successes + other.num_successes,
            num_failures=self.num_failures + other.num_failures,
            reached_max_iterations=self.reached_max_iterations or other.reached_max_iterations,
            command_log=self.command_log + other.command_log,
        )


@dataclass
class _InternalQueueTimingEntry:
    """
    Internal timing entry for commands.
    fields should be self-explanatory.
    """

    command_type: Type[Command[Any, Any]]
    method_elapsed_ms: float
    response_should_proceed: bool  # the method's return.should_proceed value
    # callbacks are initialized to 0 for ease of building this object
    callbacks_count: int = 0
    callbacks_elapsed_ms: float = 0


@dataclass
class CommandTimingData:
    """Timing data for a set of commands"""

    @dataclass
    class CommandTimingEntry:
        count: int
        avg_elapsed_ms: float = 0
        std_dev_elapsed_ms: float = 0

    should_defer_timing: CommandTimingEntry
    should_defer_percentage: float
    """Percentage of the time should_defer() deferred, or NaN"""
    should_defer_callbacks: CommandTimingEntry
    should_cancel_timing: CommandTimingEntry
    should_cancel_percentage: float
    """Percentage of the time should_cancel() canceled, or NaN"""
    should_cancel_callbacks: CommandTimingEntry
    execute_timing: CommandTimingEntry
    execute_failure_percentage: float
    """Percentage of the time execute() returned a failure, or NaN"""
    execute_callbacks: CommandTimingEntry


class CommandQueue:
    def __init__(self, timing_queue_length: int = 0):
        """
        Construct a new CommandQueue.

        Args:
            timing_queue_length (int, optional): Length of the timing queue for performance measurement, set to 0 to disable timing. Defaults to 0.
        """
        self._timing_queue_length = timing_queue_length
        self._queue: list[Command[Any, Any]] = []
        self.logger = getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}@{id(self)}")

        self._timing_should_defer: deque[_InternalQueueTimingEntry] = deque(
            maxlen=timing_queue_length,
        )
        self._timing_should_cancel: deque[_InternalQueueTimingEntry] = deque(
            maxlen=timing_queue_length,
        )
        self._timing_execute: deque[_InternalQueueTimingEntry] = deque(
            maxlen=timing_queue_length,
        )

    def submit(self, command: Command[Any, ResponseType]) -> ResponseType:
        """
        Submit a command to the queue.

        Args:
            command (Command[ArgsType, ResponseType]): The command to be submitted.

        Returns:
            ResponseType: The response object associated with the command.
        """
        self._queue.append(command)
        return command.response

    def submit_many(self, *commands: Command[Any, Any]) -> list[CommandResponse]:
        """
        Submit multiple commands to the queue.

        Args:
            *commands (Command[ArgsType, ResponseType]): The commands to be submitted.

        Returns:
            list[ResponseType]: List of response objects associated with the submitted commands.
        """
        responses: list[CommandResponse] = []
        for command in commands:
            responses.append(self.submit(command))
        return responses

    def _process_single_command(
        self,
        command: Command[CommandArgs, CommandResponse],
        queue_process_response: QueueProcessResponse,
    ) -> tuple[CommandLogEntry, bool]:
        """Process a single command and return its log entry
        Returns:
            CommandLogEntry: The log entry for the command, containing the command and its responses.
            bool: True if the command should be removed from the queue, False otherwise.
        """
        output = CommandLogEntry(
            command=command,
            responses=[],
            dependency_response=None,
        )
        # bring it into PENDING if it hasn't started being processed yet
        if command.response.status == ResponseStatus.CREATED:
            queue_process_response.num_ingested += 1
            command.response.status = ResponseStatus.PENDING
        # now process the command based on its current status
        match command.response.status:
            case ResponseStatus.PENDING:
                queue_process_response.num_commands_processed += 1
                # 1. check dependencies
                dependency_response = command.check_dependencies()
                output.dependency_response = dependency_response
                if dependency_response.status == DependencyAction.DEFER:
                    queue_process_response.num_deferrals += 1
                    new_defer_response = DeferResponse(
                        should_proceed=False,
                        reason=ReasonByDependencyCheck(
                            f"Deferred due to dependency: {dependency_response.reasons}"
                        ),
                    )
                    start = perf_counter()
                    command.call_on_defer_callbacks(new_defer_response)
                    elapsed = perf_counter() - start
                    self._timing_should_defer.append(
                        _InternalQueueTimingEntry(
                            command_type=command.__class__,
                            method_elapsed_ms=0,  # `should_defer()` didn't run
                            response_should_proceed=False,
                            callbacks_count=command.on_defer_callbacks_count(),
                            callbacks_elapsed_ms=elapsed * 1000,  # convert to ms
                        )
                    )
                    output.responses.append(new_defer_response)
                    return output, False
                elif dependency_response.status == DependencyAction.CANCEL:
                    queue_process_response.num_cancellations += 1
                    new_cancel_response = CancelResponse(
                        should_proceed=False,
                        reason=ReasonByDependencyCheck(
                            f"Canceled due to dependency: {dependency_response.reasons}"
                        ),
                    )
                    start = perf_counter()
                    command.call_on_cancel_callbacks(new_cancel_response)
                    elapsed = perf_counter() - start
                    self._timing_should_cancel.append(
                        _InternalQueueTimingEntry(
                            command_type=command.__class__,
                            method_elapsed_ms=0,  # `should_cancel()` didn't run
                            response_should_proceed=False,
                            callbacks_count=command.on_cancel_callbacks_count(),
                            callbacks_elapsed_ms=elapsed * 1000,  # convert to ms
                        )
                    )
                    output.responses.append(new_cancel_response)
                    command.response.status = ResponseStatus.CANCELED
                    return output, True
                # 2. check if we should defer
                start = perf_counter()
                defer_response = command.should_defer()
                elapsed = perf_counter() - start
                defer_timing_entry = _InternalQueueTimingEntry(
                    command_type=command.__class__,
                    method_elapsed_ms=elapsed * 1000,
                    response_should_proceed=defer_response.should_proceed,
                )
                if not defer_response.should_proceed:
                    queue_process_response.num_deferrals += 1
                    start = perf_counter()
                    command.call_on_defer_callbacks(defer_response)
                    elapsed = perf_counter() - start
                    defer_timing_entry.callbacks_count = command.on_defer_callbacks_count()
                    defer_timing_entry.callbacks_elapsed_ms = elapsed * 1000
                    self._timing_should_defer.append(defer_timing_entry)
                    output.responses.append(defer_response)
                    return output, False
                self._timing_should_defer.append(defer_timing_entry)
                # 3. check if we should cancel
                start = perf_counter()
                cancel_response = command.should_cancel()
                elapsed = perf_counter() - start
                cancel_timing_entry = _InternalQueueTimingEntry(
                    command_type=command.__class__,
                    method_elapsed_ms=elapsed * 1000,
                    response_should_proceed=cancel_response.should_proceed,
                )
                if not cancel_response.should_proceed:
                    queue_process_response.num_cancellations += 1
                    start = perf_counter()
                    command.call_on_cancel_callbacks(cancel_response)
                    elapsed = perf_counter() - start
                    cancel_timing_entry.callbacks_count = command.on_cancel_callbacks_count()
                    cancel_timing_entry.callbacks_elapsed_ms = elapsed * 1000
                    self._timing_should_cancel.append(cancel_timing_entry)
                    output.responses.append(cancel_response)
                    command.response.status = ResponseStatus.CANCELED
                    return output, True
                self._timing_should_cancel.append(cancel_timing_entry)
                # 4. execute the command
                start = perf_counter()
                try:
                    execution_response = command.execute()
                except Exception as e:
                    execution_response = ExecutionResponse.failure(str(e))
                elapsed = perf_counter() - start
                start = perf_counter()
                command.call_on_execute_callbacks(execution_response)
                elapsed_callbacks = perf_counter() - start
                self._timing_execute.append(
                    _InternalQueueTimingEntry(
                        command_type=command.__class__,
                        method_elapsed_ms=elapsed * 1000,
                        response_should_proceed=execution_response.should_proceed,
                        callbacks_count=command.on_execute_callbacks_count(),
                        callbacks_elapsed_ms=elapsed_callbacks * 1000,
                    )
                )
                output.responses.append(execution_response)
                if execution_response.should_proceed:
                    command.response.status = ResponseStatus.COMPLETED
                    queue_process_response.num_successes += 1
                else:
                    command.response.status = ResponseStatus.FAILED
                    queue_process_response.num_failures += 1
                return output, True

            case ResponseStatus.CANCELED | ResponseStatus.COMPLETED | ResponseStatus.FAILED:
                queue_process_response.num_commands_processed += 1
                return output, True
        # mypy wants a return statement here, but it should never be reached
        raise RuntimeError(
            f"Command {command} has an invalid response status: {command.response.status}"
        )

    def process_once(self, max_iterations: int = 1000) -> QueueProcessResponse:
        """
        Process all commands in the queue a single time.

        If a command is deferred, it will not be processed again until the next call to `process_once()`.

        Args:
            max_iterations (int, optional): Maximum number of commands to process in one call. Defaults to 1000.

        Returns:
            QueueProcessResponse: Response containing details of the processing.
        """
        response = QueueProcessResponse(command_log=[])
        to_remove: list[Command[Any, Any]] = []
        for command in self._queue:
            if response.num_commands_processed >= max_iterations:
                response.reached_max_iterations = True
                break
            command_log_entry, should_remove = self._process_single_command(command, response)
            response.command_log.append(command_log_entry)
            if should_remove:
                to_remove.append(command)
        # remove all processed commands
        for command in to_remove:
            if command in self._queue:
                self._queue.remove(command)
        return response

    def process_all(self, max_total_iterations: int = 1000) -> QueueProcessResponse:
        """
        Process all commands in the queue until either all commands are processed, or the maximum number of iterations is reached.

        Args:
            max_total_iterations (int, optional): Maximum number of times `process_once()` can be run. Defaults to 1000.

        Returns:
            QueueProcessResponse: Response containing details of the processing.
        """
        response = QueueProcessResponse(command_log=[])
        while len(self._queue) > 0:
            if response.num_commands_processed >= max_total_iterations:
                response.reached_max_iterations = True
                break
            response += self.process_once(max_iterations=max_total_iterations)
        return response

    # Magic methods

    def __len__(self) -> int:
        """
        Get the number of commands in the queue.

        Returns:
            int: The number of commands in the queue.
        """
        return len(self._queue)

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}(queue_size={len(self._queue)})"

    def get_timing_data(self) -> dict[Type[Command[Any, Any]], CommandTimingData]:
        """
        Get timing data for the command queue.

        Relatively expensive operation, so cache this if you need to access it frequently.

        Returns:
            dict[Type[Command[Any, Any]], CommandTimingData]: A dictionary mapping command types to their timing data, returns an empty dictionary if timing is disabled.
        """
        output: dict[Type[Command[Any, Any]], CommandTimingData] = {}

        def calculate_subtimings(
            input_timings: deque[_InternalQueueTimingEntry],
        ) -> tuple[
            defaultdict[
                Type[Command[Any, Any]],
                tuple[CommandTimingData.CommandTimingEntry, CommandTimingData.CommandTimingEntry],
            ],
            defaultdict[Type[Command[Any, Any]], float],
        ]:
            """invert a deque of _InternalQueueTimingEntry objects into two dictionaries:
            one maps command types -> (command timing data, callbacks timing data)
            the other maps command types -> failure percentage (opposite of `should_proceed` percentage)
            """
            intermediate_timings = defaultdict[
                Type[Command[Any, Any]], list[_InternalQueueTimingEntry]
            ](list)
            for entry in input_timings:
                intermediate_timings[entry.command_type].append(entry)
            # now calculate the average and standard deviation for each command type
            output = defaultdict[
                Type[Command[Any, Any]],
                tuple[CommandTimingData.CommandTimingEntry, CommandTimingData.CommandTimingEntry],
            ](
                lambda: (
                    CommandTimingData.CommandTimingEntry(count=0),
                    CommandTimingData.CommandTimingEntry(count=0),
                )
            )
            output_failure_percentage = defaultdict[Type[Command[Any, Any]], float](float)
            for command_type, timings in intermediate_timings.items():
                if len(timings) == 0:
                    continue
                output[command_type] = (
                    CommandTimingData.CommandTimingEntry(
                        count=len(timings),
                        avg_elapsed_ms=statistics.mean(
                            entry.method_elapsed_ms for entry in timings
                        ),
                        std_dev_elapsed_ms=(
                            statistics.stdev(entry.method_elapsed_ms for entry in timings)
                            if len(timings) > 1
                            else 0.0
                        ),
                    ),
                    CommandTimingData.CommandTimingEntry(
                        count=sum(entry.callbacks_count for entry in timings),
                        avg_elapsed_ms=statistics.mean(
                            entry.callbacks_elapsed_ms for entry in timings
                        ),
                        std_dev_elapsed_ms=(
                            statistics.stdev(entry.callbacks_elapsed_ms for entry in timings)
                            if len(timings) > 1
                            else 0.0
                        ),
                    ),
                )
                output_failure_percentage[command_type] = 1 - sum(
                    entry.response_should_proceed for entry in timings
                ) / len(timings)
            return output, output_failure_percentage

        should_defer_subtimings, defer_percents = calculate_subtimings(self._timing_should_defer)
        should_cancel_subtimings, cancel_percents = calculate_subtimings(self._timing_should_cancel)
        execute_subtimings, failure_percents = calculate_subtimings(self._timing_execute)

        # now build the output
        encountered_command_types: set[Type[Command[Any, Any]]] = set(
            should_defer_subtimings.keys()
            | should_cancel_subtimings.keys()
            | execute_subtimings.keys()
        )
        COMMAND_TIMINGS = 0
        CALLBACKS_TIMINGS = 1
        for command_type in encountered_command_types:
            output[command_type] = CommandTimingData(
                should_defer_timing=should_defer_subtimings[command_type][COMMAND_TIMINGS],
                should_defer_percentage=defer_percents[command_type],
                should_defer_callbacks=should_defer_subtimings[command_type][CALLBACKS_TIMINGS],
                should_cancel_timing=should_cancel_subtimings[command_type][COMMAND_TIMINGS],
                should_cancel_percentage=cancel_percents[command_type],
                should_cancel_callbacks=should_cancel_subtimings[command_type][CALLBACKS_TIMINGS],
                execute_timing=execute_subtimings[command_type][COMMAND_TIMINGS],
                execute_failure_percentage=failure_percents[command_type],
                execute_callbacks=execute_subtimings[command_type][CALLBACKS_TIMINGS],
            )
        return output
