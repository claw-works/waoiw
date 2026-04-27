"""
skills/__init__.py — 导入所有 skill（触发注册）
"""
from .base import Skill, SkillContext, SkillResult
from .registry import register, all_skills, get_skill, skill_descriptions

# 导入所有具体 skill（触发 @register 装饰器）
from . import gather_mining

__all__ = [
    "Skill", "SkillContext", "SkillResult",
    "register", "all_skills", "get_skill", "skill_descriptions",
]
