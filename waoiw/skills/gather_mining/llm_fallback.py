"""
skills/gather_mining/llm_fallback.py
多模态 LLM 兜底推理

当 OpenCV 本地方案搞不定时（找不到矿点、定位失败、遇到异常画面），
截图发给 Claude Vision 让它看图说话，给出下一步行动建议。

设计原则：
  - 这是兜底，不是主路径，调用要少
  - 每次调用约 1-3 秒，完全可以接受
  - 提示词要具体，让 LLM 输出结构化决策
"""
import base64
import json
from typing import Optional
from dataclasses import dataclass

import numpy as np
import cv2
from anthropic import Anthropic

client = Anthropic()

# ── 决策结构 ──────────────────────────────────────────────────────────────────

@dataclass
class LLMDecision:
    action: str             # "fly_to", "gather", "wait", "open_map", "unknown"
    bearing_deg: float      # 建议飞行方向（action=fly_to 时有效）
    reasoning: str          # LLM 的推理说明
    confidence: float       # 0.0-1.0


FALLBACK_PROMPT = """你是一个 World of Warcraft 飞行采矿助手。
我会给你当前游戏截图，你来判断下一步该怎么做。

当前状态：{context}

请观察截图，回答以下问题，并以 JSON 格式输出：
1. 小地图上有没有黄色矿点？在哪个方向？
2. 屏幕上是否有可以交互的矿石节点（发光的石头）？
3. 角色当前状态（在飞行中？落地了？在采集？）

输出格式（只输出 JSON）：
{
  "action": "fly_to" | "gather" | "wait" | "open_map" | "unknown",
  "bearing_deg": 0-360,
  "reasoning": "简短说明",
  "confidence": 0.0-1.0
}

action 说明：
- fly_to: 往 bearing_deg 方向飞
- gather: 当前位置可以采集，右键交互
- wait: 等待（采集动画进行中）
- open_map: 打开大地图看位置
- unknown: 无法判断
"""


def ask_llm(
    frame: np.ndarray,
    context: str = "正在寻找矿点",
    regions: Optional[list[dict]] = None,
) -> LLMDecision:
    """
    把截图（或指定区域）发给 Claude Vision，获取行动建议。

    frame: 全屏 BGRA numpy array
    context: 当前状态描述，帮助 LLM 聚焦
    regions: 要裁剪并发送的区域列表（可选，None=发全屏）
    """
    # 准备图片
    if regions:
        # 拼接多个区域截图
        crops = []
        for r in regions:
            crop = frame[
                r["top"]:r["top"] + r["height"],
                r["left"]:r["left"] + r["width"],
                :3
            ]
            # 缩小一半（节省 token）
            crop = cv2.resize(crop, None, fx=0.5, fy=0.5)
            crops.append(crop)
        # 横向拼接
        img = np.hstack(crops) if len(crops) > 1 else crops[0]
    else:
        # 全屏缩到 1280 宽（够 LLM 看清）
        h, w = frame.shape[:2]
        scale = min(1.0, 1280 / w)
        img = cv2.resize(frame[:, :, :3], None, fx=scale, fy=scale)

    # 编码为 base64 PNG
    _, buf = cv2.imencode(".png", img)
    img_b64 = base64.standard_b64encode(buf.tobytes()).decode()

    # 调用 Claude
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": FALLBACK_PROMPT.format(context=context),
                    },
                ],
            }
        ],
    )

    text = response.content[0].text.strip()

    # 解析 JSON
    try:
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        return LLMDecision(
            action=data.get("action", "unknown"),
            bearing_deg=float(data.get("bearing_deg", 0)),
            reasoning=data.get("reasoning", ""),
            confidence=float(data.get("confidence", 0.5)),
        )
    except Exception as e:
        return LLMDecision(
            action="unknown",
            bearing_deg=0,
            reasoning=f"解析失败: {e} | 原文: {text[:100]}",
            confidence=0.0,
        )
