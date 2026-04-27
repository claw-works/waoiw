"""
vision/__init__.py — vision layer
Reads game state from screenshots: HP, mana, cooldowns, gather nodes.
"""
from .reader import read_game_state, GameState

__all__ = ["read_game_state", "GameState"]
