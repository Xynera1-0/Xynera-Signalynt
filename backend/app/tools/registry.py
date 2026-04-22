"""
Tool Registry — single instantiation, filtered per agent.
All tools registered here. Agents receive only their scoped subset.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any

AgentID = str  # trend_scout | spy_scout | anthropologist | contextual_scout | temporal_agent | temporal_poller


@dataclass
class ToolEntry:
    name: str
    fn: Callable[..., Awaitable[Any]]   # the async tool function
    agents: list[AgentID]
    description: str = ""


_REGISTRY: dict[str, ToolEntry] = {}


def register(name: str, fn: Callable, agents: list[AgentID], description: str = "") -> None:
    _REGISTRY[name] = ToolEntry(name=name, fn=fn, agents=agents, description=description)


def get_tools_for(agent_id: AgentID) -> dict[str, Callable]:
    """Returns {tool_name: fn} for tools this agent is allowed to use."""
    return {
        entry.name: entry.fn
        for entry in _REGISTRY.values()
        if agent_id in entry.agents
    }


def get_all_tool_names() -> list[str]:
    return list(_REGISTRY.keys())
