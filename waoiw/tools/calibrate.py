"""
tools/calibrate.py — interactive calibration tool

Run this to set up your region coordinates in config.
Lets you click corners of HP bar, minimap, etc. and saves to .env

Usage:
    python -m waoiw.tools.calibrate
"""
import time
import json
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt, Confirm

console = Console()

REGIONS = [
    ("region_hp_bar",     "HP bar (the green bar, player frame)"),
    ("region_mana_bar",   "Mana bar (blue bar, player frame)"),
    ("region_minimap",    "Minimap (full circle)"),
    ("region_action_bar", "Action bar row 1"),
]


def capture_region_interactive(name: str, description: str) -> dict | None:
    """Ask user to click two corners of a region."""
    console.print(f"\n[bold yellow]Calibrating:[/] {description}")
    console.print("  → Position your mouse at the [bold]TOP-LEFT[/] corner, then press ENTER")
    input()

    try:
        import pydirectinput
        x1, y1 = pydirectinput.position()
        console.print(f"  Top-left: ({x1}, {y1})")

        console.print("  → Now move to [bold]BOTTOM-RIGHT[/] corner, then press ENTER")
        input()
        x2, y2 = pydirectinput.position()
        console.print(f"  Bottom-right: ({x2}, {y2})")

        region = {
            "left": min(x1, x2),
            "top": min(y1, y2),
            "width": abs(x2 - x1),
            "height": abs(y2 - y1),
        }
        console.print(f"  [green]✓[/] Region: {region}")
        return region

    except ImportError:
        console.print("[red]pydirectinput not installed — run pip install pydirectinput[/]")
        return None


def main():
    console.print("[bold cyan]waoiw calibration tool[/] 💣")
    console.print("This will walk you through setting up screen regions.")
    console.print("Make sure WoW is open and visible.\n")

    env_path = Path(".env")
    existing = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()

    results = dict(existing)

    for name, description in REGIONS:
        env_key = f"WAOIW_{name.upper()}"
        if env_key in existing:
            console.print(f"[dim]Skipping {name} (already set: {existing[env_key]})[/]")
            if not Confirm.ask("  Recalibrate?", default=False):
                continue

        region = capture_region_interactive(name, description)
        if region:
            results[env_key] = json.dumps(region)

    # Write .env
    lines = [f"{k}={v}" for k, v in results.items()]
    env_path.write_text("\n".join(lines) + "\n")
    console.print(f"\n[green]✓ Saved to {env_path}[/]")
    console.print("Run [bold]python -m waoiw.run[/] to start the agent.")


if __name__ == "__main__":
    main()
