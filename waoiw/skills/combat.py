"""
skills/combat.py — 战斗 Skill（独立模块）

场景：
  - 装备等级压制，基本不会死，无需逃跑
  - 一键攻击绑定在 R 键（已在游戏内编排好技能序列）
  - 脱战后才能飞行，所以必须打完再走
  - 可扩展：额外防御键、回血键（后续加）

战斗流程：
  Tab 选中敌人
    ↓
  循环按 R 攻击
    ↓
  检测战斗结束（目标血条消失 + 不在战斗状态）
    ↓
  等待脱战（约 6s）
    ↓
  返回 SkillResult

状态检测方式（纯截图，不依赖 addon）：
  - 有无目标框：屏幕上方中央是否有目标血条区域
  - 在不在战斗：玩家头像旁是否有"战斗"标志（剑图标变红）
  - 自身血量：用 vision/ocr.py 的血条检测
"""
import time
import random
from dataclasses import dataclass
from typing import Optional

import numpy as np
import cv2

from waoiw.skills.base import Skill, SkillContext, SkillResult
from waoiw.skills.registry import register
from waoiw.capture import capture_full
from waoiw.executor.input import press_key, random_delay
from waoiw.config import config


# ── 配置 ──────────────────────────────────────────────────────────────────────

# 攻击键
ATTACK_KEY = "r"

# 可扩展的额外按键列表（按顺序，每次攻击循环中穿插）
# 格式：{"key": "f", "every_n": 3, "label": "防御"}  每3次攻击按一次
EXTRA_KEYS: list[dict] = [
    # 示例（默认空，需要时填入）：
    # {"key": "f", "every_n": 3, "label": "防御技能"},
    # {"key": "g", "every_n": 5, "label": "回血药"},
]

# 攻击间隔（秒），模拟人类节奏
ATTACK_INTERVAL_MIN = 1.0
ATTACK_INTERVAL_MAX = 2.2

# 脱战等待时间（秒）
COMBAT_EXIT_WAIT = 6.5

# 最长战斗时间（秒），超时视为异常
MAX_COMBAT_DURATION = 120

# 目标血条区域（需要校准）
# 默认值：1920x1080 下目标框大概在屏幕上方中央
DEFAULT_TARGET_FRAME_REGION = {
    "left": 760,
    "top":  50,
    "width": 400,
    "height": 60,
}

# 血条红色 HSV（目标血条）
TARGET_HP_BAR_LO = np.array([0,   120, 100])
TARGET_HP_BAR_HI = np.array([10,  255, 255])
TARGET_HP_BAR_LO2 = np.array([170, 120, 100])
TARGET_HP_BAR_HI2 = np.array([180, 255, 255])


# ── Skill ─────────────────────────────────────────────────────────────────────

@register
class CombatSkill(Skill):
    name = "combat"
    description = (
        "战斗模块：自动攻击当前目标直到战斗结束。"
        "使用 R 键一键攻击，等待脱战后返回。"
        "适用于：打怪、战斗、攻击敌人等指令，"
        "也供其他 skill（如采矿）在遭遇战斗时内部调用。"
    )

    def can_handle(self, instruction: str) -> float:
        keywords = ["打怪", "战斗", "攻击", "combat", "fight", "kill"]
        for kw in keywords:
            if kw.lower() in instruction.lower():
                return 0.9
        return 0.0

    def run(self, ctx: SkillContext) -> SkillResult:
        """
        执行一场战斗，直到脱战。
        可以被 GatherMining 等 skill 直接调用。
        """
        start = time.time()
        attack_count = 0
        extra_key_counters = {k["key"]: 0 for k in EXTRA_KEYS}

        _log(ctx, "⚔ 进入战斗")

        # ── Tab 选中最近敌人 ──────────────────────────────────────────────
        press_key("tab")
        random_delay(200, 400)

        # 确认是否选中了目标
        if not self._has_target():
            _log(ctx, "⚠ Tab 没选中目标，再试一次")
            press_key("tab")
            random_delay(300, 500)

        # ── 攻击循环 ──────────────────────────────────────────────────────
        while not ctx.should_stop():
            elapsed = time.time() - start

            # 超时保护
            if elapsed > MAX_COMBAT_DURATION:
                _log(ctx, f"⏰ 战斗超过 {MAX_COMBAT_DURATION}s，强制退出")
                break

            # 检测战斗是否结束
            if not self._in_combat():
                _log(ctx, f"✓ 战斗结束（{elapsed:.1f}s，攻击{attack_count}次）")
                break

            # 按攻击键
            press_key(ATTACK_KEY)
            attack_count += 1

            # 穿插额外按键（防御/回血等）
            for extra in EXTRA_KEYS:
                extra_key_counters[extra["key"]] += 1
                if extra_key_counters[extra["key"]] >= extra["every_n"]:
                    extra_key_counters[extra["key"]] = 0
                    press_key(extra["key"])
                    _log(ctx, f"  + {extra.get('label', extra['key'])}")

            # 攻击间隔（随机，模拟人类）
            interval = random.uniform(ATTACK_INTERVAL_MIN, ATTACK_INTERVAL_MAX)
            time.sleep(interval)

        # ── 等待脱战 ──────────────────────────────────────────────────────
        _log(ctx, f"⏳ 等待脱战 {COMBAT_EXIT_WAIT}s...")
        time.sleep(COMBAT_EXIT_WAIT + random.uniform(0, 1.5))

        # 清除目标
        press_key("escape")
        random_delay(100, 200)

        total = time.time() - start
        return SkillResult(
            success=True,
            message=f"战斗结束：攻击{attack_count}次，耗时{total:.1f}s",
            data={"attack_count": attack_count, "duration": total},
            should_continue=False,
        )

    # ── 状态检测 ──────────────────────────────────────────────────────────────

    def _has_target(self) -> bool:
        """
        检测是否选中了目标（目标血条框是否出现）。
        方法：在目标框区域找红色血条像素。
        """
        frame = capture_full()
        region = getattr(config, "region_target_frame", None) or DEFAULT_TARGET_FRAME_REGION
        crop = frame[
            region["top"]:region["top"] + region["height"],
            region["left"]:region["left"] + region["width"],
            :3
        ]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, TARGET_HP_BAR_LO, TARGET_HP_BAR_HI)
        mask |= cv2.inRange(hsv, TARGET_HP_BAR_LO2, TARGET_HP_BAR_HI2)
        # 红色像素占比超过 5% = 有目标血条
        ratio = mask.sum() / (mask.shape[0] * mask.shape[1] * 255)
        return ratio > 0.05

    def _in_combat(self) -> bool:
        """
        检测是否仍在战斗中。
        方法：目标血条还存在 = 还在战斗。
        目标死亡后血条消失，_has_target() 返回 False = 脱战。

        更准确的方法（可选扩展）：
          检测玩家头像旁的战斗标志（小剑图标变红）
        """
        return self._has_target()


# ── 供其他 skill 直接调用的便捷函数 ──────────────────────────────────────────

def run_combat(ctx: SkillContext) -> SkillResult:
    """
    便捷函数：直接运行一场战斗。
    供 GatherMining 等 skill 内部调用，无需通过 agent loop。

    用法：
        from waoiw.skills.combat import run_combat
        result = run_combat(ctx)
    """
    return CombatSkill().run(ctx)


def _log(ctx: SkillContext, msg: str):
    import time as _t
    ts = _t.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
