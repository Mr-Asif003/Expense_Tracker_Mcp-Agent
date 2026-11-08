"""Interface-agnostic chat turn handling, shared by the CLI and the Streamlit UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from expense_tracker.host.results import content_to_text


@dataclass(frozen=True)
class ToolTrace:
    """One tool invocation made by the agent during a turn."""

    name: str
    arguments: dict[str, Any]
    result: str = ""


@dataclass(frozen=True)
class ChatReply:
    text: str
    tool_calls: list[ToolTrace] = field(default_factory=list)


def _extract_tool_traces(messages: list[Any]) -> list[ToolTrace]:
    """Collect tool calls (and their results) made after the latest human message."""
    last_human = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=-1)
    turn = messages[last_human + 1 :]
    results = {
        m.tool_call_id: content_to_text(m.content) for m in turn if isinstance(m, ToolMessage)
    }
    traces: list[ToolTrace] = []
    for message in turn:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                traces.append(
                    ToolTrace(
                        name=call["name"],
                        arguments=dict(call.get("args", {})),
                        result=results.get(call.get("id") or "", ""),
                    )
                )
    return traces


async def ask(agent: Any, thread_id: str, user_text: str) -> ChatReply:
    """Send one user message to the agent and return its reply and tool trace."""
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=user_text)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    messages = result.get("messages", [])
    if not messages:
        return ChatReply(text="No response was returned.")
    return ChatReply(
        text=content_to_text(messages[-1].content) or "(empty response)",
        tool_calls=_extract_tool_traces(messages),
    )
