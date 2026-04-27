"""
skills/gather_mining/map_reader.py
大地图读取：定位角色当前位置，辅助决定探索方向

WoW 大地图操作：
  M 键 — 打开/关闭大地图
  大地图上角色位置 = 一个小箭头图标

用途：
  当小地图找不到矿点时，打开大地图看角色在哪个区域，
  判断应该往哪个方向飞去探索新区域。
"""
import time
import random
import numpy as np
import cv2
from dataclasses import dataclass
from typing import Optional

from waoiw.executor.input import press_key
from waoiw.capture import capture_full


@dataclass
class MapPosition:
    """角色在大地图上的位置信息"""
    # 角色箭头在截图中的像素坐标
    pixel_x: int
    pixel_y: int
    # 相对大地图区域的归一化坐标（0.0-1.0）
    norm_x: float
    norm_y: float
    # 箭头朝向角（0°=北，顺时针）—— 可选，不一定能检测到
    facing_deg: Optional[float] = None


# ── 大地图区域配置（需要校准）─────────────────────────────────────────────────
# 大地图打开后的屏幕区域，格式 {left, top, width, height}
# 默认值是 1920x1080 全屏的大概位置，需要实测
DEFAULT_MAP_REGION = {
    "left": 200,
    "top": 100,
    "width": 1500,
    "height": 900,
}

# 角色箭头的颜色（绿色箭头）
PLAYER_ARROW_HSV_LO = np.array([40,  100, 150])
PLAYER_ARROW_HSV_HI = np.array([80,  255, 255])

# 箭头面积范围
ARROW_AREA_MIN = 20
ARROW_AREA_MAX = 300


def open_map() -> None:
    """打开大地图"""
    press_key("m")
    time.sleep(0.6 + random.uniform(0, 0.2))  # 等待地图加载


def close_map() -> None:
    """关闭大地图"""
    press_key("m")
    time.sleep(0.3)


def read_player_position(
    map_region: dict | None = None,
) -> Optional[MapPosition]:
    """
    截取大地图区域，找到角色箭头，返回位置信息。
    map_region: 大地图在屏幕上的区域，None 时用默认值
    """
    region = map_region or DEFAULT_MAP_REGION
    frame = capture_full()
    crop = frame[
        region["top"]:region["top"] + region["height"],
        region["left"]:region["left"] + region["width"],
        :3
    ]

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, PLAYER_ARROW_HSV_LO, PLAYER_ARROW_HSV_HI)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_cnt = None
    best_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if ARROW_AREA_MIN <= area <= ARROW_AREA_MAX and area > best_area:
            best_area = area
            best_cnt = cnt

    if best_cnt is None:
        return None

    M = cv2.moments(best_cnt)
    if M["m00"] == 0:
        return None

    px = int(M["m10"] / M["m00"])
    py = int(M["m01"] / M["m00"])

    h, w = crop.shape[:2]
    norm_x = px / w
    norm_y = py / h

    # 尝试从轮廓形状推断箭头朝向（粗略）
    facing = _estimate_arrow_facing(best_cnt)

    return MapPosition(
        pixel_x=px + region["left"],
        pixel_y=py + region["top"],
        norm_x=norm_x,
        norm_y=norm_y,
        facing_deg=facing,
    )


def suggest_explore_direction(pos: MapPosition) -> float:
    """
    根据角色在地图的位置，建议探索方向。
    简单策略：偏向地图未探索的一侧（远离边缘）。

    pos.norm_x/y: 0=左/上，1=右/下
    返回建议飞行方向角（0°=北，顺时针）
    """
    # 往地图中心方向飞
    dx = 0.5 - pos.norm_x   # 正=往右(东)
    dy = 0.5 - pos.norm_y   # 正=往下(南)，地图 y 轴朝下

    import math
    # 转成方位角（北=0，顺时针）
    bearing = math.degrees(math.atan2(dx, -dy)) % 360

    # 加随机偏差
    bearing += random.uniform(-30, 30)
    return bearing % 360


def _estimate_arrow_facing(contour: np.ndarray) -> Optional[float]:
    """
    从箭头轮廓估计朝向角。
    用 PCA 找主轴方向，但精度有限。
    仅供参考，不作为关键决策依据。
    """
    try:
        pts = contour.reshape(-1, 2).astype(np.float32)
        mean, eigenvectors = cv2.PCACompute(pts, mean=None)
        angle = np.degrees(np.arctan2(eigenvectors[0, 1], eigenvectors[0, 0]))
        return float(angle % 360)
    except Exception:
        return None
