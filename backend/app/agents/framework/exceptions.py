class AgentFrameworkError(Exception):
    """Base exception for the agent framework."""


class AgentRegistrationError(AgentFrameworkError):
    """Raised when agent registration fails."""


class AgentNotFoundError(AgentFrameworkError):
    """Raised when an agent is not found in the registry."""


class AgentExecutionError(AgentFrameworkError):
    """Raised when agent execution fails."""


class ToolExecutionError(AgentFrameworkError):
    """Raised when a tool execution fails."""


class OrchestrationError(AgentFrameworkError):
    """Raised when orchestration fails."""


class InvalidContextError(AgentFrameworkError):
    """Raised when the provided context is invalid."""
