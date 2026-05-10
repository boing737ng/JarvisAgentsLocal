"""Jarvis CLI: Rich REPL with slash commands."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from langchain_core.messages import HumanMessage
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import print as rprint

app = typer.Typer(help="Jarvis — Local Multi-Agent AI System")
console = Console()

BANNER = """
[bold cyan]     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗[/bold cyan]
[bold cyan]     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝[/bold cyan]
[bold cyan]     ██║███████║██████╔╝██║   ██║██║███████╗[/bold cyan]
[bold cyan]██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║[/bold cyan]
[bold cyan]╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║[/bold cyan]
[bold cyan] ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝[/bold cyan]
[dim]        Local Multi-Agent AI System v0.1.0[/dim]
"""

HELP_TEXT = """\
[bold]Available commands:[/bold]
  [cyan]/agents[/cyan]           — Show all configured agents and their models
  [cyan]/memory query <q>[/cyan] — Search long-term memory
  [cyan]/memory add <text>[/cyan]— Save text to memory (notes namespace)
  [cyan]/unload[/cyan]           — Unload all models from RAM
  [cyan]/reset[/cyan]            — Reset conversation history
  [cyan]/image <path>[/cyan]     — Analyze an image (Visionary agent)
  [cyan]/help[/cyan]             — Show this help
  [cyan]/quit[/cyan] or [cyan]/exit[/cyan]   — Exit Jarvis
"""


def setup_logging(level: str = "WARNING") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.WARNING),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def show_banner() -> None:
    console.print(BANNER)
    console.print("[dim]Type [cyan]/help[/cyan] for commands or just ask me anything![/dim]\n")


def show_agents() -> None:
    from jarvis.core.config import get_agents
    agents = get_agents()

    table = Table(title="Configured Agents", show_header=True, header_style="bold magenta")
    table.add_column("Agent", style="cyan", width=15)
    table.add_column("Model", style="green", width=25)
    table.add_column("Keep Alive", style="yellow", width=12)
    table.add_column("Temperature", style="blue", width=12)
    table.add_column("Tools", style="dim", width=30)

    for name, cfg in agents.items():
        table.add_row(
            name,
            cfg.model,
            str(cfg.keep_alive),
            str(cfg.temperature),
            ", ".join(cfg.tools) or "—",
        )

    console.print(table)

    # Also show running models
    from jarvis.core.model_manager import model_manager
    running = model_manager.list_running()
    if running:
        console.print("\n[bold yellow]Currently in RAM:[/bold yellow]")
        for m in running:
            size_mb = m.get("size", 0) // (1024 * 1024)
            console.print(f"  [green]●[/green] {m['name']} ({size_mb} MB)")
    else:
        console.print("\n[dim]No models currently in RAM[/dim]")


def handle_slash_command(cmd: str, state: dict) -> tuple[bool, bool]:
    """
    Handle slash commands.
    Returns (handled: bool, should_exit: bool)
    """
    parts = cmd.strip().split(" ", 2)
    command = parts[0].lower()

    if command in ("/quit", "/exit"):
        console.print("\n[bold cyan]Goodbye! 👋[/bold cyan]")
        return True, True

    elif command == "/help":
        console.print(Panel(HELP_TEXT, title="Help", border_style="cyan"))
        return True, False

    elif command == "/agents":
        show_agents()
        return True, False

    elif command == "/reset":
        state["messages"] = []
        state["research_results"] = []
        state["plan"] = ""
        state["code"] = ""
        state["execution_result"] = {}
        state["memory_results"] = []
        state["iteration"] = 0
        state["fix_attempts"] = 0
        console.print("[green]✓ Conversation reset[/green]")
        return True, False

    elif command == "/unload":
        from jarvis.core.model_manager import model_manager
        console.print("[yellow]Unloading all models from RAM...[/yellow]")
        model_manager.unload_all()
        console.print("[green]✓ All models unloaded[/green]")
        return True, False

    elif command == "/memory":
        if len(parts) < 3:
            console.print("[red]Usage: /memory query <text> OR /memory add <text>[/red]")
            return True, False

        subcommand = parts[1].lower()
        text = parts[2]

        from jarvis.tools.memory import get_memory
        memory = get_memory()

        if subcommand == "query":
            with console.status("[yellow]Searching memory...[/yellow]"):
                results = memory.query_all_namespaces(text, k=5)
            if results:
                console.print(Panel(
                    "\n".join(f"• {r}" for r in results),
                    title=f"Memory: '{text}'",
                    border_style="blue",
                ))
            else:
                console.print("[dim]No relevant memories found[/dim]")
        elif subcommand == "add":
            memory.add(text, namespace="notes")
            console.print(f"[green]✓ Saved to memory[/green]")
        return True, False

    elif command == "/image":
        if len(parts) < 2:
            console.print("[red]Usage: /image <path>[/red]")
            return True, False
        image_path = parts[1] if len(parts) > 1 else ""
        state["image_path"] = image_path
        state["current_task"] = f"Analyze this image: {image_path}"
        state["next_agent"] = "vision"
        return False, False  # Let it flow through the graph

    return False, False


def run_graph(user_input: str, state: dict) -> str:
    """Run the Jarvis graph with the given input."""
    from jarvis.graph import get_graph
    graph = get_graph()

    # Update state with new user message
    state["messages"] = state.get("messages", []) + [HumanMessage(content=user_input)]
    state["current_task"] = user_input
    state["iteration"] = 0
    state["fix_attempts"] = 0
    state["research_results"] = []
    state["plan"] = ""
    state["code"] = ""
    state["execution_result"] = {}
    state["memory_results"] = []
    state["final_answer"] = ""
    state["next_agent"] = ""
    state.setdefault("image_path", None)

    result = graph.invoke(state)

    # Update persistent state
    state.update(result)

    return result.get("final_answer", "") or _extract_last_ai_message(result.get("messages", []))


def _extract_last_ai_message(messages: list) -> str:
    from langchain_core.messages import AIMessage
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return msg.content
    return "[No response generated]"


def _format_response(text: str) -> None:
    """Display the response with rich formatting."""
    if not text:
        return
    # Try markdown rendering
    try:
        md = Markdown(text)
        console.print(Panel(md, title="[bold green]Jarvis[/bold green]", border_style="green", padding=(1, 2)))
    except Exception:
        console.print(Panel(text, title="[bold green]Jarvis[/bold green]", border_style="green"))


@app.command()
def run(
    log_level: str = typer.Option("WARNING", "--log-level", "-l", help="Log level (DEBUG/INFO/WARNING/ERROR)"),
    no_banner: bool = typer.Option(False, "--no-banner", help="Skip the ASCII art banner"),
):
    """Start the Jarvis interactive REPL."""
    setup_logging(log_level)

    if not no_banner:
        show_banner()

    # Persistent conversation state
    state: dict = {
        "messages": [],
        "current_task": "",
        "plan": "",
        "code": "",
        "execution_result": {},
        "research_results": [],
        "memory_results": [],
        "next_agent": "",
        "iteration": 0,
        "fix_attempts": 0,
        "image_path": None,
        "final_answer": "",
    }

    # Setup prompt with history
    history_file = Path.home() / ".jarvis_history"
    session: PromptSession = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
    )

    console.print("[dim]Ollama endpoint: [cyan]http://localhost:11434[/cyan][/dim]\n")

    while True:
        try:
            user_input = session.prompt(
                [("class:prompt", "You ❯ ")],
                style=None,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold cyan]Goodbye! 👋[/bold cyan]")
            break

        if not user_input:
            continue

        # Handle slash commands
        if user_input.startswith("/"):
            handled, should_exit = handle_slash_command(user_input, state)
            if should_exit:
                break
            if handled:
                continue

        # Run through graph
        try:
            with console.status(
                "[bold yellow]⚙ Thinking...[/bold yellow]",
                spinner="dots",
            ):
                response = run_graph(user_input, state)

            _format_response(response)

            # Show execution artifacts if any
            exec_result = state.get("execution_result", {})
            if exec_result:
                color = "green" if exec_result.get("success") else "red"
                status_icon = "✓" if exec_result.get("success") else "✗"
                console.print(
                    f"[{color}]{status_icon} Code executed in {exec_result.get('duration', 0):.1f}s "
                    f"(exit_code={exec_result.get('exit_code')})[/{color}]"
                )
                if exec_result.get("stdout"):
                    console.print(Panel(
                        exec_result["stdout"][:2000],
                        title="[bold]stdout[/bold]",
                        border_style="dim",
                    ))

            # Show memory save suggestion
            if state.get("research_results"):
                console.print(
                    "[dim]💡 Tip: Use [cyan]/memory add <info>[/cyan] to save important findings[/dim]"
                )

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted[/yellow]")
        except Exception as e:
            console.print(f"\n[bold red]Error: {e}[/bold red]")
            if log_level.upper() == "DEBUG":
                import traceback
                traceback.print_exc()
