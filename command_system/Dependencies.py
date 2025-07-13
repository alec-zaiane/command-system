from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Optional, cast

from .CommandLifecycle import LifecycleResponseReason
from .CommandResponse import ResponseStatus

if TYPE_CHECKING:
    from .Command import Command, CommandArgs, CommandResponse


class DependencyAction(Enum):
    """
    Enum representing the possible actions to take based on command dependencies.
    """

    PROCEED = "proceed"
    DEFER = "defer"
    CANCEL = "cancel"


@dataclass
class ReasonByDependencyCheck(LifecycleResponseReason):
    """
    A reason for a lifecycle response that was created by a dependency check.
    """

    pass


@dataclass
class DependencyCheckResponse:
    """
    Represents the result of checking command dependencies.

    Attributes:
        status (DependencyCheckResponseOption): The status of the dependency check.
            - PROCEED: Proceed with the command execution.
            - DEFER: Defer the command execution.
            - CANCEL: Cancel the command execution.
        reasons list[str]: A list of reasons for the current status.

    """

    status: DependencyAction
    reasons: list[str] = cast(list[str], field(default_factory=list))

    def attempt_escalation(self, status: DependencyAction, reason: Optional[str] = None) -> None:
        """
        Update the status of the dependency check response if the new status is more severe than the current one.

        Severity order is: CANCEL > DEFER > PROCEED.

        - If the new status is less severe, nothing happens.
        - If the new status is equally severe, the self.reasons list is updated with the new reason.
        - If the new status is more severe, the self.status is updated and the reason is reset to the new reason.

        Args:
            status (DependencyCheckResponseOption): The new status to set.
            reason (Optional[str]): An optional reason for the new status.
        """
        severity_order = {
            DependencyAction.PROCEED: 0,
            DependencyAction.DEFER: 1,
            DependencyAction.CANCEL: 2,
        }
        current_severity = severity_order[self.status]
        new_severity = severity_order[status]
        if new_severity < current_severity:
            return
        if new_severity == current_severity:
            if reason is not None:
                self.reasons.append(reason)
            return
        self.status = status
        self.reasons = []
        if reason is not None:
            self.reasons.append(reason)

    def __repr__(self) -> str:  # pragma: no cover
        return f"DependencyCheckResponse(status={self.status}, reasons={','.join(self.reasons)})"

    @classmethod
    def proceed(cls) -> "DependencyCheckResponse":
        """Create a DependencyCheckResponse indicating that the command can proceed."""
        return cls(status=DependencyAction.PROCEED)


# map all valid strings to DependencyAction - for use in DependencyEntry
_dependency_action_map = {
    "proceed": DependencyAction.PROCEED,
    "defer": DependencyAction.DEFER,
    "cancel": DependencyAction.CANCEL,
}


@dataclass
class DependencyEntry:
    """
    Represents a single dependency entry for a command.

    Attributes:
        command (Command): The command that this dependency entry depends on.
        on_pending (Literal["defer", "cancel", "proceed"]):
            Action that the depending command should take when the dependency is pending (or freshly created).
            - "defer": Defer the command execution.
            - "cancel": Cancel the command execution.
            - "proceed": Proceed with the command execution.
            - Default is "defer".
        on_canceled (Literal["cancel", "proceed"]):
            Action that the depending command should take when the dependency is canceled.
            - "cancel": Cancel the command execution.
            - "proceed": Proceed with the command execution.
            - Default is "cancel".
        on_failed (Literal["cancel", "proceed"]):
            Action that the depending command should take when the dependency fails.
            - "cancel": Cancel the command execution.
            - "proceed": Proceed with the command execution.
            - Default is "cancel".
        on_completed (Literal["cancel", "proceed"]):
            Action that the depending command should take when the dependency is completed.
            - "cancel": Cancel the command execution.
            - "proceed": Proceed with the command execution.
            - Default is "proceed".

    """

    command: "Command[Any, Any]"
    on_pending: Literal["defer", "cancel", "proceed"] = "defer"
    on_canceled: Literal["cancel", "proceed"] = "cancel"
    on_failed: Literal["cancel", "proceed"] = "cancel"
    on_completed: Literal["cancel", "proceed"] = "proceed"

    def evaluate(self) -> DependencyAction:
        """
        Evaluate the dependency entry based on the current state of the command.
        """
        command = cast("Command[CommandArgs, CommandResponse]", self.command)
        # no need for case _ here, type checker yells at us if we miss a case
        match command.response.status:
            case ResponseStatus.PENDING | ResponseStatus.CREATED:
                return _dependency_action_map[self.on_pending]
            case ResponseStatus.CANCELED:
                return _dependency_action_map[self.on_canceled]
            case ResponseStatus.FAILED:
                return _dependency_action_map[self.on_failed]
            case ResponseStatus.COMPLETED:
                return _dependency_action_map[self.on_completed]
