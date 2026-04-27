"""
vision/reader.py — extract game state from a screenshot frame
"""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from .ocr import read_bar_value
from .matcher import find_template, is_cooldown_active


@dataclass
class GameState:
    hp_pct: Optional[float] = None          # 0.0 - 1.0
    mana_pct: Optional[float] = None        # 0.0 - 1.0
    target_hp_pct: Optional[float] = None
    in_combat: bool = False
    gather_node_visible: bool = False
    gather_node_pos: Optional[tuple] = None  # (x, y) screen coords
    skills_on_cd: list[int] = field(default_factory=list)  # slot indices
    raw_frame: Optional[np.ndarray] = None

    def __str__(self):
        parts = []
        if self.hp_pct is not None:
            parts.append(f"HP:{self.hp_pct*100:.0f}%")
        if self.mana_pct is not None:
            parts.append(f"MP:{self.mana_pct*100:.0f}%")
        if self.gather_node_visible:
            parts.append(f"NODE@{self.gather_node_pos}")
        if self.in_combat:
            parts.append("⚔COMBAT")
        return " | ".join(parts) if parts else "unknown"


def read_game_state(frame: np.ndarray) -> GameState:
    """
    Given a full-screen BGRA frame, extract the current game state.
    Returns a GameState dataclass.

    NOTE: Region coordinates need calibration for your specific
    WoW resolution and UI scale. Run the calibration tool first:
        python -m waoiw.tools.calibrate
    """
    from waoiw.config import config

    state = GameState(raw_frame=frame)

    # HP bar
    if config.region_hp_bar:
        state.hp_pct = read_bar_value(frame, config.region_hp_bar, color="green")

    # Mana bar
    if config.region_mana_bar:
        state.mana_pct = read_bar_value(frame, config.region_mana_bar, color="blue")

    # Gather node detection (minimap)
    if config.region_minimap:
        from .minimap import find_gather_node
        node = find_gather_node(frame, config.region_minimap)
        if node:
            state.gather_node_visible = True
            state.gather_node_pos = node

    return state
