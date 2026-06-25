"""
unframed CLI — interactive AI narrative game.

Run::

    unframed                          # starts an interactive session
    unframed --model deepseek-chat    # use a different model
    unframed --base-url https://...   # custom API endpoint

Environment variables:

    OPENAI_API_KEY   API key (also accepted via --api-key)
    OPENAI_BASE_URL  API base URL (also accepted via --base-url)
    OPENAI_MODEL     Model name (default: gpt-4o)
"""

from __future__ import annotations

import argparse
import atexit
import itertools
import json
import os
import sys
import threading
import time
from typing import List, Optional

# ---- Colorama: 跨平台 ANSI 支持 ----
import colorama

colorama.init()

# ---- Readline: 命令行历史、行编辑 ----
try:
    import readline  # noqa: F401

    histfile = os.path.expanduser("~/.unframed_history")
    try:
        readline.read_history_file(histfile)
    except (FileNotFoundError, OSError):
        pass

    atexit.register(readline.write_history_file, histfile)
except ImportError:
    pass

# ---- Rich: Markdown 渲染输出 ----
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from .engine import GameEngine


# ======================================================================
# 常量
# ======================================================================

AUTOSAVE_PATH = os.path.expanduser("~/.unframed_autosave.json")
SAVES_DIR = os.path.expanduser("~/.unframed_saves")
SEEDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "seeds"))


# ======================================================================
# 种子发现
# ======================================================================


def _find_seeds() -> List[dict]:
    """Scans seeds directory, returns available seed files."""
    if not os.path.isdir(SEEDS_DIR):
        return []
    seeds = []
    for f in sorted(os.listdir(SEEDS_DIR)):
        if f.endswith(".md"):
            path = os.path.join(SEEDS_DIR, f)
            name = f[:-3]
            try:
                with open(path, encoding="utf-8") as fh:
                    first = fh.readline().strip().lstrip("# ")
            except OSError:
                first = ""
            seeds.append({"name": name, "path": path, "desc": first})
    return seeds


# ======================================================================
# 存档管理
# ======================================================================


def _save_slot_path(slot: str) -> str:
    os.makedirs(SAVES_DIR, exist_ok=True)
    return os.path.join(SAVES_DIR, f"slot_{slot}.json")


def _list_saves() -> List[dict]:
    if not os.path.isdir(SAVES_DIR):
        return []
    saves = []
    for f in sorted(os.listdir(SAVES_DIR)):
        if f.startswith("slot_") and f.endswith(".json"):
            slot = f.replace("slot_", "").replace(".json", "")
            path = os.path.join(SAVES_DIR, f)
            try:
                with open(path, encoding="utf-8") as fh:
                    meta = json.load(fh)
                saves.append({"slot": slot, "path": path, "round": meta.get("round", "?")})
            except (json.JSONDecodeError, OSError):
                saves.append({"slot": slot, "path": path, "round": "?"})
    return saves


# ======================================================================
# 启动菜单
# ======================================================================


def _startup_menu() -> Optional[dict]:
    """Show menu, return {'action':..., 'path':...} or None to quit."""
    seeds = _find_seeds()
    saves = _list_saves()
    has_autosave = os.path.exists(AUTOSAVE_PATH)

    console.print()
    console.print("[bold]启动选项：[/]")
    console.print()

    items = []
    if has_autosave:
        items.append(("c", "继续上次游戏"))
    for i, s in enumerate(seeds, 1):
        items.append((str(i), f"新游戏：{s['name']}  {s['desc']}"))
    if not seeds:
        items.append(("n", "新游戏（无种子）"))
    if saves:
        items.append(("l", "读档"))
    items.append(("q", "退出"))

    for key, label in items:
        console.print(f"  [bold green]{key}[/]  {label}")

    while True:
        pick = input("\033[1;32m> \033[0m").strip().lower()
        if pick == "q":
            return None
        if pick == "c" and has_autosave:
            return {"action": "continue", "path": AUTOSAVE_PATH}
        if pick == "l" and saves:
            return {"action": "load_menu", "saves": saves}
        if pick == "n" and not seeds:
            return {"action": "new", "seed": None}
        if seeds and pick.isdigit():
            idx = int(pick) - 1
            if 0 <= idx < len(seeds):
                return {"action": "new", "seed": seeds[idx]["path"]}
        console.print("[red]无效选择[/]")


def _show_saves() -> None:
    """显示所有存档槽位。"""
    saves = _list_saves()
    if not saves:
        console.print("[dim]暂无存档。使用 /save <数字> 存档[/]")
        return
    console.print("[bold]存档列表：[/]")
    for s in saves:
        console.print(f"  [bold green]{s['slot']}[/]  第 {s['round']} 轮")


def _show_load_menu(engine: GameEngine) -> None:
    """显示读档选择菜单。"""
    saves = _list_saves()
    if not saves:
        console.print("[dim]暂无存档。[/]")
        return
    console.print("[bold]读档：选择存档槽位[/]")
    for s in saves:
        console.print(f"  [bold green]{s['slot']}[/]  第 {s['round']} 轮")
    console.print("  [bold green]q[/]  取消")
    while True:
        pick = input("\033[1;32m> \033[0m").strip().lower()
        if pick == "q":
            return
        if pick.isdigit():
            path = _save_slot_path(pick)
            if os.path.exists(path):
                _load_game(engine, path)
                return
        console.print("[red]无效选择[/]")


# ======================================================================
# Spinner（后台转圈指示器）
# ======================================================================


class _Spinner:
    """Simple spinner that runs in a background thread.

    Message can be updated dynamically via :meth:`update` so the
    displayed text reflects what the AI is currently doing.
    Automatically clears when stopped.
    """

    _FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None
        self._msg = "AI 正在调整世界"

    def start(self, msg: str = "") -> None:
        if msg:
            self._msg = msg
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def update(self, msg: str) -> None:
        """Update the displayed message (thread-safe)."""
        self._msg = msg

    def _spin(self) -> None:
        for frame in itertools.cycle(self._FRAMES):
            if not self._running:
                break
            sys.stdout.write(f"\r\033[2K\033[2m{frame} {self._msg}...\033[0m")
            sys.stdout.flush()
            time.sleep(0.1)
        # Clear the line on stop
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
            self._thread = None


# ======================================================================
# Console
# ======================================================================

console = Console()


# ======================================================================
# 工具名称 → 显示文案映射
# ======================================================================

_TOOL_LABELS = {
    "set_var": "修改世界状态",
    "get_var": "读取变量",
    "pin_var": "固定核心变量",
    "unpin_var": "释放核心变量",
    "mark_as_end_node": "准备结局",
    "set_setting": "锁定游戏设定",
    "set_root_plan_node": "规划剧情主线",
    "append_plan_node": "规划剧情分支",
    "advance_plot": "推进剧情",
}


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
        help="Custom API base URL (default: OPENAI_BASE_URL env)",
    )
    parser.add_argument(
        "--model",
        help="Model name (default: gpt-4o, overridable via OPENAI_MODEL env)",
    )
    parser.add_argument(
        "--continue",
        action="store_true",
        dest="resume",
        help="从上次自动存档继续游戏，并打印历史",
    )
    parser.add_argument(
        "--seed",
        help="种子文件路径（Markdown），定义游戏世界观、规则和目标",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="显示工具调用等调试信息",
    )
    return parser


def print_banner() -> None:
    """Print a welcome banner."""
    panel = Panel(
        Text("AI 自举叙事游戏 · 无预设框架", justify="center"),
        title="[bold]U N F R A M E D[/]",
        title_align="center",
        border_style="cyan",
        padding=(1, 2),
        subtitle="AI 从零构建世界观、规则、角色与剧情",
    )
    console.print()
    console.print(panel)
    console.print()
    console.print(
        "输入你的行动或对话，按下回车继续故事。\n"
        "[dim]/quit 退出 | /save <path> 存档 | /load <path> 读档[/]"
    )
    console.print()


# ======================================================================
# Streaming Display — BBCode 渲染
# ======================================================================


def _handle_stream(engine: GameEngine, player_input: str, debug: bool = False) -> bool:
    """Run one game round. Buffers all narrative, renders as Markdown when done.

    Shows a spinner during AI thinking/tool-calling.

    Returns:
        ``True`` if the game should continue, ``False`` if it has ended.
    """
    narrative = ""
    tool_names: List[str] = []
    spinner = _Spinner()
    spinner.start("AI 正在构思剧情")

    for event in engine.play(player_input):
        if event["type"] == "content":
            narrative += event["data"]

        elif event["type"] == "tool_call":
            fn_name = event["data"]["function"]["name"]
            spinner.update(f"AI 正在{_TOOL_LABELS.get(fn_name, '调整世界')}")
            tool_names.append(fn_name)

            if debug:
                spinner.stop()
                raw_args = event["data"]["function"]["arguments"]
                try:
                    args = json.loads(raw_args)
                except (json.JSONDecodeError, TypeError):
                    args = raw_args
                parts = [f"[debug] {fn_name}"]
                if isinstance(args, dict):
                    for k, v in args.items():
                        parts.append(f"  {k}={v}")
                sys.stdout.write("\033[2K" + "".join(parts) + "\n")
                sys.stdout.flush()
                spinner.start()

        elif event["type"] == "tool_result":
            if debug:
                spinner.stop()
                name = event["data"]["name"]
                result = event["data"]["result"]
                # Truncate long results
                if len(result) > 120:
                    result = result[:117] + "..."
                sys.stdout.write(f"\033[2K[debug] {name} -> {result}\n")
                sys.stdout.flush()
                spinner.start()

        elif event["type"] == "error":
            spinner.stop()
            console.print(f"\n[bold red]╴ 系统错误: {event['data']}[/]")

        elif event["type"] == "done":
            spinner.stop()
            if narrative:
                console.print(Markdown(narrative))
                console.print()

    return not engine.is_ending


# ======================================================================
# Save / Load
# ======================================================================


def _save_game(engine: GameEngine, path: str, quiet: bool = False) -> None:
    """Save the current game state to a JSON file."""
    try:
        state = engine.export_state()
        state["conversation"] = engine.export_conversation()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        if not quiet:
            console.print(f"[dim]✓ 存档已保存至 {path}[/]")
    except OSError as e:
        if not quiet:
            console.print(f"[bold red]✗ 无法写入存档: {e}[/]")


def _load_game(engine: GameEngine, path: str) -> None:
    """Load a game state from a JSON file."""
    if not os.path.exists(path):
        console.print(f"[bold red]✗ 存档文件不存在: {path}[/]")
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        engine.import_state(state)
        conversation = state.get("conversation", [])
        if conversation:
            engine.import_conversation(conversation)
        console.print(f"[dim]✓ 存档已加载: 第 {engine.round_num} 轮[/]")
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        console.print(f"[bold red]✗ 无法读取存档: 文件格式损坏 ({e})[/]")


def _print_history(engine: GameEngine) -> None:
    """打印对话历史中所有 AI 叙事内容。"""
    first = True
    for msg in engine.export_conversation():
        if msg.get("role") == "assistant" and msg.get("content"):
            if not first:
                console.print("\n[dim]─[/]")
            first = False
            console.print(Markdown(msg["content"]))
    console.print("\n[dim]━━━ 历史结束，继续游戏 ━━━[/]")
    console.print()


# ======================================================================
# Main
# ======================================================================


def main(argv: Optional[List[str]] = None) -> None:
    """Main entry point for ``unframed``."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]错误：[/]需要 API Key。"
            "请设置 [bold]OPENAI_API_KEY[/] 环境变量"
            "或通过 [bold]--api-key[/] 参数传入。"
        )
        sys.exit(1)

    base_url = args.base_url or os.environ.get("OPENAI_BASE_URL")
    model = args.model or os.environ.get("OPENAI_MODEL", "gpt-4o")

    engine = GameEngine(
        api_key=api_key,
        base_url=base_url,
        model=model,
    )

    # ---- 启动流程 ----
    seed_content: Optional[str] = None
    use_menu = not args.seed and not getattr(args, "resume", False)

    if getattr(args, "resume", False):
        if os.path.exists(AUTOSAVE_PATH):
            _load_game(engine, AUTOSAVE_PATH)
            _print_history(engine)
        else:
            console.print("[bold red]没有找到自动存档，开始新游戏。[/]")
    elif args.seed:
        try:
            with open(args.seed, "r", encoding="utf-8") as f:
                seed_content = f.read()
            console.print(f"[dim]已加载种子: {args.seed}[/]")
        except (FileNotFoundError, OSError) as e:
            console.print(f"[bold red]无法读取种子文件: {e}[/]")
            sys.exit(1)

    if use_menu:
        choice = _startup_menu()
        if choice is None:
            sys.exit(0)
        if choice["action"] == "continue":
            _load_game(engine, choice["path"])
            _print_history(engine)
        elif choice["action"] == "new":
            if choice.get("seed"):
                with open(choice["seed"], "r", encoding="utf-8") as f:
                    seed_content = f.read()
                console.print(f"[dim]已加载种子: {choice['seed']}[/]")
        elif choice["action"] == "load_menu":
            _show_load_menu(engine)

    print_banner()

    # ---- Interactive game loop ----
    first_round = True

    while True:
        if first_round and seed_content:
            player_input = seed_content
            seed_content = None
        else:
            try:
                console.print()
                player_input = input("\033[1;32m> \033[0m").strip()
                console.print()
            except (EOFError, KeyboardInterrupt):
                console.print()
                console.print("\n[dim]游戏结束。[/]")
                break

        first_round = False

        # -- Special commands --
        if player_input == "/quit":
            console.print("[dim]游戏结束。感谢游玩！[/]")
            break

        if player_input.startswith("/save "):
            arg = player_input[6:].strip()
            if arg == "list":
                _show_saves()
            elif arg.isdigit():
                _save_game(engine, _save_slot_path(arg))
            else:
                _save_game(engine, arg)
            continue

        if player_input.startswith("/load "):
            arg = player_input[6:].strip()
            if arg == "" or arg == "list":
                _show_load_menu(engine)
            elif arg.isdigit():
                _load_game(engine, _save_slot_path(arg))
            else:
                _load_game(engine, arg)
            continue

        if player_input == "":
            continue

        # -- Game round --
        should_continue = _handle_stream(engine, player_input, debug=args.debug)
        _save_game(engine, AUTOSAVE_PATH, quiet=True)
        if not should_continue:
            console.print(
                f"\n[bold yellow]╴ 故事结束[/] {engine.end_requested}"
            )
            console.print("[dim]输入 /quit 退出，或继续输入进行自由探索。[/]")

    sys.exit(0)


if __name__ == "__main__":
    main()
