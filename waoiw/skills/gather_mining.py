"""
skills/gather_mining.py — 采矿 skill
"""
import time
import random

from .base import Skill, SkillContext, SkillResult
from .registry import register


@register
class GatherMining(Skill):
    name = "gather_mining"
    description = (
        "在当前区域循环采集矿石节点。适用于：采矿、挖矿、采矿石、farm矿、挂机采矿等指令。"
        "会在小地图寻找矿点，移动过去采集，循环直到手动停止。"
    )

    def can_handle(self, instruction: str) -> float:
        keywords = ["采矿", "挖矿", "矿石", "mining", "mine", "矿", "farm矿"]
        for kw in keywords:
            if kw.lower() in instruction.lower():
                return 0.9
        return 0.0

    def run(self, ctx: SkillContext) -> SkillResult:
        from waoiw.capture import capture_full
        from waoiw.vision.reader import read_game_state
        from waoiw.brain.states import StateMachine, State, ActionType
        from waoiw.executor.input import move_to, interact, press_key, random_delay
        from waoiw.config import config

        sm = StateMachine()
        gathered = 0
        cycles = 0
        max_cycles = ctx.params.get("max_cycles", 9999)
        log = []

        def emit(msg: str):
            log.append(msg)
            # supervisor panel 会实时显示，这里只记录摘要

        emit(f"🪨 GatherMining 开始 | 指令: {ctx.instruction!r}")

        while not ctx.should_stop() and cycles < max_cycles:
            cycles += 1

            # ── 1. 截图 ────────────────────────────────────────────────────
            frame = capture_full()
            game_state = read_game_state(frame)

            # ── 2. 状态机决策 ──────────────────────────────────────────────
            action = sm.decide(game_state)

            # ── 3. 执行 ────────────────────────────────────────────────────
            if action.type == ActionType.WAIT:
                time.sleep(0.3)

            elif action.type == ActionType.SCAN:
                # 随机小幅转镜头，模拟玩家环顾
                if random.random() < 0.15:
                    key = random.choice(["a", "d"])
                    press_key(key, hold_ms=random.randint(150, 400))
                time.sleep(config.screenshot_interval_ms / 1000.0)

            elif action.type == ActionType.MOVE_TO and action.pos:
                emit(f"→ 移动到节点 {action.pos}")
                move_to(action.pos)

            elif action.type == ActionType.INTERACT:
                emit(f"⛏ 采集节点")
                interact()
                # 等待采集动画完成（2-3秒，随机）
                time.sleep(random.uniform(2.2, 3.5))
                gathered += 1
                emit(f"✓ 已采集 {gathered} 个")
                sm.transition(State.IDLE, "gather done")

            elif action.type == ActionType.FIGHT:
                emit(f"⚔ 遭遇战斗，自动反击")
                press_key("1")
                time.sleep(1.0)

            # 每20个循环给 agent loop 一次汇报机会
            if cycles % 20 == 0:
                return SkillResult(
                    success=True,
                    message=f"采集进行中，已采 {gathered} 个矿，运行 {ctx.elapsed():.0f}s",
                    data={"gathered": gathered, "cycles": cycles},
                    should_continue=True,  # 告诉 agent loop：继续
                )

        return SkillResult(
            success=True,
            message=f"采矿结束，共采集 {gathered} 个矿石，运行 {ctx.elapsed():.0f}s",
            data={"gathered": gathered, "log": log},
            should_continue=False,
        )
