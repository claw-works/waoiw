"""
capture.py — screenshot module
Grabs WoW window frames as fast as possible using mss.
"""
import sys
import time
from pathlib import Path
from datetime import datetime

import mss
import mss.tools
import numpy as np
from PIL import Image

from waoiw.config import config


def get_monitor() -> dict:
    """Return the monitor dict for the configured monitor index."""
    with mss.mss() as sct:
        return sct.monitors[config.monitor_index]


def capture_full() -> np.ndarray:
    """Capture the full monitor, return as numpy array (BGR)."""
    with mss.mss() as sct:
        monitor = sct.monitors[config.monitor_index]
        raw = sct.grab(monitor)
        img = np.array(raw)
        return img  # BGRA


def capture_region(region: dict) -> np.ndarray:
    """Capture a specific region. region = {left, top, width, height}"""
    with mss.mss() as sct:
        raw = sct.grab(region)
        return np.array(raw)  # BGRA


def save_screenshot(img: np.ndarray, tag: str = "") -> Path:
    """Save a screenshot to the screenshots dir for debugging."""
    out_dir = Path(config.screenshots_dir)
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    fname = out_dir / f"{ts}_{tag}.png" if tag else out_dir / f"{ts}.png"
    Image.fromarray(img).save(fname)
    return fname


def bgra_to_rgb(img: np.ndarray) -> np.ndarray:
    """Convert BGRA numpy array to RGB."""
    return img[:, :, [2, 1, 0]]


def bgra_to_gray(img: np.ndarray) -> np.ndarray:
    """Convert BGRA to grayscale."""
    import cv2
    return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("📸 Capture test — taking screenshot in 3 seconds...")
    time.sleep(3)

    img = capture_full()
    path = save_screenshot(img, "test")
    print(f"✅ Saved to: {path}")
    print(f"   Shape: {img.shape}  dtype: {img.dtype}")
    print(f"   Monitor: {get_monitor()}")
