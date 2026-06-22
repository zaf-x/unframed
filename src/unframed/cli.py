"""
unframed CLI — interactive AI narrative game.

Run::

    unframed                          # starts an interactive session
    unframed --model deepseek-chat    # use a different model
    unframed --base-url https://...   # custom API endpoint

Environment variables:

    OPENAI_API_KEY   API key (also accepted via --api-key)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from .engine import GameEngine


# ======================================================================
# Helpers
# ======================================================================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="unframed",
        description="AI 叙事游戏 — AI 从零构建世界观、规则、角色与剧情",
    )
    parser.add_argument(
        "--api-key",
        help="OpenAI-compatible API key (default: OPENAI_API_KEY env)",
    )
    parser.add_argument(
        "--base-url",
        help="Custom API base URL (for compatible providers)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o",
        help="Model name (default: gpt-4o)",
    )
    return parser


def print_banner() -> None:
    """Print a welcome banner."""
    banner = r"""
    ╔══════════════════════════════════════════╗
    ║           U N F R A M E D                ║
    ║     AI 自举叙事游戏 · 无预设框架         ║
    ╚══════════════════════════════════════════╝

AI 将从零开始构建世界观、规则、角色与剧情。
输入你的行动或对话，按下回车继续故事。
输入 /quit 退出，输入 /save <path> 存档，输入 /load <path> 读档。

准备好了吗？输入任意内容开始你的冒险...

"""
    print(banner)


# ======================================================================
# Streaming Display
# ======================================================================


def _handle_stream(engine: GameEngine, player_input: str) -> bool:
    """Run one game round and display the stream.

    Returns:
        ``True`` if the game should continue, ``False`` if it has ended.
    """
    tool_names: List[str] = []
    narrative_chunks: List[str] = []

    for event in engine.play(player_input):
        if event["type"] == "content":
            chunk = event["data"]
            narrative_chunks.append(chunk)
            print(chunk, end="", flush=True)

        elif event["type"] == "tool_call":
            fn_name = event["data"]["function"]["name"]
            tool_names.append(fn_name)
            # Optionally show tool progress:
            # print(f"\n  [工具: {fn_name}]", end="", flush=True)

        elif event["type"] == "tool_result":
            # Optionally show results:
            # result = event["data"]["result"]
            pass

        elif event["type"] == "error":
            print(f"\n[系统错误] {event['data']}", file=sys.stderr)

        elif event["type"] == "done":
            # Ensure we end with a newline
            if narrative_chunks:
                print()

    return not engine.is_ending


# ======================================================================
# Save / Load
# ======================================================================


def _save_game(engine: GameEngine, path: str) -> None:
    """Save the current game state to a JSON file."""
    try:
        state = engine.export_state()
        state["conversation"] = engine.export_conversation()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print(f"[存档已保存至 {path}]")
    except OSError as e:
        print(f"[错误] 无法写入存档: {e}")


def _load_game(engine: GameEngine, path: str) -> None:
    """Load a game state from a JSON file."""
    if not os.path.exists(path):
        print(f"[错误] 存档文件不存在: {path}")
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        engine.import_state(state)
        conversation = state.get("conversation", [])
        if conversation:
            engine.import_conversation(conversation)
        print(f"[存档已加载: 第 {engine.round_num} 轮]")
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[错误] 无法读取存档: 文件格式损坏 ({e})")


# ======================================================================
# Main
# ======================================================================


def main(argv: Optional[List[str]] = None) -> None:
    """Main entry point for ``unframed``."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(
            "错误：需要 API Key。请设置 OPENAI_API_KEY 环境变量"
            "或通过 --api-key 参数传入。",
            file=sys.stderr,
        )
        sys.exit(1)

    engine = GameEngine(
        api_key=api_key,
        base_url=args.base_url,
        model=args.model,
    )

    print_banner()

    # ---- Interactive game loop ----
    while True:
        try:
            player_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("\n游戏结束。")
            break

        # -- Special commands --
        if player_input == "/quit":
            print("游戏结束。感谢游玩！")
            break

        if player_input.startswith("/save "):
            path = player_input[6:].strip()
            _save_game(engine, path)
            continue

        if player_input.startswith("/load "):
            path = player_input[6:].strip()
            _load_game(engine, path)
            continue

        if player_input == "":
            continue

        # -- Game round --
        should_continue = _handle_stream(engine, player_input)
        if not should_continue:
            print(
                f"\n[故事结束] {engine.end_requested}"
            )
            print("输入 /quit 退出，或继续输入进行自由探索。")

    sys.exit(0)


if __name__ == "__main__":
    main()
