"""
MCP Client — wraps langchain-mcp-adapters MultiServerMCPClient.

MCP servers are run via npx (stdio transport).
Each server is started on first use and reused for the app lifetime.

Tools with MCP servers (use MCP):
  tavily, firecrawl, exa, playwright, serpapi, reddit, youtube, hackernews

Tools WITHOUT MCP servers (use direct SDK wrappers in implementations/):
  pytrends, newsapi, calendarific, meta_ads, linkedin_ads, semrush, crunchbase, patents

Usage:
    from app.tools.mcp_client import get_mcp_tools
    tools = await get_mcp_tools()           # all MCP tools as LangChain BaseTool list
    tools = await get_mcp_tools(["tavily_search", "exa_search"])  # filtered subset
"""
from __future__ import annotations

import asyncio
from typing import Any
from langchain_core.tools import BaseTool

from app.core.config import get_settings

settings = get_settings()

# MCP server definitions — command + env vars per server
# npx pulls the server package on first run (cached after that)
_MCP_SERVERS: dict[str, dict[str, Any]] = {
    "tavily": {
        "command": "npx",
        "args": ["-y", "tavily-mcp@latest"],
        "env": {"TAVILY_API_KEY": settings.tavily_api_key},
        "transport": "stdio",
    },
    "firecrawl": {
        "command": "npx",
        "args": ["-y", "firecrawl-mcp"],
        "env": {"FIRECRAWL_API_KEY": settings.firecrawl_api_key},
        "transport": "stdio",
    },
    "exa": {
        "command": "npx",
        "args": ["-y", "exa-mcp-server"],
        "env": {"EXA_API_KEY": settings.exa_api_key},
        "transport": "stdio",
    },
    "playwright": {
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest"],
        "env": {},
        "transport": "stdio",
    },
    "reddit": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-reddit"],
        "env": {
            "REDDIT_CLIENT_ID": settings.reddit_client_id,
            "REDDIT_CLIENT_SECRET": settings.reddit_client_secret,
            "REDDIT_USER_AGENT": settings.reddit_user_agent,
        },
        "transport": "stdio",
    },
    "hackernews": {
        "command": "npx",
        "args": ["-y", "mcp-hn"],
        "env": {},
        "transport": "stdio",
    },
}

# Global client cache — initialised once at startup
_mcp_client = None
_mcp_tools: list[BaseTool] = []
_init_lock = asyncio.Lock()


async def init_mcp_client() -> None:
    """
    Called once at FastAPI startup.
    Starts all configured MCP server processes and caches their tools.
    Skips servers whose required API keys are not configured.
    """
    global _mcp_client, _mcp_tools

    async with _init_lock:
        if _mcp_client is not None:
            return

        # Filter out servers missing required keys
        active_servers = {
            name: cfg
            for name, cfg in _MCP_SERVERS.items()
            if _server_has_keys(name, cfg)
        }

        if not active_servers:
            _mcp_tools = []
            return

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            _mcp_client = MultiServerMCPClient(active_servers)
            _mcp_tools = await _mcp_client.get_tools()
        except ImportError:
            # langchain-mcp-adapters not installed — degrade gracefully
            _mcp_tools = []
        except Exception as e:
            # MCP servers failed to start — log and degrade gracefully
            import logging
            logging.getLogger(__name__).warning(f"MCP client init failed: {e}. Falling back to direct SDK tools.")
            _mcp_tools = []


def _server_has_keys(name: str, cfg: dict) -> bool:
    """Returns False if any env var required by this server is empty."""
    for val in cfg.get("env", {}).values():
        if not val:
            return False
    return True


async def get_mcp_tools(tool_names: list[str] | None = None) -> list[BaseTool]:
    """
    Returns MCP-backed LangChain tools, optionally filtered by name.
    If MCP is unavailable, returns empty list (callers fall back to SDK tools).
    """
    if _mcp_client is None:
        await init_mcp_client()

    if tool_names is None:
        return _mcp_tools

    return [t for t in _mcp_tools if t.name in tool_names]


def get_mcp_tool_names() -> list[str]:
    """Returns names of all currently active MCP tools."""
    return [t.name for t in _mcp_tools]


async def close_mcp_client() -> None:
    """Called at FastAPI shutdown."""
    global _mcp_client, _mcp_tools
    if _mcp_client is not None:
        try:
            await _mcp_client.__aexit__(None, None, None)
        except Exception:
            pass
    _mcp_client = None
    _mcp_tools = []
