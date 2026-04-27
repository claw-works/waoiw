"""
tools/vision_test.py — test vision detection on a screenshot

Usage:
    python -m waoiw.tools.vision_test                  # live capture
    python -m waoiw.tools.vision_test path/to/img.png  # from file
"""
import sys
import time
import numpy as np
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()


def test_live():
    console.print("[bold cyan]Vision test[/] — capturing in 3s...")
    time.sleep(3)

    from waoiw.capture import capture_full, save_screenshot
    from waoiw.vision.reader import read_game_state

    frame = capture_full()
    path = save_screenshot(frame, "vision_test")
    console.print(f"Screenshot saved: {path}")

    state = read_game_state(frame)
    _print_state(state)


def test_file(img_path: str):
    import cv2
    from waoiw.vision.reader import read_game_state

    console.print(f"Loading: {img_path}")
    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        console.print("[red]Failed to load image[/]")
        return

    # Convert BGR to BGRA if needed
    if img.shape[2] == 3:
        import cv2
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

    state = read_game_state(img)
    _print_state(state)


def _print_state(state):
    t = Table(title="Detected Game State")
    t.add_column("Field", style="cyan")
    t.add_column("Value", style="bold")

    t.add_row("HP %",         f"{state.hp_pct*100:.1f}%" if state.hp_pct is not None else "[dim]not configured[/]")
    t.add_row("Mana %",       f"{state.mana_pct*100:.1f}%" if state.mana_pct is not None else "[dim]not configured[/]")
    t.add_row("In Combat",    "⚔ YES" if state.in_combat else "no")
    t.add_row("Node Visible", "✓ YES" if state.gather_node_visible else "no")
    t.add_row("Node Pos",     str(state.gather_node_pos) if state.gather_node_pos else "—")

    console.print(t)
    console.print()
    console.print("[dim]Tip: run calibrate first if values show 'not configured'[/]")
    console.print("  [bold]python -m waoiw.tools.calibrate[/]")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_file(sys.argv[1])
    else:
        test_live()
