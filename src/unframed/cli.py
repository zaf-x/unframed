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
import datetime
import itertools
import json
import os
import sys
import termios
import threading
import time
import tty
from typing import Any, Dict, List, Optional

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
from .settings import load_settings, save_settings, DEFAULT_MODEL, DEFAULT_TEMPERATURE


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
    """Scans seeds directory for .json seed files."""
    if not os.path.isdir(SEEDS_DIR):
        return []
    seeds = []
    for f in sorted(os.listdir(SEEDS_DIR)):
        if f.endswith(".json"):
            json_path = os.path.join(SEEDS_DIR, f)
            try:
                with open(json_path, encoding="utf-8") as fh:
                    meta = json.load(fh)
                title = meta.get("title", f[:-5])
                content_rel = meta.get("content", "")
                content_path = os.path.join(SEEDS_DIR, content_rel) if content_rel else ""
                if not content_path or not os.path.exists(content_path):
                    continue
                seeds.append({
                    "title": title,
                    "path": content_path,
                })
            except (json.JSONDecodeError, OSError):
                continue
    return seeds


# ======================================================================
# 存档管理
# ======================================================================

MAX_SLOTS = 10

def _save_slot_path(slot: str) -> str:
    os.makedirs(SAVES_DIR, exist_ok=True)
    return os.path.join(SAVES_DIR, f"slot_{slot}.json")


def _save_meta(path: str) -> Optional[dict]:
    """Read save file metadata without loading the full game."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None
    return {
        "round": data.get("round", "?"),
        "time": data.get("save_time", ""),
        "model": data.get("model", ""),
    }


def _list_saves() -> List[dict]:
    if not os.path.isdir(SAVES_DIR):
        return []
    saves = []
    for f in sorted(os.listdir(SAVES_DIR)):
        if f.startswith("slot_") and f.endswith(".json"):
            slot = f.replace("slot_", "").replace(".json", "")
            path = os.path.join(SAVES_DIR, f)
            meta = _save_meta(path)
            if meta:
                saves.append({"slot": slot, "path": path, **meta})
    return saves


def _format_time(ts: str) -> str:
    """Format ISO timestamp for display."""
    if not ts:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(ts)
        return dt.strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return ts


def _show_save_slots(highlight: Optional[str] = None) -> None:
    """Display save slots 1-10 with existing save info."""
    saves = {s["slot"]: s for s in _list_saves()}
    console.print()
    console.print("[bold]存档槽位：[/]")
    for i in range(1, MAX_SLOTS + 1):
        si = str(i)
        if si in saves:
            s = saves[si]
            info = f"第 {s['round']} 轮"
            if s.get("time"):
                info += f"  {_format_time(s['time'])}"
            marker = " [bold green]◀[/]" if si == highlight else ""
            console.print(f"  [bold]{i}[/]  {info}{marker}")
        else:
            marker = " [bold green]◀[/]" if si == highlight else ""
            console.print(f"  [bold]{i}[/]  [dim]空[/]{marker}")
    console.print(f"  [bold]q[/]  取消")


def _confirm(msg: str) -> bool:
    """Ask for y/n confirmation."""
    console.print()
    console.print(f"[yellow]{msg} (y/n)[/]")
    while True:
        c = input("\033[1;32m>\033[0m ").strip().lower()
        if c == "y":
            return True
        if c == "n":
            return False
        console.print("[red]请输入 y 或 n[/]")


def _save_menu(engine: GameEngine) -> None:
    """Interactive save menu."""
    _show_save_slots()
    console.print()

    while True:
        pick = input("\033[1;32m存到哪个槽位？\033[0m ").strip()
        if pick == "q":
            return
        if pick.isdigit():
            n = int(pick)
            if n < 1 or n > MAX_SLOTS:
                console.print(f"[red]槽位 1-{MAX_SLOTS}[/]")
                continue
            path = _save_slot_path(pick)
            if os.path.exists(path) and not _confirm("该槽位已有存档，覆盖？"):
                return
            _save_game(engine, path)
            return
        console.print("[red]无效[/]")


def _load_menu(engine: GameEngine) -> bool:
    """Interactive load menu. Returns True if a save was loaded."""
    saves = _list_saves()
    if not saves:
        console.print("[dim]暂无存档[/]")
        return False

    _show_save_slots()
    console.print()

    while True:
        pick = input("\033[1;32m读哪个槽位？\033[0m ").strip()
        if pick == "q":
            return False
        if pick.isdigit():
            path = _save_slot_path(pick)
            if not os.path.exists(path):
                console.print("[red]该槽位为空[/]")
                continue
            _load_game(engine, path)
            return True
        console.print("[red]无效[/]")


def _delete_menu() -> None:
    """Interactive delete save menu."""
    saves = _list_saves()
    if not saves:
        console.print("[dim]暂无存档可删除[/]")
        return

    _show_save_slots()
    console.print()

    while True:
        pick = input("\033[1;32m删除哪个槽位？\033[0m ").strip()
        if pick == "q":
            return
        if pick.isdigit():
            path = _save_slot_path(pick)
            if not os.path.exists(path):
                console.print("[red]该槽位为空[/]")
                continue
            if _confirm(f"确定删除槽位 {pick}？"):
                os.remove(path)
                console.print(f"[dim]已删除槽位 {pick}[/]")
            return
        console.print("[red]无效[/]")


# ======================================================================
# 启动菜单
# ======================================================================


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
    "show_var": "显示变量",
    "unshow_var": "隐藏变量",
}


# ======================================================================
# Helpers
# ======================================================================


def _build_parser(defaults: Dict[str, Any]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="unframed",
        description="AI 叙事游戏 — AI 从零构建世界观、规则、角色与剧情（默认 TUI）",
        add_help=False,
    )
    parser.add_argument(
        "--api-key",
        default=defaults.get("api_key"),
        help="OpenAI-compatible API key (default: OPENAI_API_KEY env or config)",
    )
    parser.add_argument(
        "--base-url",
        default=defaults.get("base_url"),
        help="Custom API base URL (default: OPENAI_BASE_URL env or config)",
    )
    parser.add_argument(
        "--model",
        default=defaults.get("model"),
        help="Model name (default: config or gpt-4o)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=defaults.get("temperature"),
        help="Sampling temperature (default: config or 0.7)",
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
    parser.add_argument(
        "--cli",
        action="store_true",
        help="使用 CLI 模式（默认 TUI）",
    )
    parser.add_argument(
        "-h", "--help",
        action="store_true",
        help="显示完整帮助文档",
    )
    return parser


def print_banner() -> None:
    """Print the welcome banner."""
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


# ======================================================================
# 键盘输入与菜单组件
# ======================================================================


def _read_key() -> str:
    """Read a single keypress. Returns 'up'/'down'/'enter'/'q' or the char."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            if seq == "[A":
                return "up"
            if seq == "[B":
                return "down"
            return "escape"
        if ch == "\r" or ch == "\n":
            return "enter"
        return ch.lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _menu_selector(items: List[str]) -> Optional[int]:
    """Show a list of items with arrow-key navigation.

    Args:
        items: List of display strings.

    Returns:
        Selected index (0-based), or ``None`` if cancelled.
    """
    n = len(items)
    sel = 0

    def _render() -> None:
        for i, item in enumerate(items):
            if i == sel:
                sys.stdout.write(f"\033[2K\r  \033[7m {item} \033[0m\n")
            else:
                sys.stdout.write(f"\033[2K\r  {item}\n")
        sys.stdout.write(f"\033[2K\r  [dim]↑↓ 选择 | Enter 确认 | q 取消[/]\n")
        sys.stdout.flush()

    _render()
    # Move cursor up to allow overwriting
    cursor_up = n + 1

    while True:
        key = _read_key()
        if key == "up" and sel > 0:
            sel -= 1
        elif key == "down" and sel < n - 1:
            sel += 1
        elif key == "enter":
            # Clear menu
            sys.stdout.write(f"\033[{cursor_up}A")
            for i in range(cursor_up):
                sys.stdout.write("\033[2K\r\n")
            sys.stdout.write(f"\033[{cursor_up}A")
            sys.stdout.flush()
            return sel
        elif key == "q":
            sys.stdout.write(f"\033[{cursor_up}A")
            for i in range(cursor_up):
                sys.stdout.write("\033[2K\r\n")
            sys.stdout.write(f"\033[{cursor_up}A")
            sys.stdout.flush()
            return None
        else:
            continue

        # Re-render
        sys.stdout.write(f"\033[{cursor_up}A")
        _render()


# ======================================================================
# 启动菜单
# ======================================================================


def _show_help() -> None:
    """Print help information."""
    help_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs", "HELP.md"))
    if os.path.exists(help_path):
        with open(help_path, encoding="utf-8") as f:
            content = f.read()
        console.print(Markdown(content))
    else:
        console.print("[red]帮助文档未找到[/]")
    console.print()
    console.print("[dim]按 Enter 返回...[/]")
    input()


def _startup_greeting() -> Optional[str]:
    """Show banner + arrow-key menu. Returns 'new' or 'load', or None to quit."""
    print_banner()
    idx = _menu_selector(["新游戏", "加载存档", "帮助文档", "退出"])
    if idx is None:
        return None
    if idx == 0:
        return "new"
    if idx == 1:
        return "load"
    if idx == 2:
        _show_help()
        return None
    return None


def _pick_seed() -> Optional[str]:
    """Show seed list with arrow keys. Returns content path or None."""
    seeds = _find_seeds()
    if not seeds:
        return None
    items = [f"《{s['title']}》" for s in seeds] + ["取消"]
    idx = _menu_selector(items)
    if idx is None or idx >= len(seeds):
        return None
    return seeds[idx]["path"]


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
        state["save_time"] = datetime.datetime.now().isoformat()
        state["model"] = engine.bot.model
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        if not quiet:
            slot_name = os.path.basename(path).replace(".json", "")
            console.print(f"[dim]✓ 已保存 ({slot_name})[/]")
    except OSError as e:
        if not quiet:
            console.print(f"[bold red]✗ 无法写入: {e}[/]")


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
    # ---- Load persisted settings first; env vars take precedence. ----
    settings = load_settings()
    defaults = {
        "api_key": os.environ.get("OPENAI_API_KEY") or settings.get("api_key") or "",
        "base_url": os.environ.get("OPENAI_BASE_URL") or settings.get("base_url") or None,
        "model": os.environ.get("OPENAI_MODEL") or settings.get("model") or DEFAULT_MODEL,
        "temperature": float(
            os.environ.get("OPENAI_TEMPERATURE")
            or settings.get("temperature")
            or DEFAULT_TEMPERATURE
        ),
    }

    parser = _build_parser(defaults)
    args = parser.parse_args(argv)

    # ---- 默认 TUI，除非指定 --cli 或需 CLI 的参数 ----
    use_cli = (
        getattr(args, "cli", False)
        or args.seed
        or getattr(args, "resume", False)
        or args.debug
    )

    # ---- 完整帮助文档 ----
    if getattr(args, "help", False):
        _show_help()
        sys.exit(0)

    if not use_cli:
        try:
            from unframed.tui.app import main as tui_main
            tui_main()
        except ImportError as e:
            console.print(f"[bold red]TUI 不可用，回退 CLI: {e}[/]")
            use_cli = True
        else:
            sys.exit(0)

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]错误：[/]需要 API Key。"
            "请设置 [bold]OPENAI_API_KEY[/] 环境变量"
            "或通过 [bold]--api-key[/] 参数传入。"
        )
        sys.exit(1)

    base_url = args.base_url or os.environ.get("OPENAI_BASE_URL")
    model = args.model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    temperature = args.temperature

    engine = GameEngine(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
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
        except (FileNotFoundError, OSError) as e:
            console.print(f"[bold red]无法读取种子文件: {e}[/]")
            sys.exit(1)

    if use_menu:
        action = _startup_greeting()
        if action is None:
            sys.exit(0)
        if action == "load":
            if not _load_menu(engine):
                # Load cancelled — start new game without seed
                pass
        elif action == "new":
            seed_path = _pick_seed()
            if seed_path:
                with open(seed_path, "r", encoding="utf-8") as f:
                    seed_content = f.read()

    # ---- 游戏内操作提示 ----
    if not args.seed and not getattr(args, "resume", False):
        console.print("[dim]/save 存档 | /load 读档 | /delete 删档 | /quit 退出[/]")

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

        if player_input == "/save":
            _save_menu(engine)
            continue

        if player_input.startswith("/save "):
            arg = player_input[6:].strip()
            if not arg:
                continue
            if arg == "list":
                _show_save_slots()
            elif arg.isdigit():
                _save_game(engine, _save_slot_path(arg))
            else:
                _save_game(engine, arg)
            continue

        if player_input == "/load":
            _load_menu(engine)
            continue

        if player_input.startswith("/load "):
            arg = player_input[6:].strip()
            if arg == "" or arg == "list":
                _show_save_slots()
            elif arg.isdigit():
                _load_game(engine, _save_slot_path(arg))
            else:
                _load_game(engine, arg)
            continue

        if player_input == "/delete":
            _delete_menu()
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
