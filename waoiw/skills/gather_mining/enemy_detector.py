"""
skills/gather_mining/enemy_detector.py
降落后检测屏幕上的敌对单位

WoW 中敌对单位头顶有红色血条，友好/中立单位是绿色或黄色。
策略：降落后先不采，截图扫描屏幕中央区域，
     发现红色血条 → 重新起飞跳过这个矿点。

检测目标：
  - 红色横条（敌对单位血条）
  - 排除 UI 元素（玩家自己的血条在屏幕边缘，不在中央）
"""
import numpy as np
import cv2
from dataclasses import dataclass


@dataclass
class EnemyDetectResult:
    has_enemy: bool
    count: int              # 检测到的红色血条数量
    confidence: float       # 0.0-1.0


# ── HSV 颜色范围 ───────────────────────────────────────────────────────────────
# 敌对单位血条：鲜红色，饱和度高
# HSV 红色跨越 0°，分两段
ENEMY_BAR_HSV_LO1 = np.array([0,   160, 120])
ENEMY_BAR_HSV_HI1 = np.array([8,   255, 255])
ENEMY_BAR_HSV_LO2 = np.array([172, 160, 120])
ENEMY_BAR_HSV_HI2 = np.array([180, 255, 255])

# 血条形状过滤：宽度远大于高度（横条）
BAR_MIN_WIDTH  = 20     # 像素
BAR_MAX_HEIGHT = 12     # 像素（血条很薄）
BAR_ASPECT_MIN = 3.0    # 宽/高 最小比例

# 检测置信度阈值
CONFIDENCE_THRESHOLD = 0.5


def detect_enemies(
    frame: np.ndarray,
    scan_region_ratio: float = 0.6,
) -> EnemyDetectResult:
    """
    在屏幕中央区域检测红色血条。

    frame: 全屏 BGRA numpy array
    scan_region_ratio: 扫描区域占屏幕的比例（中央部分，排除 UI 边框）
                       0.6 = 中央 60% 区域
    """
    h, w = frame.shape[:2]

    # 取中央区域，排除边缘 UI
    margin_x = int(w * (1 - scan_region_ratio) / 2)
    margin_y = int(h * (1 - scan_region_ratio) / 2)
    roi = frame[margin_y:h - margin_y, margin_x:w - margin_x, :3]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # 红色 mask（两段合并）
    mask = cv2.inRange(hsv, ENEMY_BAR_HSV_LO1, ENEMY_BAR_HSV_HI1)
    mask |= cv2.inRange(hsv, ENEMY_BAR_HSV_LO2, ENEMY_BAR_HSV_HI2)

    # 形态学处理：连接相邻像素，填充小空洞
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 2))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # 找轮廓
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bars = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        # 过滤：必须是横条形状
        if cw >= BAR_MIN_WIDTH and ch <= BAR_MAX_HEIGHT and cw / max(ch, 1) >= BAR_ASPECT_MIN:
            area = cv2.contourArea(cnt)
            fill_ratio = area / (cw * ch) if cw * ch > 0 else 0
            # 填充率够高才算（排除噪点）
            if fill_ratio > 0.4:
                bars.append((x, y, cw, ch, fill_ratio))

    count = len(bars)
    if count == 0:
        return EnemyDetectResult(has_enemy=False, count=0, confidence=0.9)

    # 置信度：bar 越多、形状越好，置信度越高
    avg_fill = sum(b[4] for b in bars) / count
    confidence = min(1.0, 0.5 + avg_fill * 0.3 + min(count, 3) * 0.1)

    return EnemyDetectResult(
        has_enemy=confidence >= CONFIDENCE_THRESHOLD,
        count=count,
        confidence=confidence,
    )


def debug_draw(
    frame: np.ndarray,
    result: EnemyDetectResult,
    scan_region_ratio: float = 0.6,
) -> np.ndarray:
    """在截图上标注检测结果（调试用）"""
    out = frame.copy()
    h, w = out.shape[:2]
    margin_x = int(w * (1 - scan_region_ratio) / 2)
    margin_y = int(h * (1 - scan_region_ratio) / 2)

    # 画扫描区域边框
    color = (0, 0, 255) if result.has_enemy else (0, 255, 0)
    cv2.rectangle(out,
                  (margin_x, margin_y),
                  (w - margin_x, h - margin_y),
                  color, 2)

    label = f"{'ENEMY' if result.has_enemy else 'CLEAR'} x{result.count} ({result.confidence:.2f})"
    cv2.putText(out, label, (margin_x + 5, margin_y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    return out
