from .Command import Command, CommandArgs, CommandResponse, ArgsType, ResponseType
from .CommandQueue import CommandQueue
from .CommandLifecycle import ExecutionResponse
from dataclasses import dataclass, field
from typing import Callable, TypeVar, Generic, Any, cast, Optional

inputDataType = TypeVar("inputDataType")
outputDataType = TypeVar("outputDataType")

subsequentArgsType = TypeVar("subsequentArgsType", bound=CommandArgs)
subsequentResponseType = TypeVar("subsequentResponseType", bound=CommandResponse)
subsequentOutputDataType = TypeVar("subsequentOutputDataType")

firstArgsType = TypeVar("firstArgsType", bound=CommandArgs)
firstResponseType = TypeVar("firstResponseType", bound=CommandResponse)
firstOutputDataType = TypeVar("firstOutputDataType")


@dataclass
class CommandChainLink(Generic[inputDataType, ArgsType, ResponseType, outputDataType]):
    args_factory: Callable[[inputDataType], ArgsType]
    command: type[Command[ArgsType, ResponseType]]
    result_extractor: Callable[[ResponseType], outputDataType]


class CommandChainBuilder(
    Generic[inputDataType, outputDataType],
):

    def __init__(
        self, input_data: inputDataType, _links: list[CommandChainLink[Any, Any, Any, Any]]
    ):
        """
        **Private constructor**. Use `CommandChainBuilder.start()` to create a new command chain.

        Args:
            input_data (inputDataType): The initial input data for the command chain.
            _links (list[CommandChainLink[Any, Any, Any, Any]]): The list of command links in the chain.
        """
        self.input_data = input_data
        self._links: list[CommandChainLink[Any, Any, Any, Any]] = _links

    @classmethod
    def start(
        cls,
        input_data: inputDataType,
        args_factory: Callable[[inputDataType], ArgsType],
        command: type[Command[ArgsType, ResponseType]],
        result_extractor: Callable[[ResponseType], outputDataType],
    ) -> "CommandChainBuilder[inputDataType, outputDataType]":
        """Start a new CommandChain with the given input data and the first command."""
        initial_link = CommandChainLink(
            args_factory=args_factory,
            command=command,
            result_extractor=result_extractor,
        )

        return cls(input_data=input_data, _links=[initial_link])

    def then(
        self,
        args_factory: Callable[[outputDataType], subsequentArgsType],
        command: type[Command[subsequentArgsType, subsequentResponseType]],
        result_extractor: Callable[[subsequentResponseType], subsequentOutputDataType],
    ) -> "CommandChainBuilder[inputDataType, subsequentOutputDataType]":
        """
        Returns a new CommandChain with an additional link.
        This method allows chaining commands together, where the output of one command can be used as the input for the next.

        Args:
            args_factory (Callable[[outputDataType], subsequentArgsType]): A function that takes the output data of the previous command and returns the arguments for the next command.
            command (type[Command[subsequentArgsType, subsequentResponseType]]): The class of the command to be executed next in the chain.
            result_extractor (Callable[[subsequentResponseType], subsequentOutputDataType]): A function that extracts the output data from the response of the command.

        Returns:
            CommandChainBuilder[inputDataType, subsequentOutputDataType]: A new CommandChainBuilder with the added link.
        """
        if len(self._links) == 0:
            raise ValueError(
                "Cannot add a subsequent command to an empty chain. Use `CommandChainBuilder.start()` to create a new chain."
            )
        new_link = CommandChainLink(
            args_factory=args_factory, command=command, result_extractor=result_extractor
        )
        new_chain: CommandChainBuilder[inputDataType, subsequentOutputDataType] = (
            CommandChainBuilder(input_data=self.input_data, _links=self._links + [new_link])
        )
        return new_chain

    @property
    def links(self) -> list[CommandChainLink[Any, Any, Any, Any]]:
        """
        Returns the list of links in the command chain.

        **Do not modify the returned list.**

        Returns:
            list[CommandChainLink[Any, Any, Any, Any]]: The links in the command chain.
        """
        return self._links

    def build(self, queue: CommandQueue) -> "CommandChain[inputDataType, outputDataType]":
        """
        Realizes the command chain builder, creating a CommandChain instance with the current input data and links.

        This does not execute the chain, it only prepares it for execution.

        Returns:
            CommandChain[inputDataType, outputDataType]: A CommandChain instance with the current input data and links.
        """
        return CommandChain(
            args=CommandChainArgs(
                queue=queue,
                input_data=self.input_data,
                chain=self,
            )
        )


@dataclass
class CommandChainArgs(CommandArgs, Generic[inputDataType, outputDataType]):
    queue: CommandQueue
    input_data: inputDataType
    chain: CommandChainBuilder[inputDataType, outputDataType]


@dataclass
class CommandChainResponse(CommandResponse, Generic[outputDataType]):
    """
    The response type for a command chain.

    Attributes:
        output_data (Optional[outputDataType]): The final output data of the command chain, if available.
        responses (list[CommandResponse]): A list of responses from each command in the chain.
        intermediate_results (list[Any]): A list of intermediate results collected during the execution of the chain, including the final output data.
    """

    output_data: Optional[outputDataType] = None
    responses: list[CommandResponse] = cast(list[CommandResponse], field(default_factory=list))
    intermediate_results: list[Any] = cast(list[Any], field(default_factory=list))


class CommandChain(
    Command[CommandChainArgs[inputDataType, outputDataType], CommandChainResponse[outputDataType]],
    Generic[inputDataType, outputDataType],
):
    """
    A command that executes a chain of commands, where each command's output can be used as the input for the next command in the chain.

    Heavily recommended to create it using the `CommandChainBuilder` class, calling the `.then()` method, and finally calling `.build()` to create the `CommandChain` instance.
    """

    ARGS: type[CommandChainArgs[inputDataType, outputDataType]] = CommandChainArgs
    _response_type: type[CommandChainResponse[outputDataType]] = CommandChainResponse

    def _on_command_execute(
        self,
        link: CommandChainLink[Any, Any, Any, Any],
        response: ExecutionResponse,
        command: Command[Any, Any],
        next_index: int,
    ) -> None:
        """Callback for when a command in the chain is executed.
        Handles the response from the command, extracting the output data and adding the next command to the queue.
        """
        if not response.should_proceed:
            self.response.set_failed()
            return
        intermediate_result = link.result_extractor(command.response)
        self.response.intermediate_results.append(intermediate_result)
        # submit the next command
        self._submit_chained_command(next_index, intermediate_result)

    def _submit_chained_command(self, position: int, previous_data: Any) -> None:
        """Process the next command in the chain using the extracted data from the previous command.

        Adds intermediate results to the response, builds callbacks for the next command, and submits it to the queue.
        """
        if position >= len(self.args.chain.links):
            self.response.set_completed()
            # set the final output data to the last intermediate result or None if there are no results somehow
            self.response.output_data = (
                self.response.intermediate_results[-1]
                if self.response.intermediate_results
                else None
            )
            return

        link = self.args.chain.links[position]
        args = link.args_factory(previous_data)
        command = link.command(args)
        command.add_on_cancel_callback(lambda _: self.response.set_failed())
        command.add_on_execute_callback(
            lambda response: self._on_command_execute(
                link=link, response=response, command=command, next_index=position + 1
            )
        )
        self.response.responses.append(self.args.queue.submit(command))

    def execute(self) -> ExecutionResponse:
        """Execute all commands in the chain using callbacks to create the arguments for each subsequent command."""
        if not self.args.chain:
            return ExecutionResponse.success()  # pragma: no cover
        self._submit_chained_command(0, self.args.input_data)
        return ExecutionResponse.success()
