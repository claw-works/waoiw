"""
waoiw/run.py — main entry point

Usage:
    python -m waoiw.run          # start supervised gather session
    python -m waoiw.capture test # test screenshot only
    python -m waoiw.vision test  # test vision detection
"""
import sys
import time
import threading
import signal

from rich.console import Console

from waoiw.config import config
from waoiw.capture import capture_full
from waoiw.vision.reader import read_game_state
from waoiw.brain.states import StateMachine, State, ActionType
from waoiw.supervisor.panel import SupervisorPanel

console = Console()


def main():
    console.print("[bold cyan]waoiw[/] 💣 starting up...")
    console.print(f"  pause key : [bold]{config.pause_key}[/]")
    console.print(f"  max session: [bold]{config.max_session_minutes} min[/]")
    console.print()

    sm = StateMachine()
    panel = SupervisorPanel(sm)
    stop_event = threading.Event()

    # Start the live display in a background thread
    display_thread = threading.Thread(
        target=panel.run_live,
        args=(stop_event,),
        daemon=True,
    )
    display_thread.start()

    panel.log("Agent started", "ok")

    # Listen for pause key (keyboard polling via pydirectinput is Windows-only)
    try:
        import keyboard
        keyboard.add_hotkey(config.pause_key, panel.toggle_pause)
        panel.log(f"Hotkey {config.pause_key} registered", "info")
    except ImportError:
        panel.log("'keyboard' package not found — hotkey disabled", "warn")
    except Exception as e:
        panel.log(f"Hotkey error: {e}", "warn")

    def shutdown(sig=None, frame=None):
        panel.log("Shutting down...", "warn")
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    session_start = time.time()
    interval = config.screenshot_interval_ms / 1000.0

    # ── Main loop ─────────────────────────────────────────────────────────────
    while not stop_event.is_set():
        # Auto-pause after max session time
        elapsed_min = (time.time() - session_start) / 60
        if elapsed_min >= config.max_session_minutes:
            panel.log(f"Max session time reached ({config.max_session_minutes}m) — pausing", "warn")
            sm.transition(State.PAUSED, "max session time")
            panel.paused = True

        # Grab frame
        frame = capture_full()
        game_state = read_game_state(frame)

        # Decide
        action = sm.decide(game_state)
        panel.update(game_state, action)

        # Execute (skip if paused)
        if sm.state != State.PAUSED:
            _execute(action, panel)

        time.sleep(interval)


def _execute(action, panel: SupervisorPanel):
    """Execute an action using the input layer."""
    from waoiw.brain.states import ActionType
    from waoiw.executor.input import move_to, interact, press_key, random_delay

    if action.type == ActionType.WAIT:
        pass  # do nothing

    elif action.type == ActionType.SCAN:
        # Occasionally rotate camera slightly to expand minimap view
        import random
        if random.random() < 0.1:
            panel.log("Rotating camera to scan", "info")
            press_key("a" if random.random() < 0.5 else "d", hold_ms=random.randint(200, 500))

    elif action.type == ActionType.MOVE_TO:
        if action.pos:
            panel.log(f"Moving toward node @ {action.pos}", "action")
            # Click minimap position to navigate
            move_to(action.pos)

    elif action.type == ActionType.INTERACT:
        panel.log("Interacting with node", "action")
        interact()

    elif action.type == ActionType.FIGHT:
        panel.log("⚔ In combat — auto-attacking", "warn")
        press_key("1")  # basic attack key — customize to your setup


if __name__ == "__main__":
    main()
