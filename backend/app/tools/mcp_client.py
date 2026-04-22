"""
MCP Client — wraps langchain-mcp-adapters MultiServerMCPClient.

MCP servers are run via npx (stdio transport).
Each server is started on first use and reused for the app lifetime.

Tools with MCP servers (use MCP):
  tavily, firecrawl, exa, playwright, serpapi, reddit, youtube

Tools WITHOUT MCP servers (use direct SDK wrappers in implementations/):
  hn_algolia (direct HTTP — no API key), pytrends, newsapi, calendarific,
  meta_ads, linkedin_ads, moz, crunchbase, patents

Usage:
    from app.tools.mcp_client import get_mcp_tools
    tools = await get_mcp_tools()           # all MCP tools as LangChain BaseTool list
    tools = await get_mcp_tools(["tavily_search", "exa_search"])  # filtered subset
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from langchain_core.tools import BaseTool

from app.core.config import get_settings

logger = logging.getLogger(__name__)
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
}

# Global client cache — initialised once at startup
_mcp_tools: list[BaseTool] = []
_init_lock = asyncio.Lock()
_initialized = False


async def init_mcp_client() -> None:
    """
    Called once at FastAPI startup.
    Tries each MCP server individually so one failure doesn't kill others.
    Skips servers whose required API keys are not configured.
    """
    global _mcp_tools, _initialized

    async with _init_lock:
        if _initialized:
            return

        _initialized = True

        # Filter out servers missing required keys
        active_servers = {
            name: cfg
            for name, cfg in _MCP_SERVERS.items()
            if _server_has_keys(name, cfg)
        }

        if not active_servers:
            logger.warning("MCP: no servers have required API keys configured — all tools will use SDK fallbacks")
            _mcp_tools = []
            return

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError:
            logger.warning("MCP: langchain-mcp-adapters not installed — using SDK fallbacks")
            _mcp_tools = []
            return

        # Try each server individually so one broken server doesn't kill the rest
        working_servers: dict[str, dict[str, Any]] = {}
        for name, cfg in active_servers.items():
            try:
                client = MultiServerMCPClient({name: cfg})
                tools = await asyncio.wait_for(client.get_tools(), timeout=15)
                working_servers[name] = cfg
                logger.info("MCP: server '%s' OK — %d tools loaded", name, len(tools))
            except asyncio.TimeoutError:
                logger.warning("MCP: server '%s' timed out — skipping", name)
            except Exception as exc:
                logger.warning("MCP: server '%s' failed (%s: %s) — skipping", name, type(exc).__name__, exc)

        if not working_servers:
            logger.warning("MCP: all servers failed — falling back to direct SDK tools")
            _mcp_tools = []
            return

        # Build final client from only working servers
        try:
            final_client = MultiServerMCPClient(working_servers)
            _mcp_tools = await final_client.get_tools()
            logger.info("MCP: initialized with %d servers, %d tools total: %s",
                        len(working_servers), len(_mcp_tools),
                        [t.name for t in _mcp_tools])
        except Exception as exc:
            logger.error("MCP: final client init failed: %s", exc)
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
    if not _initialized:
        await init_mcp_client()

    if tool_names is None:
        return _mcp_tools

    return [t for t in _mcp_tools if t.name in tool_names]


def get_mcp_tool_names() -> list[str]:
    """Returns names of all currently active MCP tools."""
    return [t.name for t in _mcp_tools]


async def close_mcp_client() -> None:
    """Called at FastAPI shutdown."""
    global _mcp_tools, _initialized
    _mcp_tools = []
    _initialized = False
