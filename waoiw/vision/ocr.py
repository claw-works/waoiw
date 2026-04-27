"""
vision/ocr.py — read numeric values from bar regions using pytesseract
"""
import re
import numpy as np
import cv2
import pytesseract

from waoiw.config import config

# Point tesseract at the right binary on Windows
pytesseract.pytesseract.tesseract_cmd = config.tesseract_cmd


def crop_region(frame: np.ndarray, region: dict) -> np.ndarray:
    """Crop a region dict {left, top, width, height} from a full frame."""
    x, y = region["left"], region["top"]
    w, h = region["width"], region["height"]
    return frame[y:y+h, x:x+w]


def read_bar_value(frame: np.ndarray, region: dict, color: str = "green") -> float | None:
    """
    Estimate a bar percentage by measuring filled pixels in the region.
    color: "green" (HP), "blue" (mana), "yellow" (energy)
    Returns 0.0 - 1.0 or None if detection fails.
    """
    crop = crop_region(frame, region)
    hsv = cv2.cvtColor(crop[:, :, :3], cv2.COLOR_BGR2HSV)

    # HSV ranges for WoW default UI bars
    ranges = {
        "green":  ([40,  50,  50], [85,  255, 255]),
        "blue":   ([100, 50,  50], [140, 255, 255]),
        "yellow": ([20,  50,  50], [35,  255, 255]),
        "red":    ([0,   50,  50], [10,  255, 255]),
    }

    if color not in ranges:
        return None

    lo, hi = [np.array(v) for v in ranges[color]]
    mask = cv2.inRange(hsv, lo, hi)

    # Count filled columns (left → right = 0% → 100%)
    col_sums = mask.sum(axis=0)
    threshold = mask.shape[0] * 0.2  # at least 20% of bar height must match
    filled_cols = (col_sums > threshold).sum()
    total_cols = mask.shape[1]

    if total_cols == 0:
        return None

    return round(filled_cols / total_cols, 3)


def read_text_in_region(frame: np.ndarray, region: dict) -> str:
    """
    OCR a region and return the raw text string.
    Useful for reading numeric values like "23456 / 45000"
    """
    crop = crop_region(frame, region)
    gray = cv2.cvtColor(crop[:, :, :3], cv2.COLOR_BGR2GRAY)
    # Upscale for better OCR accuracy
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    # Threshold
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(
        thresh,
        config="--psm 7 -c tessedit_char_whitelist=0123456789/%, "
    )
    return text.strip()


def parse_fraction(text: str) -> tuple[int, int] | None:
    """Parse '23456 / 45000' → (23456, 45000)"""
    m = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None
