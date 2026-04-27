"""
skills/gather_mining/flight.py
飞行控制模块

WoW 飞行操作：
  Z         — 起飞/降落切换（坐骑飞行）
  W         — 向前飞
  鼠标右键拖拽 — 转向（转摄像机=转角色朝向）
  Space     — 向上
  X         — 向下（下降）

转向策略：
  用右键拖拽鼠标来转向，比直接按 A/D 更精确，
  可以对齐到任意角度而不是固定转速。
"""
import time
import math
import random

import pydirectinput

from waoiw.executor.input import random_delay, press_key


# ── 常量 ──────────────────────────────────────────────────────────────────────

# 每像素对应的转向角度（需要实测校准）
# WoW 默认鼠标灵敏度下，大约 3-5 px/度
PIXELS_PER_DEGREE = 4.0

# 飞行巡逻单次持续时间（秒）
DEFAULT_FLY_DURATION = 5.0

# 起飞后等待爬升的时间
TAKEOFF_SETTLE_S = 1.2

# 降落后等待落地动画
LANDING_SETTLE_S = 0.8

# 采集交互后等待动画完成
GATHER_ANIMATION_S = (2.0, 3.5)  # min, max


# ── 飞行控制 ──────────────────────────────────────────────────────────────────

def takeoff():
    """起飞"""
    press_key("z")
    time.sleep(TAKEOFF_SETTLE_S + random.uniform(0, 0.3))


def land():
    """降落"""
    press_key("z")
    time.sleep(LANDING_SETTLE_S + random.uniform(0, 0.2))


def fly_forward(duration: float):
    """向前飞行指定秒数"""
    pydirectinput.keyDown("w")
    time.sleep(duration + random.uniform(-0.2, 0.2))
    pydirectinput.keyUp("w")


def turn_to_bearing(target_bearing: float, current_bearing: float):
    """
    转向目标角度。
    通过右键拖拽鼠标实现精确转向。

    target_bearing: 目标方向（0-360，0=北）
    current_bearing: 当前朝向（0-360）
    """
    # 计算最短转向角（-180 ~ +180）
    delta = (target_bearing - current_bearing + 180) % 360 - 180

    if abs(delta) < 5:
        return  # 偏差很小，不转

    # 转换为像素偏移
    pixels = int(delta * PIXELS_PER_DEGREE)

    # 在屏幕中间按住右键拖拽
    sw, sh = _screen_center()
    pydirectinput.moveTo(sw, sh)
    time.sleep(0.05)
    pydirectinput.mouseDown(button="right")
    time.sleep(random.uniform(0.05, 0.1))

    # 分多步拖拽（更像人类）
    steps = max(3, abs(pixels) // 20)
    step_px = pixels / steps
    for _ in range(steps):
        cur_x, _ = pydirectinput.position()
        pydirectinput.moveTo(int(cur_x + step_px), sh)
        time.sleep(random.uniform(0.01, 0.025))

    pydirectinput.mouseUp(button="right")
    time.sleep(random.uniform(0.1, 0.2))


def fly_to_bearing(
    bearing: float,
    current_bearing: float,
    duration: float = DEFAULT_FLY_DURATION,
    jitter_deg: float = 12.0,
):
    """
    转向目标方向，加随机抖动，然后向前飞 duration 秒。

    jitter_deg: 随机偏差范围（±度），模拟人类不精确操作
    """
    # 加随机角度偏差
    actual_bearing = bearing + random.uniform(-jitter_deg, jitter_deg)
    actual_bearing %= 360

    turn_to_bearing(actual_bearing, current_bearing)
    time.sleep(random.uniform(0.2, 0.4))  # 转完稍等一下再飞

    fly_forward(duration)

    # 返回实际飞行方向（供外部更新 current_bearing）
    return actual_bearing


def descend_and_interact():
    """
    下降到矿点高度并交互采集。
    策略：按 X 键下降 + 右键点击矿点
    实际矿点交互靠 Tab 选中 + 右键，或者直接对准右键
    """
    # 先降落一段
    pydirectinput.keyDown("x")
    time.sleep(random.uniform(1.0, 1.8))
    pydirectinput.keyUp("x")
    time.sleep(0.3)

    # 尝试 Tab 选中最近目标
    press_key("tab")
    time.sleep(0.2)

    # 右键交互
    pydirectinput.rightClick()
    time.sleep(random.uniform(*GATHER_ANIMATION_S))


def explore_direction(current_bearing: float) -> float:
    """
    当找不到矿点时，决定探索方向。
    策略：在当前方向基础上偏转 60-120°，避免原路返回。
    """
    offset = random.choice([-1, 1]) * random.uniform(60, 120)
    return (current_bearing + offset) % 360


# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _screen_center() -> tuple[int, int]:
    """返回屏幕中心坐标"""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()
    root.destroy()
    return w // 2, h // 2
