"""LangGraph state definition for Jarvis."""
from __future__ import annotations

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class JarvisState(TypedDict):
    """Shared state flowing through the LangGraph graph."""

    # Conversation history (append-only via add_messages reducer)
    messages: Annotated[list[BaseMessage], add_messages]

    # Current high-level task description
    current_task: str

    # Plan produced by architect
    plan: str

    # Latest code produced by coder
    code: str

    # Execution results (docker stdout/stderr)
    execution_result: dict[str, Any]

    # Research results (list of {url, summary})
    research_results: list[dict[str, str]]

    # Memory query results
    memory_results: list[str]

    # Next agent to route to
    next_agent: str

    # Iteration counter (protection against infinite loops)
    iteration: int

    # Code fix attempts
    fix_attempts: int

    # Image path for vision agent
    image_path: Optional[str]

    # Final answer to display to user
    final_answer: str
