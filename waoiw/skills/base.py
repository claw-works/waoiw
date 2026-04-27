"""
skills/base.py — Skill 基类
每个 Skill 描述自己能干什么，agent loop 根据描述选择合适的 skill 执行。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any
import time


@dataclass
class SkillContext:
    """运行时上下文，skill 可以读取和写入"""
    instruction: str = ""           # 用户原始指令
    params: dict = field(default_factory=dict)  # agent 解析出的参数
    stop_requested: bool = False    # 外部请求停止
    session_start: float = field(default_factory=time.time)

    def elapsed(self) -> float:
        return time.time() - self.session_start

    def should_stop(self) -> bool:
        return self.stop_requested


@dataclass
class SkillResult:
    success: bool
    message: str                    # 反馈给 agent loop 的摘要
    data: dict = field(default_factory=dict)
    should_continue: bool = False   # 是否需要 agent 继续决策


class Skill(ABC):
    # 子类必须定义这两个
    name: str = ""
    description: str = ""

    @abstractmethod
    def run(self, ctx: SkillContext) -> SkillResult:
        """执行 skill，返回结果"""
        ...

    def can_handle(self, instruction: str) -> float:
        """
        返回 0.0-1.0，表示这个 skill 有多适合处理该指令。
        默认返回 0（由 LLM 决策），子类可以覆盖做关键词快速匹配。
        """
        return 0.0
