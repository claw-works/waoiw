"""
vision/minimap.py — detect gather nodes on the WoW minimap
"""
import numpy as np
import cv2


# WoW minimap gather node dot colors (HSV)
# Herb nodes: yellow-ish dot
# Mining nodes: grey/silver dot
# These need fine-tuning per your UI settings
NODE_COLORS = {
    "herb":   {"lo": [20,  80,  150], "hi": [35,  255, 255]},
    "mining": {"lo": [0,   0,   160], "hi": [180, 30,  255]},
}


def find_gather_node(
    frame: np.ndarray,
    region: dict,
    node_type: str = "mining",
) -> tuple[int, int] | None:
    """
    Scan the minimap region for a gather node dot.
    Returns (x, y) screen coordinates of the node, or None.
    """
    x0, y0 = region["left"], region["top"]
    w, h = region["width"], region["height"]
    crop = frame[y0:y0+h, x0:x0+w]

    hsv = cv2.cvtColor(crop[:, :, :3], cv2.COLOR_BGR2HSV)

    colors = NODE_COLORS.get(node_type, NODE_COLORS["mining"])
    lo = np.array(colors["lo"])
    hi = np.array(colors["hi"])

    mask = cv2.inRange(hsv, lo, hi)

    # Find contours (node dots)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 4 < area < 200:  # node dots are small
            if area > best_area:
                best_area = area
                M = cv2.moments(cnt)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"]) + x0
                    cy = int(M["m01"] / M["m00"]) + y0
                    best = (cx, cy)

    return best
