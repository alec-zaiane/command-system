> Parts of this readme do not render correctly on pypi, see the [repository](https://github.com/alec-zaiane/command-system) for a better experience

# Command System
A type-safe implementation of the command pattern in Python, designed to handle command execution with a lifecycle that includes deferral and cancellation.

With this package, you can create commands that can be queued and manage their own lifecycle, allowing for interacting with external systems, or building your own systems with complex interactions in a safe, clean, and maintainable way.


## Example Usage
Simply subclass `Command`, `CommandArgs`, and optionally `CommandResponse` to create a custom command for your use case.

```python
# SayHelloCommand.py
from command_system import (
    Command,
    CommandArgs,
    CommandResponse,
    ExecutionResponse,
)
from dataclasses import dataclass

@dataclass
class SayHelloArgs(CommandArgs):
    name: str

@dataclass
class SayHelloResponse(CommandResponse):
    message: str = ""

class SayHelloCommand(Command[SayHelloArgs, SayHelloResponse]):
    ARGS = SayHelloArgs
    _response_type = SayHelloResponse

    def execute(self) -> ExecutionResponse:
        if not self.args.name:
            return ExecutionResponse.failure("Name cannot be empty.")
        self.response.message = f"Hello, {self.args.name}!"
        return ExecutionResponse.success()
```

You can then use the `CommandQueue` to submit commands, and then `queue.process_once()` or `queue.process_all()` to execute them.

```python
# main.py
from command_system import CommandQueue
from SayHelloCommand import SayHelloCommand, SayHelloArgs

queue = CommandQueue()
response = queue.submit(SayHelloCommand(SayHelloArgs(name="Alice")))
print(response.status) # Pending
queue.process_once()
print(response.status) # Completed
print(response.message) # Hello, Alice!
```

## Command Lifecycle
```mermaid
flowchart TD
    A[create command] -->|"queue.submit(command)"| B[responseStatus.CREATED]
    B --> C{"command.should_defer()"}
    C -->|"DeferResponse.defer()"| W["responseStatus.PENDING"]
    W --> C
    C -->|"DeferResponse.proceed()"| D{"command.should_cancel()"}
    D -->|"CancelResponse.cancel()"| E[ResponseStatus.CANCELED]
    D -->|"CancelResponse.proceed()"| F["command.execute()"]
    F -->|"ExecutionResponse.success()"| G["ResponseStatus.COMPLETED"]
    F -->|"ExecutionResponse.failure()"| H["ResponseStatus.FAILED"]
```


## Creating a command
Subclass `CommandArgs` and add any arguments your command needs. This class will be used to pass parameters to your command.

> [!CAUTION]
> Don't add your arguments directly to the `Command` class. The args class is required for command chaining to work in a type-safe manner.

Subclass `Command` and set the `ARGS` class attribute to the subclass of `CommandArgs` you created. Implement the `execute` method to define the command's behavior.
- You can also override `should_defer` and `should_cancel` methods to control the command's lifecycle.

Optionally, you can create a custom response class by subclassing `CommandResponse` so that your command can return specific type-safe data. If you do this, set the `_response_type` class attribute of your `Command` subclass to your custom response class.

### Writing your `execute` method
> [!WARNING]  
> Your `execute` method should not return your custom response class directly. 
> The `self.response` attribute is automatically set to an instance of your custom response class, which you should *modify* instead. Then, return an `ExecutionResponse` instance to indicate the command's success or failure. 

### Writing `should_defer` and `should_cancel` methods
These methods can be overridden to control the command's lifecycle. They must return a `DeferResponse` or `CancelResponse` instance, respectively. You can use them to set conditions for deferring or canceling the command.

### Complex Command example
for an example of deferring and canceling commands, see the [tests/test_defer_cancel.py](tests/test_defer_cancel.py) file.