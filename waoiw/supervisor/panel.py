"""
supervisor/panel.py — terminal UI showing agent status in real time
Uses `rich` for a live dashboard.

Controls:
  F12 (configurable) — pause/resume
  Ctrl+C             — stop
"""
import time
import threading
from collections import deque
from datetime import datetime

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from waoiw.brain.states import State, Action, StateMachine
from waoiw.vision.reader import GameState
from waoiw.config import config

console = Console()


class SupervisorPanel:
    def __init__(self, sm: StateMachine):
        self.sm = sm
        self.paused = False
        self._log: deque[str] = deque(maxlen=12)
        self._last_game_state: GameState | None = None
        self._last_action: Action | None = None
        self._start_time = time.time()
        self._gather_count = 0
        self._lock = threading.Lock()

    def log(self, msg: str, level: str = "info") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        icons = {"info": "·", "ok": "✓", "warn": "⚠", "error": "✗", "action": "→"}
        icon = icons.get(level, "·")
        with self._lock:
            self._log.append(f"[dim]{ts}[/dim] {icon} {msg}")

    def update(self, game_state: GameState, action: Action) -> None:
        with self._lock:
            self._last_game_state = game_state
            self._last_action = action
            if action.type.name == "INTERACT":
                self._gather_count += 1

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        if self.paused:
            self.sm.transition(State.PAUSED, "manual pause")
            self.log("⏸ Paused by user", "warn")
        else:
            self.sm.transition(State.IDLE, "resumed")
            self.log("▶ Resumed", "ok")

    def _build_display(self) -> Panel:
        gs = self._last_game_state
        sm = self.sm
        action = self._last_action
        elapsed = int(time.time() - self._start_time)
        elapsed_str = f"{elapsed // 3600:02d}:{(elapsed % 3600) // 60:02d}:{elapsed % 60:02d}"

        # Status line
        state_colors = {
            State.IDLE: "cyan",
            State.MOVING: "yellow",
            State.GATHERING: "green",
            State.COMBAT: "red",
            State.PAUSED: "dim",
        }
        color = state_colors.get(sm.state, "white")
        state_text = Text(f" {sm.state.name} ", style=f"bold {color} on default")

        # Stats table
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("key", style="dim", width=12)
        table.add_column("val", style="bold")

        table.add_row("State", state_text)
        table.add_row("Action", str(action) if action else "—")

        if gs:
            hp_bar = _make_bar(gs.hp_pct, 20, "green") if gs.hp_pct is not None else "?"
            mp_bar = _make_bar(gs.mana_pct, 20, "blue") if gs.mana_pct is not None else "?"
            table.add_row("HP", hp_bar)
            table.add_row("Mana", mp_bar)
            table.add_row("Node", "✓ visible" if gs.gather_node_visible else "—")

        table.add_row("Gathered", str(self._gather_count))
        table.add_row("Uptime", elapsed_str)
        table.add_row("", "")
        table.add_row(f"[{config.pause_key}]", "pause / resume")

        # Log
        log_text = "\n".join(self._log) or "[dim]no events yet[/dim]"

        from rich.columns import Columns
        from rich.console import Group
        combined = Group(table, Panel(log_text, title="log", border_style="dim"))
        title = "🔍 waoiw supervisor" + (" [blink bold red]PAUSED[/]" if self.paused else "")
        return Panel(combined, title=title, border_style=color)

    def run_live(self, stop_event: threading.Event) -> None:
        """Run the live display loop. Call from a background thread."""
        with Live(self._build_display(), console=console, refresh_per_second=4) as live:
            while not stop_event.is_set():
                live.update(self._build_display())
                time.sleep(0.25)


def _make_bar(value: float | None, width: int, color: str) -> str:
    if value is None:
        return "?"
    filled = int(round(value * width))
    bar = "█" * filled + "░" * (width - filled)
    pct = f"{value*100:.0f}%"
    return f"[{color}]{bar}[/] {pct}"
