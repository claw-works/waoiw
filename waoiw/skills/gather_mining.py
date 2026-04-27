"""
skills/gather_mining.py — 飞行采矿主 Skill（重写版）

主循环逻辑：
  起飞
  loop:
    截图小地图
    OpenCV 找矿点
    ├─ 找到 + 无敌人 → 转向飞过去 → 降落采集
    ├─ 找到 + 有敌人 → 跳过，换下一个
    └─ 没找到 → 打开大地图定位
                ├─ 定位成功 → 推算探索方向 → 继续飞
                └─ 定位失败 → LLM 看图兜底
  每次飞行 5s，加随机方向扰动
"""
import time
import random

from waoiw.skills.base import Skill, SkillContext, SkillResult
from waoiw.skills.registry import register
from waoiw.capture import capture_full, crop_region
from waoiw.config import config

from waoiw.skills.gather_mining.node_finder import find_nodes, best_node
from waoiw.skills.gather_mining.enemy_detector import detect_enemies
from waoiw.skills.gather_mining.flight import (
    takeoff, land, fly_to_bearing, descend_and_interact, explore_direction,
    DEFAULT_FLY_DURATION,
)
from waoiw.skills.gather_mining.map_reader import (
    open_map, close_map, read_player_position, suggest_explore_direction,
)
from waoiw.skills.gather_mining.llm_fallback import ask_llm


@register
class GatherMining(Skill):
    name = "gather_mining"
    description = (
        "飞行巡逻采集矿石节点。开启坐骑飞行，在小地图上寻找黄色矿点，"
        "飞过去采集，找不到时打开大地图决定探索方向，循环直到手动停止。"
        "遇到有敌人守卫的矿点自动绕开。"
        "适用于：采矿、挖矿、采矿石、farm矿、挂机采矿等指令。"
    )

    def can_handle(self, instruction: str) -> float:
        keywords = ["采矿", "挖矿", "矿石", "mining", "mine", "矿", "farm矿"]
        for kw in keywords:
            if kw.lower() in instruction.lower():
                return 0.9
        return 0.0

    def run(self, ctx: SkillContext) -> SkillResult:
        gathered = 0
        skipped = 0
        llm_calls = 0
        current_bearing = 0.0          # 当前飞行朝向
        consecutive_empty_scans = 0    # 连续找不到矿点的次数
        max_session = config.max_session_minutes * 60

        # ── 起飞 ──────────────────────────────────────────────────────────
        _log(ctx, "🛫 起飞")
        takeoff()

        # ── 主循环 ────────────────────────────────────────────────────────
        while not ctx.should_stop():

            # 超时保护
            if ctx.elapsed() > max_session:
                _log(ctx, f"⏰ 超过最大时长 {config.max_session_minutes}min，停止")
                break

            # ── 截图 + 找矿点 ──────────────────────────────────────────
            frame = capture_full()
            minimap_crop = _get_minimap(frame)

            if minimap_crop is not None:
                nodes = find_nodes(minimap_crop, node_type="mining")
                target = best_node(nodes, avoid_enemies=True)
            else:
                nodes = []
                target = None

            # ── 有矿点：飞过去采 ───────────────────────────────────────
            if target:
                consecutive_empty_scans = 0
                dist = int((target.dx**2 + target.dy**2) ** 0.5)
                _log(ctx, f"🪨 发现矿点 方位={target.bearing_deg:.0f}° 距离={dist}px")

                # 转向飞过去
                current_bearing = fly_to_bearing(
                    bearing=target.bearing_deg,
                    current_bearing=current_bearing,
                    duration=DEFAULT_FLY_DURATION,
                    jitter_deg=8.0,
                )

                # 降落前先检测头顶血条
                _log(ctx, "👀 降落检查是否有敌人...")
                landing_frame = capture_full()
                enemy_result = detect_enemies(landing_frame)

                if enemy_result.has_enemy:
                    skipped += 1
                    _log(ctx, f"⚠ 发现 {enemy_result.count} 个敌人血条（置信度{enemy_result.confidence:.2f}），绕开")
                    # 偏转方向继续飞，不降落
                    away = (target.bearing_deg + 120 + random.uniform(-30, 30)) % 360
                    current_bearing = fly_to_bearing(away, current_bearing, jitter_deg=15.0)
                else:
                    # 安全，降落采集
                    _log(ctx, "⛏ 无敌人，降落采集")
                    descend_and_interact()
                    gathered += 1
                    _log(ctx, f"✓ 第 {gathered} 个矿采集完成")
                    # 重新起飞
                    time.sleep(random.uniform(0.5, 1.0))
                    takeoff()

            # ── 小地图没有矿点：看大地图 ───────────────────────────────
            else:
                consecutive_empty_scans += 1
                _log(ctx, f"🔍 小地图无矿点（连续第{consecutive_empty_scans}次）")

                if consecutive_empty_scans >= 3:
                    # 连续3次找不到，打开大地图决定方向
                    _log(ctx, "🗺 打开大地图定位...")
                    land()
                    open_map()
                    time.sleep(0.5)

                    pos = read_player_position()
                    close_map()

                    if pos:
                        suggested = suggest_explore_direction(pos)
                        _log(ctx, f"📍 角色位置 ({pos.norm_x:.2f}, {pos.norm_y:.2f})，建议方向 {suggested:.0f}°")
                        current_bearing = suggested
                        consecutive_empty_scans = 0
                        takeoff()
                        current_bearing = fly_to_bearing(current_bearing, current_bearing, jitter_deg=20.0)
                    else:
                        # 大地图也定位失败，上 LLM 兜底
                        _log(ctx, "🤖 LLM 兜底推理...")
                        close_map()
                        frame2 = capture_full()
                        llm_calls += 1
                        decision = ask_llm(
                            frame2,
                            context=f"连续{consecutive_empty_scans}次找不到矿点，需要决定探索方向",
                            regions=[config.region_minimap] if config.region_minimap else None,
                        )
                        _log(ctx, f"🤖 LLM: {decision.action} {decision.bearing_deg:.0f}° — {decision.reasoning}")

                        if decision.action == "fly_to" and decision.confidence > 0.5:
                            current_bearing = fly_to_bearing(
                                decision.bearing_deg, current_bearing, jitter_deg=15.0
                            )
                            consecutive_empty_scans = 0
                        else:
                            # 实在不知道，随机换方向继续飞
                            fallback_dir = explore_direction(current_bearing)
                            _log(ctx, f"🎲 随机探索方向 {fallback_dir:.0f}°")
                            current_bearing = fly_to_bearing(fallback_dir, current_bearing, jitter_deg=20.0)
                            consecutive_empty_scans = 0

                        takeoff()
                else:
                    # 还没到阈值，先换个方向继续飞
                    next_dir = explore_direction(current_bearing)
                    _log(ctx, f"↗ 换方向探索 {next_dir:.0f}°")
                    current_bearing = fly_to_bearing(next_dir, current_bearing, jitter_deg=15.0)

            # ── 每 10 个矿汇报一次给 agent loop ───────────────────────
            if gathered > 0 and gathered % 10 == 0:
                return SkillResult(
                    success=True,
                    message=(
                        f"采矿进行中：已采 {gathered} 个，"
                        f"跳过 {skipped} 个（有敌人），"
                        f"LLM兜底 {llm_calls} 次，"
                        f"运行 {ctx.elapsed():.0f}s"
                    ),
                    data={
                        "gathered": gathered,
                        "skipped": skipped,
                        "llm_calls": llm_calls,
                    },
                    should_continue=True,
                )

        # ── 结束 ──────────────────────────────────────────────────────────
        land()
        return SkillResult(
            success=True,
            message=f"采矿结束：共采 {gathered} 个，跳过 {skipped} 个，LLM兜底 {llm_calls} 次，运行 {ctx.elapsed():.0f}s",
            data={"gathered": gathered, "skipped": skipped, "llm_calls": llm_calls},
            should_continue=False,
        )


# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _get_minimap(frame):
    """从全屏截图裁剪小地图区域"""
    if not config.region_minimap:
        return None
    r = config.region_minimap
    return frame[r["top"]:r["top"]+r["height"], r["left"]:r["left"]+r["width"]]


def _log(ctx: SkillContext, msg: str):
    """输出日志（supervisor panel 会接管显示）"""
    import time as _t
    ts = _t.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
