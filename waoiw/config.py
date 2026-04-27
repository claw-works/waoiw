"""
waoiw config — edit this to match your WoW window and UI layout
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Config(BaseSettings):
    # WoW window title (partial match)
    wow_window_title: str = "World of Warcraft"

    # Monitor index (0 = primary)
    monitor_index: int = 1

    # Screenshot region overrides (None = full screen)
    # Format: {"left": x, "top": y, "width": w, "height": h}
    # You'll calibrate these after first run
    region_hp_bar: dict | None = None
    region_mana_bar: dict | None = None
    region_target_frame: dict | None = None
    region_minimap: dict | None = None
    region_action_bar: dict | None = None

    # Timing
    screenshot_interval_ms: int = 500       # how often to grab a frame
    action_delay_min_ms: int = 150          # min delay between actions
    action_delay_max_ms: int = 400          # max delay (randomized)

    # Safety
    max_session_minutes: int = 120          # auto-pause after this long
    pause_key: str = "F12"                  # hotkey to pause agent

    # Paths
    tesseract_cmd: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    screenshots_dir: str = "screenshots"
    templates_dir: str = "templates"

    class Config:
        env_file = ".env"
        env_prefix = "WAOIW_"


config = Config()
