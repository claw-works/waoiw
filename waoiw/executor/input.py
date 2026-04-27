"""
executor/input.py — simulate human-like keyboard and mouse input

Uses pydirectinput for DirectInput-compatible key events (works with WoW).
All timings are randomized to avoid bot-detection patterns.
"""
import time
import random
import math

import pydirectinput

from waoiw.config import config


def random_delay(min_ms: int | None = None, max_ms: int | None = None) -> None:
    """Sleep for a random duration between min and max milliseconds."""
    lo = min_ms if min_ms is not None else config.action_delay_min_ms
    hi = max_ms if max_ms is not None else config.action_delay_max_ms
    time.sleep(random.randint(lo, hi) / 1000.0)


def move_mouse_smooth(target_x: int, target_y: int, steps: int = 20) -> None:
    """
    Move mouse to target in a slightly curved path (not a straight line).
    Much more human-like than instant jumps.
    """
    cur_x, cur_y = pydirectinput.position()

    # Add a small random arc
    arc_x = random.randint(-30, 30)
    arc_y = random.randint(-30, 30)

    for i in range(1, steps + 1):
        t = i / steps
        # Cubic ease-in-out
        t_eased = 3 * t**2 - 2 * t**3
        # Arc diminishes toward end
        arc_factor = math.sin(math.pi * t)
        x = int(cur_x + (target_x - cur_x) * t_eased + arc_x * arc_factor)
        y = int(cur_y + (target_y - cur_y) * t_eased + arc_y * arc_factor)
        pydirectinput.moveTo(x, y)
        time.sleep(random.uniform(0.005, 0.015))


def move_to(pos: tuple) -> None:
    """Move mouse to (x, y) and click to navigate."""
    x, y = pos
    # Add tiny random offset so we don't click the exact same pixel every time
    jitter_x = random.randint(-3, 3)
    jitter_y = random.randint(-3, 3)
    move_mouse_smooth(x + jitter_x, y + jitter_y)
    random_delay(50, 120)
    pydirectinput.rightClick()  # WoW uses right-click to move
    random_delay()


def interact() -> None:
    """Right-click to interact with the target node."""
    random_delay(100, 250)
    pydirectinput.rightClick()
    random_delay()


def press_key(key: str, hold_ms: int | None = None) -> None:
    """Press a key with optional hold duration."""
    pydirectinput.keyDown(key)
    hold = hold_ms if hold_ms is not None else random.randint(
        config.action_delay_min_ms,
        config.action_delay_max_ms
    )
    time.sleep(hold / 1000.0)
    pydirectinput.keyUp(key)
    random_delay()


def click_at(x: int, y: int, button: str = "left") -> None:
    """Click at screen coordinates."""
    move_mouse_smooth(x, y)
    random_delay(50, 120)
    if button == "left":
        pydirectinput.click()
    else:
        pydirectinput.rightClick()
    random_delay()
