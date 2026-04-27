"""
skills/gather_mining/node_finder.py
小地图矿点检测 + 方向角计算

WoW 小地图上：
  - 矿点 = 黄色小圆点（采矿追踪开启后）
  - 敌对单位 = 红色小点
  - 中心 = 当前角色位置

输出：
  - 矿点相对中心的偏移 (dx, dy)
  - 换算成飞行方向角度（0°=北，顺时针）
  - 是否有红点（敌对单位）在矿点附近
"""
import math
import numpy as np
import cv2
from dataclasses import dataclass
from typing import Optional


@dataclass
class NodeInfo:
    """小地图上检测到的矿点信息"""
    # 矿点在小地图上的像素坐标（相对截图左上角）
    pixel_x: int
    pixel_y: int
    # 相对小地图中心的偏移
    dx: int
    dy: int
    # 飞行方向角（0°=北/上，顺时针，0-360）
    bearing_deg: float
    # 矿点附近是否有红点（敌对单位）
    enemy_nearby: bool = False
    # 置信度 0.0-1.0
    confidence: float = 1.0


# ── HSV 颜色范围 ───────────────────────────────────────────────────────────────
# 这些值需要对着真实截图微调，以下是经验初始值

# 矿点：黄色，相对饱和
MINING_NODE_HSV_LO = np.array([18,  120, 150])
MINING_NODE_HSV_HI = np.array([32,  255, 255])

# 草药节点：绿色（备用）
HERB_NODE_HSV_LO = np.array([40,  80, 100])
HERB_NODE_HSV_HI = np.array([80,  255, 255])

# 敌对单位：红色（两段，红色在HSV里跨0°）
ENEMY_HSV_LO1 = np.array([0,   150, 150])
ENEMY_HSV_HI1 = np.array([8,   255, 255])
ENEMY_HSV_LO2 = np.array([172, 150, 150])
ENEMY_HSV_HI2 = np.array([180, 255, 255])

# 矿点点大小范围（像素面积）
NODE_AREA_MIN = 3
NODE_AREA_MAX = 80

# 敌对单位点大小范围
ENEMY_AREA_MIN = 2
ENEMY_AREA_MAX = 50

# 认为"附近有敌人"的距离（像素）
ENEMY_PROXIMITY_PX = 20


def find_nodes(
    minimap_crop: np.ndarray,
    node_type: str = "mining",
) -> list[NodeInfo]:
    """
    在小地图截图中找所有矿点，返回 NodeInfo 列表（按距中心距离排序）。

    minimap_crop: BGRA 截图，应只包含小地图区域
    node_type: "mining" | "herb"
    """
    h, w = minimap_crop.shape[:2]
    cx, cy = w // 2, h // 2

    # 转 HSV
    bgr = minimap_crop[:, :, :3]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # 选颜色范围
    if node_type == "herb":
        lo, hi = HERB_NODE_HSV_LO, HERB_NODE_HSV_HI
    else:
        lo, hi = MINING_NODE_HSV_LO, MINING_NODE_HSV_HI

    # 生成矿点 mask
    node_mask = cv2.inRange(hsv, lo, hi)

    # 生成敌人 mask（两段红色）
    enemy_mask = cv2.inRange(hsv, ENEMY_HSV_LO1, ENEMY_HSV_HI1)
    enemy_mask |= cv2.inRange(hsv, ENEMY_HSV_LO2, ENEMY_HSV_HI2)

    # 找矿点轮廓
    contours, _ = cv2.findContours(node_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    enemy_contours, _ = cv2.findContours(enemy_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 提取敌人中心点
    enemy_centers = []
    for cnt in enemy_contours:
        area = cv2.contourArea(cnt)
        if ENEMY_AREA_MIN <= area <= ENEMY_AREA_MAX:
            M = cv2.moments(cnt)
            if M["m00"] > 0:
                ex = int(M["m10"] / M["m00"])
                ey = int(M["m01"] / M["m00"])
                enemy_centers.append((ex, ey))

    # 提取矿点
    nodes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if NODE_AREA_MIN <= area <= NODE_AREA_MAX:
            M = cv2.moments(cnt)
            if M["m00"] > 0:
                px = int(M["m10"] / M["m00"])
                py = int(M["m01"] / M["m00"])
                dx = px - cx
                dy = py - cy
                bearing = _offset_to_bearing(dx, dy)

                # 检查附近是否有敌人
                enemy_nearby = any(
                    math.hypot(px - ex, py - ey) < ENEMY_PROXIMITY_PX
                    for ex, ey in enemy_centers
                )

                nodes.append(NodeInfo(
                    pixel_x=px,
                    pixel_y=py,
                    dx=dx,
                    dy=dy,
                    bearing_deg=bearing,
                    enemy_nearby=enemy_nearby,
                    confidence=min(1.0, area / 20.0),  # 面积越大越置信
                ))

    # 按距中心距离排序（最近的优先）
    nodes.sort(key=lambda n: math.hypot(n.dx, n.dy))
    return nodes


def best_node(
    nodes: list[NodeInfo],
    avoid_enemies: bool = True,
) -> Optional[NodeInfo]:
    """
    从检测到的节点中选最佳目标。
    avoid_enemies=True 时跳过有敌人的节点。
    """
    for node in nodes:
        if avoid_enemies and node.enemy_nearby:
            continue
        return node
    # 所有节点都有敌人时，如果不绕开就返回最近的
    if nodes and not avoid_enemies:
        return nodes[0]
    return None


def _offset_to_bearing(dx: int, dy: int) -> float:
    """
    小地图像素偏移 → 飞行方向角（度）
    WoW 小地图：上=北，右=东
    atan2(dx, -dy)：dx正=东，-dy正=北 → 0°=北，顺时针
    """
    angle = math.degrees(math.atan2(dx, -dy))
    return angle % 360


def debug_draw(
    minimap_crop: np.ndarray,
    nodes: list[NodeInfo],
) -> np.ndarray:
    """在小地图上画出检测到的节点（调试用）"""
    out = minimap_crop.copy()
    h, w = out.shape[:2]
    cx, cy = w // 2, h // 2

    # 画中心十字
    cv2.drawMarker(out, (cx, cy), (255, 255, 255), cv2.MARKER_CROSS, 10, 1)

    for node in nodes:
        color = (0, 0, 255) if node.enemy_nearby else (0, 255, 255)  # 红/黄
        cv2.circle(out, (node.pixel_x, node.pixel_y), 5, color, 2)
        cv2.line(out, (cx, cy), (node.pixel_x, node.pixel_y), color, 1)
        label = f"{node.bearing_deg:.0f}°"
        cv2.putText(out, label, (node.pixel_x + 6, node.pixel_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

    return out
