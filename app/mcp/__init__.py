"""MCP client adapters for external tools."""

from .filesystem_client import FilesystemMCPClient
from .github_client import GitHubMCPClient

__all__ = ["FilesystemMCPClient", "GitHubMCPClient"]
