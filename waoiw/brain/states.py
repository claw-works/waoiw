"""
brain/states.py — gather bot state machine

States:
  IDLE        → scanning for nodes
  MOVING      → walking toward a detected node
  GATHERING   → interacting with node
  COMBAT      → in combat, handle threat
  PAUSED      → human took over / pause key pressed
"""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional
import time

from waoiw.vision.reader import GameState


class State(Enum):
    IDLE = auto()
    MOVING = auto()
    GATHERING = auto()
    COMBAT = auto()
    PAUSED = auto()


@dataclass
class StateMachine:
    state: State = State.IDLE
    target_pos: Optional[tuple] = None
    state_entered_at: float = field(default_factory=time.time)
    gather_attempts: int = 0
    last_node_pos: Optional[tuple] = None

    def transition(self, new_state: State, reason: str = "") -> None:
        if new_state != self.state:
            self.state = new_state
            self.state_entered_at = time.time()
            if reason:
                pass  # supervisor will log this

    def time_in_state(self) -> float:
        return time.time() - self.state_entered_at

    def decide(self, game_state: GameState) -> "Action":
        """
        Given the current game state, return the next action to take.
        """
        # Safety: always check combat first
        if game_state.in_combat and self.state != State.PAUSED:
            self.transition(State.COMBAT, "entered combat")
            return Action(ActionType.FIGHT)

        if self.state == State.PAUSED:
            return Action(ActionType.WAIT)

        if self.state == State.COMBAT:
            if not game_state.in_combat:
                self.transition(State.IDLE, "combat ended")
            else:
                return Action(ActionType.FIGHT)

        if self.state == State.IDLE:
            if game_state.gather_node_visible and game_state.gather_node_pos:
                self.target_pos = game_state.gather_node_pos
                self.transition(State.MOVING, f"node found @ {self.target_pos}")
                return Action(ActionType.MOVE_TO, pos=self.target_pos)
            return Action(ActionType.SCAN)

        if self.state == State.MOVING:
            if not game_state.gather_node_visible:
                # Lost the node
                self.transition(State.IDLE, "lost node")
                return Action(ActionType.SCAN)
            # Check if we're close enough (minimap dot near center)
            if self._node_is_close(game_state.gather_node_pos):
                self.transition(State.GATHERING, "close enough to node")
                return Action(ActionType.INTERACT)
            return Action(ActionType.MOVE_TO, pos=game_state.gather_node_pos)

        if self.state == State.GATHERING:
            self.gather_attempts += 1
            if self.time_in_state() > 8.0:
                # Gathering took too long, give up and move on
                self.last_node_pos = self.target_pos
                self.transition(State.IDLE, "gather timeout")
                return Action(ActionType.SCAN)
            return Action(ActionType.WAIT)

        return Action(ActionType.WAIT)

    def _node_is_close(self, pos: Optional[tuple]) -> bool:
        """
        Check if the node dot is near the minimap center (= we're close in-game).
        This is a rough heuristic — refine after calibration.
        """
        if pos is None:
            return False
        from waoiw.config import config
        if not config.region_minimap:
            return False
        mm = config.region_minimap
        cx = mm["left"] + mm["width"] // 2
        cy = mm["top"] + mm["height"] // 2
        dist = ((pos[0] - cx) ** 2 + (pos[1] - cy) ** 2) ** 0.5
        return dist < 10  # pixels — tune this


class ActionType(Enum):
    WAIT = auto()
    SCAN = auto()
    MOVE_TO = auto()
    INTERACT = auto()
    FIGHT = auto()


@dataclass
class Action:
    type: ActionType
    pos: Optional[tuple] = None

    def __str__(self):
        if self.pos:
            return f"{self.type.name} → {self.pos}"
        return self.type.name
