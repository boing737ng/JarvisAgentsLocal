"""
Jarvis LangGraph: connects all agents into a stateful graph.

Flow:
  user_input → orchestrator → [respond|research|plan|code|recall|vision|finalize]
                     ↑______________________________________________↓  (loop)
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from jarvis.core.config import get_settings
from jarvis.core.state import JarvisState

logger = logging.getLogger(__name__)


# ── Node implementations ──────────────────────────────────────────────────────


def orchestrator_node(state: JarvisState) -> dict[str, Any]:
    """Route the current task to the appropriate specialist."""
    from jarvis.agents.orchestrator import OrchestratorAgent

    agent = OrchestratorAgent()
    messages = state.get("messages", [])
    current_task = state.get("current_task", "")

    # Build context from previous results
    context_parts = []
    if state.get("research_results"):
        context_parts.append("Web research results:\n" + "\n".join(
            f"[{r['url']}]\n{r['summary']}" for r in state["research_results"]
        ))
    if state.get("plan"):
        context_parts.append(f"Current plan:\n{state['plan']}")
    if state.get("execution_result"):
        ex = state["execution_result"]
        context_parts.append(
            f"Code execution result (exit_code={ex.get('exit_code')}):\n"
            f"stdout: {ex.get('stdout', '')}\n"
            f"stderr: {ex.get('stderr', '')}"
        )
    if state.get("memory_results"):
        context_parts.append("Memory recall:\n" + "\n".join(state["memory_results"]))

    context = "\n\n---\n\n".join(context_parts) if context_parts else ""

    # Get last user message
    user_msg = current_task
    if not user_msg and messages:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_msg = msg.content
                break

    result = agent.route(user_msg, context=context)

    next_agent = result.get("next_agent", "respond")
    message = result.get("message", "")
    task_context = result.get("task_context", user_msg)

    # Guard rails: prevent re-running a specialist when results already exist
    if next_agent == "research" and state.get("research_results"):
        logger.warning("[graph] Blocking redundant research route (results already present) → respond")
        next_agent = "respond"
        message = message or "Based on the research I've gathered, here's a summary."
    if next_agent == "recall" and state.get("memory_results"):
        logger.warning("[graph] Blocking redundant recall route → respond")
        next_agent = "respond"
    if next_agent == "plan" and state.get("plan"):
        logger.warning("[graph] Plan already exists, routing to code instead")
        next_agent = "code"

    logger.info("[graph] Orchestrator routes → %s", next_agent)

    iteration = state.get("iteration", 0) + 1
    settings = get_settings()
    if iteration > settings.graph.max_iterations:
        logger.warning("[graph] Max iterations reached, forcing END")
        next_agent = "respond"
        message = "I've reached the maximum number of reasoning steps. Here's what I have so far."

    new_messages = []
    if next_agent == "respond" and message:
        new_messages.append(AIMessage(content=message))

    return {
        "messages": new_messages,
        "next_agent": next_agent,
        "current_task": task_context,
        "iteration": iteration,
        "final_answer": message if next_agent == "respond" else state.get("final_answer", ""),
    }


def research_node(state: JarvisState) -> dict[str, Any]:
    """Perform web research: search + fetch + distill."""
    from jarvis.tools.web_search import search
    from jarvis.tools.web_fetch import fetch_and_distill

    task = state.get("current_task", "")
    logger.info("[graph] Research node: %s", task[:80])

    results = search(task, k=4)
    distilled = []

    for r in results[:3]:  # Limit to top 3 to save time
        url = r.get("url", "")
        if not url:
            continue
        summary = fetch_and_distill(url, topic=task)
        distilled.append({"url": url, "title": r.get("title", ""), "summary": summary})

    return {"research_results": distilled}


def plan_node(state: JarvisState) -> dict[str, Any]:
    """Generate a step-by-step plan using the Architect."""
    from jarvis.agents.architect import ArchitectAgent

    agent = ArchitectAgent()
    task = state.get("current_task", "")
    logger.info("[graph] Architect planning: %s", task[:80])

    plan = agent.plan(task)
    return {"plan": plan}


def code_node(state: JarvisState) -> dict[str, Any]:
    """Write and execute Python code, auto-fixing on failure."""
    from jarvis.agents.coder import CoderAgent
    from jarvis.tools.docker_exec import run_python_in_sandbox

    agent = CoderAgent()
    task = state.get("current_task", "")
    plan = state.get("plan", "")
    current_code = state.get("code", "")
    fix_attempts = state.get("fix_attempts", 0)
    execution_result = state.get("execution_result", {})

    MAX_FIX_ATTEMPTS = 3

    # If we have a previous failed execution, try to fix
    if current_code and execution_result and not execution_result.get("success", True):
        if fix_attempts < MAX_FIX_ATTEMPTS:
            logger.info("[graph] Coder fixing code (attempt %d/%d)", fix_attempts + 1, MAX_FIX_ATTEMPTS)
            code = agent.fix_code(current_code, execution_result.get("stderr", ""), task=task)
            fix_attempts += 1
        else:
            logger.warning("[graph] Max fix attempts reached")
            return {"next_agent": "respond", "final_answer": f"Could not fix code after {MAX_FIX_ATTEMPTS} attempts.\nLast error:\n{execution_result.get('stderr', '')}"}
    else:
        logger.info("[graph] Coder writing new code: %s", task[:80])
        code = agent.write_code(task, plan=plan)
        fix_attempts = 0

    if not code:
        return {"code": "", "execution_result": {"success": False, "stderr": "No code generated", "exit_code": -1}}

    logger.info("[graph] Running code in Docker sandbox...")
    result = run_python_in_sandbox(code)

    return {
        "code": code,
        "execution_result": result,
        "fix_attempts": fix_attempts,
    }


def recall_node(state: JarvisState) -> dict[str, Any]:
    """Query long-term memory."""
    from jarvis.tools.memory import get_memory

    task = state.get("current_task", "")
    logger.info("[graph] Memory recall: %s", task[:80])

    memory = get_memory()
    results = memory.query_all_namespaces(task, k=5)
    return {"memory_results": results}


def vision_node(state: JarvisState) -> dict[str, Any]:
    """Analyze an image."""
    from jarvis.agents.visionary import VisionaryAgent

    image_path = state.get("image_path", "")
    task = state.get("current_task", "Describe this image.")

    if not image_path:
        return {"final_answer": "[No image path provided for vision task]", "next_agent": "respond"}

    agent = VisionaryAgent()
    result = agent.analyze_image(image_path, question=task)
    return {"final_answer": result, "next_agent": "respond"}


def finalize_node(state: JarvisState) -> dict[str, Any]:
    """Deep analysis via Grandmaster (qwen3.5:27b)."""
    from jarvis.agents.grandmaster import GrandmasterAgent

    agent = GrandmasterAgent()

    # Compile comprehensive brief
    parts = [f"Task: {state.get('current_task', '')}"]
    if state.get("research_results"):
        parts.append("Research:\n" + "\n".join(
            f"- [{r['title']}]: {r['summary']}" for r in state["research_results"]
        ))
    if state.get("plan"):
        parts.append(f"Plan:\n{state['plan']}")
    if state.get("code"):
        parts.append(f"Code:\n{state['code']}")
    if state.get("execution_result"):
        ex = state["execution_result"]
        parts.append(f"Execution output:\n{ex.get('stdout', '')}")

    brief = "\n\n".join(parts)
    logger.info("[graph] Grandmaster analyzing...")

    result = agent.analyze(brief)
    return {
        "final_answer": result,
        "messages": [AIMessage(content=result)],
        "next_agent": "respond",
    }


# ── Routing ───────────────────────────────────────────────────────────────────


def route_after_orchestrator(state: JarvisState) -> str:
    """Conditional edge: decide which node to visit after orchestrator."""
    next_agent = state.get("next_agent", "respond")
    mapping = {
        "respond": END,
        "research": "research",
        "plan": "plan",
        "code": "code",
        "recall": "recall",
        "vision": "vision",
        "finalize": "finalize",
    }
    return mapping.get(next_agent, END)


def route_after_code(state: JarvisState) -> str:
    """After code execution: if failed and can retry → back to orchestrator, else respond."""
    result = state.get("execution_result", {})
    fix_attempts = state.get("fix_attempts", 0)

    if not result.get("success") and fix_attempts < 3:
        # Re-enter code node to attempt fix
        return "code"
    return "orchestrator"


def route_after_specialist(state: JarvisState) -> str:
    """After research/recall/plan/vision/finalize → back to orchestrator."""
    # Check if we already have a final answer (vision/finalize set it directly)
    if state.get("next_agent") == "respond":
        return END
    return "orchestrator"


# ── Graph builder ─────────────────────────────────────────────────────────────


def build_graph() -> Any:
    """Construct and compile the Jarvis LangGraph."""
    graph = StateGraph(JarvisState)

    # Add nodes
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("research", research_node)
    graph.add_node("plan", plan_node)
    graph.add_node("code", code_node)
    graph.add_node("recall", recall_node)
    graph.add_node("vision", vision_node)
    graph.add_node("finalize", finalize_node)

    # Entry point
    graph.add_edge(START, "orchestrator")

    # Conditional routing from orchestrator
    graph.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            END: END,
            "research": "research",
            "plan": "plan",
            "code": "code",
            "recall": "recall",
            "vision": "vision",
            "finalize": "finalize",
        },
    )

    # Code node: retry on failure
    graph.add_conditional_edges(
        "code",
        route_after_code,
        {
            "code": "code",
            "orchestrator": "orchestrator",
        },
    )

    # All specialists loop back to orchestrator (or END if final_answer set)
    for node in ("research", "plan", "recall"):
        graph.add_edge(node, "orchestrator")

    graph.add_conditional_edges(
        "vision",
        route_after_specialist,
        {END: END, "orchestrator": "orchestrator"},
    )
    graph.add_conditional_edges(
        "finalize",
        route_after_specialist,
        {END: END, "orchestrator": "orchestrator"},
    )

    return graph.compile()


# Singleton compiled graph
_compiled_graph: Any = None


def get_graph() -> Any:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
