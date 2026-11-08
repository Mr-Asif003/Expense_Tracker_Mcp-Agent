"""Errors raised by the AI host."""

from __future__ import annotations


class HostError(Exception):
    """Base class for AI-host errors."""


class ConfigurationError(HostError):
    """Required configuration (for example an API key) is missing."""


class McpConnectionError(HostError):
    """The MCP server could not be started or reached."""


class ToolCallError(HostError):
    """An MCP tool reported an error."""
