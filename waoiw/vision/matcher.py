"""
vision/matcher.py — template matching for skill icons, gather nodes, etc.
"""
from pathlib import Path
import numpy as np
import cv2

from waoiw.config import config

TEMPLATES_DIR = Path(config.templates_dir)


def load_template(name: str) -> np.ndarray | None:
    """Load a template image by name (without extension)."""
    for ext in [".png", ".jpg"]:
        path = TEMPLATES_DIR / f"{name}{ext}"
        if path.exists():
            return cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    return None


def find_template(
    frame: np.ndarray,
    template_name: str,
    threshold: float = 0.8,
    region: dict | None = None,
) -> tuple[int, int] | None:
    """
    Find a template in the frame using normalized cross-correlation.
    Returns (x, y) center of best match, or None if not found.
    """
    tmpl = load_template(template_name)
    if tmpl is None:
        return None

    search = frame
    offset_x, offset_y = 0, 0

    if region:
        x, y = region["left"], region["top"]
        w, h = region["width"], region["height"]
        search = frame[y:y+h, x:x+w]
        offset_x, offset_y = x, y

    # Convert to BGR for matching
    s = search[:, :, :3]
    t = tmpl[:, :, :3] if tmpl.ndim == 3 and tmpl.shape[2] >= 3 else tmpl

    if t.shape[0] > s.shape[0] or t.shape[1] > s.shape[1]:
        return None  # template larger than search area

    result = cv2.matchTemplate(s, t, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < threshold:
        return None

    # Center of the match
    cx = offset_x + max_loc[0] + t.shape[1] // 2
    cy = offset_y + max_loc[1] + t.shape[0] // 2
    return (cx, cy)


def is_cooldown_active(frame: np.ndarray, slot_region: dict) -> bool:
    """
    Detect if a skill slot has an active cooldown overlay (dark/greyed out).
    Returns True if on cooldown.
    """
    crop = frame[
        slot_region["top"]:slot_region["top"] + slot_region["height"],
        slot_region["left"]:slot_region["left"] + slot_region["width"],
    ]
    gray = cv2.cvtColor(crop[:, :, :3], cv2.COLOR_BGR2GRAY)
    avg_brightness = float(gray.mean())
    # If avg brightness < 80, the icon is dark = on cooldown
    return avg_brightness < 80
