# SPDX-FileCopyrightText: 2026-present zaf-x <baoshuwen2013@outlook.com>
#
# SPDX-License-Identifier: MIT

"""
unframed — AI 自举叙事游戏

AI 从零开始构建世界观、规则、角色与剧情。
核心原则：无预设框架，AI 是唯一的创世者。
"""

from unframed.engine import GameEngine, VarEntry, PlanNode, SYSTEM_PROMPT
from unframed.render import BBCodeRenderer, render, strip_tags

__all__ = [
    "GameEngine",
    "VarEntry",
    "PlanNode",
    "SYSTEM_PROMPT",
    "BBCodeRenderer",
    "render",
    "strip_tags",
]
