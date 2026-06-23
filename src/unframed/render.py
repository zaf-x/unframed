"""
BBCode → ANSI 终端渲染器。

逻辑极简：遇到 [tag] 输出 ANSI 码 → 内容直接输出 → 遇到 [/tag] 输出 \033[0m。

支持标签：
    [b]           → 加粗
    [i]           → 斜体
    [u]           → 下划线
    [code]        → 青色（代码）
    [h1]          → 粗体+下划线（标题）
    [h2]          → 粗体（子标题）
    [color=X]     → 彩色文字
    [hr]          → 空行（被忽略）
    其余未知标签 → 静默忽略
"""

from __future__ import annotations

import re
from typing import Dict


# ======================================================================
# ANSI 码映射
# ======================================================================

_RESET = "\033[0m"

_STYLES: Dict[str, str] = {
    "b": "\033[1m",        # bold
    "i": "\033[3m",        # italic
    "u": "\033[4m",        # underline
    "s": "\033[9m",        # strikethrough
    "code": "\033[36m",    # cyan foreground
    "h1": "\033[1;4m",     # bold + underline
    "h2": "\033[1m",       # bold
    # Named colors
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "gray": "\033[90m",
    "dim": "\033[2m",
}


# ======================================================================
# Renderer
# ======================================================================


class BBCodeRenderer:
    """Incremental BBCode → ANSI renderer.

    开标签 → ANSI 码
    内容   → 直接输出
    闭标签 → \\033[0m

    跨块标签天然工作：前一块末尾 bold 没关，下一块开头继续 bold，
    直到遇到 [/b] 才 reset。最终由 reset() 确保终端不残留格式。

    Args:
        write: 输出回调（默认 sys.stdout.write）。
    """

    def __init__(self, write=None) -> None:
        self._write = write or (
            lambda s: (
                __import__("sys").stdout.write(s),
                __import__("sys").stdout.flush(),
            )
        )
        self._buffer = ""

    def feed(self, text: str) -> None:
        """处理一块 BBCode 文本，实时输出 ANSI 格式。"""
        self._buffer += text
        self._flush()

    def _flush(self) -> None:
        text = self._buffer
        out = []
        i = 0

        while i < len(text):
            if text[i] == "[":
                end = text.find("]", i)
                if end == -1:
                    # 标签未完成 — 留在 buffer
                    self._buffer = text[i:]
                    break

                raw = text[i + 1 : end]
                self._buffer = text[end + 1 :]

                if raw.startswith("/"):
                    # [/tag] → reset
                    out.append(_RESET)
                elif "=" in raw:
                    # [color=X] → ANSI
                    _, val = raw.split("=", 1)
                    code = _STYLES.get(val)
                    if code:
                        out.append(code)
                else:
                    # [tag] → ANSI
                    code = _STYLES.get(raw)
                    if code:
                        out.append(code)
                    # 未知标签（如 [hr]）→ 忽略

                i = end + 1
            else:
                out.append(text[i])
                i += 1

        if i >= len(text):
            self._buffer = ""

        if out:
            self._write("".join(out))

    def reset(self) -> None:
        """清 buffer 并输出 reset，确保终端不残留格式。"""
        self._buffer = ""
        self._write(_RESET)


# ======================================================================
# 辅助函数
# ======================================================================


def render(text: str) -> str:
    """一次性渲染（非流式），返回带 ANSI 码的字符串。"""
    from io import StringIO
    buf = StringIO()
    r = BBCodeRenderer(write=buf.write)
    r.feed(text)
    r.reset()
    return buf.getvalue()


def strip_tags(text: str) -> str:
    """移除所有 [tag] 标记，留下纯文本。"""
    return re.sub(r"\[/?(?:\w+)(?:=\w+)?\]", "", text)
