"""Behavior execution abstraction for queued Helios actions."""

from __future__ import annotations

import heapq
from dataclasses import asdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from .action_models import ActionDecision


class BehaviorStatus(Enum):
    QUEUED = "queued"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class BehaviorCommand:
    priority: int
    name: str
    action: str
    behavior_id: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    proposal_id: str = ""
    decision_id: str = ""
    channel_id: str = ""
    op_name: str = ""
    normalized_intensity: float = 0.0
    modality: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    policy_trace: dict[str, Any] = field(default_factory=dict)
    behavior_snapshot: dict[str, Any] = field(default_factory=dict)
    status: BehaviorStatus = BehaviorStatus.QUEUED
    result: Optional[dict[str, Any]] = None
    sort_index: int = 0


class BehaviorExecutor:
    def __init__(self):
        self._queue: list[tuple[int, int, BehaviorCommand]] = []
        self._paused: list[BehaviorCommand] = []
        self._current: Optional[BehaviorCommand] = None
        self._insert_counter = 0
        self._result_callback: Optional[Callable[[BehaviorCommand, dict[str, Any]], None]] = None

    @property
    def current(self) -> Optional[BehaviorCommand]:
        return self._current

    @property
    def queue_depth(self) -> int:
        return len(self._queue) + len(self._paused) + (1 if self._current else 0)

    def enqueue(self, command: BehaviorCommand) -> BehaviorCommand:
        self._insert_counter += 1
        command.sort_index = self._insert_counter
        command.status = BehaviorStatus.QUEUED

        if self._current is None:
            self._current = command
            self._current.status = BehaviorStatus.EXECUTING
            return command

        if command.priority > self._current.priority:
            self._current.status = BehaviorStatus.PAUSED
            self._paused.append(self._current)
            self._current = command
            self._current.status = BehaviorStatus.EXECUTING
            return command

        heapq.heappush(self._queue, (-command.priority, command.sort_index, command))
        return command

    def enqueue_named(self, name: str, action: str, priority: int, params: Optional[dict[str, Any]] = None) -> BehaviorCommand:
        return self.enqueue(
            BehaviorCommand(
                priority=priority,
                name=name,
                action=action,
                params=params or {},
            )
        )

    def enqueue_decision(self, decision: ActionDecision) -> BehaviorCommand:
        return self.enqueue(
            BehaviorCommand(
                priority=decision.execution_priority,
                name=decision.decision_id,
                action=decision.behavior_name,
                behavior_id=str(decision.behavior_snapshot.get("behavior_id", "") or ""),
                params=dict(decision.validated_params),
                proposal_id=decision.proposal_id,
                decision_id=decision.decision_id,
                channel_id=decision.selected_channel_id,
                op_name=decision.selected_op,
                normalized_intensity=decision.normalized_intensity,
                modality=decision.selected_modality,
                provenance=dict(decision.proposal_snapshot),
                policy_trace=dict(decision.policy_trace),
                behavior_snapshot=dict(decision.behavior_snapshot),
            )
        )

    def cancel(self, name: str) -> bool:
        if self._current and self._current.name == name:
            self._current.status = BehaviorStatus.CANCELLED
            self._current = None
            self._advance()
            return True

        removed_from_queue = self._remove_from_queue(name, BehaviorStatus.CANCELLED)
        removed_from_paused = self._remove_from_paused(name, BehaviorStatus.CANCELLED)
        return removed_from_queue or removed_from_paused

    def pause(self, name: str) -> bool:
        if self._current and self._current.name == name:
            self._current.status = BehaviorStatus.PAUSED
            self._paused.append(self._current)
            self._current = None
            self._advance()
            return True

        if self._remove_from_queue(name, BehaviorStatus.PAUSED, move_to_paused=True):
            return True
        return False

    def resume(self, name: str) -> bool:
        for index, command in enumerate(self._paused):
            if command.name != name:
                continue
            command.status = BehaviorStatus.QUEUED
            self._paused.pop(index)
            if self._current is None:
                self._current = command
                self._current.status = BehaviorStatus.EXECUTING
            else:
                heapq.heappush(self._queue, (-command.priority, command.sort_index, command))
            return True
        return False

    def complete_current(self, result: dict[str, Any]) -> Optional[BehaviorCommand]:
        if self._current is None:
            return None

        completed = self._current
        completed.status = BehaviorStatus.COMPLETED
        merged_result = dict(result)
        merged_result.setdefault("proposal_id", completed.proposal_id)
        merged_result.setdefault("decision_id", completed.decision_id)
        merged_result.setdefault("behavior_id", completed.behavior_id)
        merged_result.setdefault("channel_id", completed.channel_id)
        merged_result.setdefault("op_name", completed.op_name)
        merged_result.setdefault("normalized_intensity", completed.normalized_intensity)
        completed.result = merged_result
        self._current = None
        if self._result_callback:
            self._result_callback(completed, merged_result)
        self._advance()
        return completed

    def set_result_callback(self, callback: Callable[[BehaviorCommand, dict[str, Any]], None]) -> None:
        self._result_callback = callback

    def _advance(self) -> Optional[BehaviorCommand]:
        if not self._queue:
            return None
        _, _, command = heapq.heappop(self._queue)
        command.status = BehaviorStatus.EXECUTING
        self._current = command
        return command

    def _remove_from_queue(self, name: str, status: BehaviorStatus, move_to_paused: bool = False) -> bool:
        removed = False
        retained: list[tuple[int, int, BehaviorCommand]] = []
        while self._queue:
            entry = heapq.heappop(self._queue)
            command = entry[2]
            if command.name == name and not removed:
                command.status = status
                if move_to_paused:
                    self._paused.append(command)
                removed = True
                continue
            retained.append(entry)
        for entry in retained:
            heapq.heappush(self._queue, entry)
        return removed

    def _remove_from_paused(self, name: str, status: BehaviorStatus) -> bool:
        for index, command in enumerate(self._paused):
            if command.name != name:
                continue
            command.status = status
            self._paused.pop(index)
            return True
        return False