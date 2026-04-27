"""
skills/registry.py — skill 注册表
"""
from typing import Type
from .base import Skill


_registry: dict[str, Type[Skill]] = {}


def register(skill_cls: Type[Skill]) -> Type[Skill]:
    """装饰器：注册一个 skill"""
    _registry[skill_cls.name] = skill_cls
    return skill_cls


def all_skills() -> list[Type[Skill]]:
    return list(_registry.values())


def get_skill(name: str) -> Type[Skill] | None:
    return _registry.get(name)


def skill_descriptions() -> str:
    """返回所有 skill 的描述，供 LLM 选择"""
    lines = []
    for cls in _registry.values():
        lines.append(f"- {cls.name}: {cls.description}")
    return "\n".join(lines)
