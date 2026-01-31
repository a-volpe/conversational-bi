"""Custom exceptions for the conversational BI application."""


class ConversationalBIError(Exception):
    """Base exception for all application errors."""

    pass


class SQLInjectionError(ConversationalBIError):
    """Raised when SQL injection is detected."""

    pass


class QueryExecutionError(ConversationalBIError):
    """Raised when a database query fails to execute."""

    pass


class AgentDiscoveryError(ConversationalBIError):
    """Raised when agent discovery fails."""

    pass


class AgentCommunicationError(ConversationalBIError):
    """Raised when communication with an agent fails."""

    pass


class LLMError(ConversationalBIError):
    """Raised when LLM call fails."""

    pass
