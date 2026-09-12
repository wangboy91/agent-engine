"""Explicit execution states shared by Skill and Agent runs."""

from enum import StrEnum


class ExecutionState(StrEnum):
    CREATED = "created"
    INPUT_VALIDATING = "input_validating"
    CONTEXT_PREPARING = "context_preparing"
    MODEL_TURN_RUNNING = "model_turn_running"
    TOOL_CALL_REQUESTED = "tool_call_requested"
    TOOL_POLICY_CHECKING = "tool_policy_checking"
    WAITING_CONFIRMATION = "waiting_confirmation"
    TOOL_EXECUTING = "tool_executing"
    TOOL_RESULT_OBSERVING = "tool_result_observing"
    OUTPUT_VALIDATING = "output_validating"
    ARTIFACT_REGISTERING = "artifact_registering"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    REQUIRES_INPUT = "requires_input"
