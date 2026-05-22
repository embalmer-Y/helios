"""
io/limb.py — Behavioral Execution Abstraction Layer

Provides a unified behavior execution framework with priority queue management,
preemption, cancel/pause/resume support, and result feedback to RegulationEngine.

Requirements: 29.1, 29.3, 29.4, 29.5
"""

import heapq
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, List

logger = logging.getLogger(__name__)


class BehaviorStatus(Enum):
    """Status of a behavior command in the execution pipeline."""
    QUEUED = "queued"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(order=True)
class BehaviorCommand:
    """A behavior queued for execution by BehaviorExecutor."""
    priority: int  # Higher = more important (negated for min-heap)
    sort_index: int = field(compare=True)  # Tie-breaking insertion order
    name: str = field(compare=False, default="")
    action: str = field(compare=False, default="")
    params: dict = field(compare=False, default_factory=dict)
    status: BehaviorStatus = field(compare=False, default=BehaviorStatus.QUEUED)
    result: Optional[dict] = field(compare=False, default=None)


class BehaviorExecutor:
    """
    Unified behavior execution framework.

    Maintains a priority-ordered behavior queue where higher-priority behaviors
    preempt lower-priority ones. Supports cancel, pause, and resume operations.
    Reports execution results back to RegulationEngine via callback.

    Priority is stored negated in the min-heap so that the highest logical
    priority (largest number) is dequeued first.
    """

    def __init__(self):
        self._queue: List[BehaviorCommand] = []  # min-heap (negated priority)
        self._current: Optional[BehaviorCommand] = None
        self._paused: List[BehaviorCommand] = []
        self._insert_counter: int = 0
        self._result_callback: Optional[Callable] = None

    @property
    def current(self) -> Optional[BehaviorCommand]:
        """The currently executing behavior, or None."""
        return self._current

    @property
    def queue_depth(self) -> int:
        """Number of behaviors waiting in the queue (excludes current and paused)."""
        return len(self._queue)

    @property
    def paused_count(self) -> int:
        """Number of paused behaviors."""
        return len(self._paused)

    def enqueue(self, name: str, action: str, priority: int, params: dict = None):
        """
        Enqueue a behavior command. Higher priority preempts current.

        If no behavior is currently executing, the new command starts immediately.
        If the new command has higher priority than the current one, the current
        behavior is paused and the new one begins executing.
        Otherwise, the command is added to the priority queue.

        Args:
            name: Unique identifier for this behavior instance.
            action: The action type (e.g., "speak", "browse").
            priority: Priority level (higher = more important).
            params: Optional parameters for the action.
        """
        self._insert_counter += 1
        cmd = BehaviorCommand(
            priority=-priority,  # Negate for min-heap (highest priority = smallest)
            sort_index=self._insert_counter,
            name=name,
            action=action,
            params=params or {},
        )

        # Preemption: if current has lower priority, pause it
        if self._current and (-self._current.priority) < priority:
            logger.debug(
                f"Preempting '{self._current.name}' (priority={-self._current.priority}) "
                f"with '{name}' (priority={priority})"
            )
            self._current.status = BehaviorStatus.PAUSED
            self._paused.append(self._current)
            self._current = cmd
            cmd.status = BehaviorStatus.EXECUTING
        elif self._current is None:
            self._current = cmd
            cmd.status = BehaviorStatus.EXECUTING
            logger.debug(f"Executing behavior '{name}' (priority={priority})")
        else:
            heapq.heappush(self._queue, cmd)
            logger.debug(
                f"Queued behavior '{name}' (priority={priority}), "
                f"queue depth={len(self._queue)}"
            )

    def cancel(self, name: str) -> bool:
        """
        Cancel a queued, executing, or paused behavior by name.

        If the cancelled behavior was currently executing, advances to the next
        behavior in the queue.

        Args:
            name: The name of the behavior to cancel.

        Returns:
            True if a behavior with that name was found and cancelled.
        """
        # Check current
        if self._current and self._current.name == name:
            self._current.status = BehaviorStatus.CANCELLED
            logger.debug(f"Cancelled executing behavior '{name}'")
            self._current = None
            self._advance()
            return True

        # Check paused
        for i, cmd in enumerate(self._paused):
            if cmd.name == name:
                cmd.status = BehaviorStatus.CANCELLED
                self._paused.pop(i)
                logger.debug(f"Cancelled paused behavior '{name}'")
                return True

        # Check queue
        original_len = len(self._queue)
        self._queue = [c for c in self._queue if c.name != name]
        if len(self._queue) < original_len:
            heapq.heapify(self._queue)
            logger.debug(f"Cancelled queued behavior '{name}'")
            return True

        return False

    def pause(self, name: str) -> bool:
        """
        Pause the currently executing behavior.

        Only the currently executing behavior can be paused. After pausing,
        advances to the next behavior in the queue.

        Args:
            name: The name of the behavior to pause.

        Returns:
            True if the behavior was found executing and paused.
        """
        if self._current and self._current.name == name:
            self._current.status = BehaviorStatus.PAUSED
            self._paused.append(self._current)
            logger.debug(f"Paused behavior '{name}'")
            self._current = None
            self._advance()
            return True
        return False

    def resume(self, name: str) -> bool:
        """
        Resume a paused behavior by re-enqueueing it.

        The resumed behavior is placed back into the priority queue and will
        be executed according to its priority relative to other queued behaviors.

        Args:
            name: The name of the paused behavior to resume.

        Returns:
            True if the behavior was found in paused list and resumed.
        """
        for i, cmd in enumerate(self._paused):
            if cmd.name == name:
                cmd.status = BehaviorStatus.QUEUED
                self._paused.pop(i)
                heapq.heappush(self._queue, cmd)
                logger.debug(f"Resumed behavior '{name}', re-queued")
                # If nothing is currently executing, advance
                if self._current is None:
                    self._advance()
                return True
        return False

    def complete_current(self, result: dict):
        """
        Mark the current behavior as complete and report feedback.

        Invokes the result callback (if set) with the completed behavior,
        then advances to the next behavior in the queue.

        Args:
            result: The execution result dictionary to attach to the behavior.
        """
        if self._current:
            self._current.status = BehaviorStatus.COMPLETED
            self._current.result = result
            logger.debug(
                f"Completed behavior '{self._current.name}' with result: {result}"
            )
            if self._result_callback:
                self._result_callback(self._current)
            self._current = None
            self._advance()

    def _advance(self):
        """Advance to next behavior in queue after completion or cancel."""
        if self._queue:
            self._current = heapq.heappop(self._queue)
            self._current.status = BehaviorStatus.EXECUTING
            logger.debug(
                f"Advanced to behavior '{self._current.name}' "
                f"(priority={-self._current.priority})"
            )

    def set_result_callback(self, callback: Callable):
        """
        Set callback for behavior completion feedback to RegulationEngine.

        The callback receives the completed BehaviorCommand instance with
        its result field populated.

        Args:
            callback: A callable accepting a BehaviorCommand argument.
        """
        self._result_callback = callback
