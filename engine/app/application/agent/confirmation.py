"""Code-level confirmation policy for Agent actions."""


class ConfirmationPolicy:
    WRITE_ACTIONS = {
        "register_skill",
        "register_tool",
        "configure_model_profile",
        "delete_skill",
        "delete_tool",
        "disable_skill",
        "disable_tool",
    }

    def requires_confirmation(self, action: str) -> bool:
        return action in self.WRITE_ACTIONS
