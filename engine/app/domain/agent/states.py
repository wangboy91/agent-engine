"""Explicit Agent turn states."""

from enum import StrEnum


class AgentTurnState(StrEnum):
    MESSAGE_RECEIVED = "message_received"
    SESSION_LOADED = "session_loaded"
    INTENT_CLASSIFIED = "intent_classified"
    ROUTE_RESOLVED = "route_resolved"
    INPUT_RESOLVED = "input_resolved"
    PLAN_BUILT = "plan_built"
    POLICY_CHECKED = "policy_checked"
    WAITING_USER_INPUT = "waiting_user_input"
    WAITING_CONFIRMATION = "waiting_confirmation"
    ACTIONS_DISPATCHING = "actions_dispatching"
    RESULTS_OBSERVED = "results_observed"
    RESPONSE_COMPOSED = "response_composed"
    TURN_PERSISTED = "turn_persisted"
    COMPLETED = "completed"
    FAILED = "failed"
