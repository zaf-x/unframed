"""
unframed TUI — Textual-based frontend for the AI narrative game.
"""

from __future__ import annotations

import datetime
import json
import os
import uuid
from typing import List

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
)

from rich.markdown import Markdown

from ..engine import GameEngine
from ..settings import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    load_settings,
    save_settings,
)

SAVES_DIR = os.path.expanduser("~/.unframed_saves")
SEEDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "seeds"))
if not os.path.isdir(SEEDS_DIR):
    SEEDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "seeds"))


def _new_save_id() -> str:
    return uuid.uuid4().hex


def _save_path(uuid_str: str) -> str:
    os.makedirs(SAVES_DIR, exist_ok=True)
    return os.path.join(SAVES_DIR, f"{uuid_str}.json")


def _last_played_path() -> str:
    return os.path.join(SAVES_DIR, ".last_played")


def _read_last_played() -> str | None:
    """Read the last-played save UUID. Returns None if not found."""
    path = _last_played_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _write_last_played(uuid_str: str) -> None:
    """Record this save as the most recently played."""
    os.makedirs(SAVES_DIR, exist_ok=True)
    try:
        with open(_last_played_path(), "w", encoding="utf-8") as f:
            f.write(uuid_str)
    except OSError:
        pass


def _list_saves() -> list[dict]:
    """Scan SAVES_DIR for all save files. Returns sorted list of metadata dicts."""
    if not os.path.isdir(SAVES_DIR):
        return []
    saves = []
    for fname in os.listdir(SAVES_DIR):
        if fname.endswith(".json") and not fname.startswith("."):
            path = os.path.join(SAVES_DIR, fname)
            uuid_str = fname[:-5]  # strip .json
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                saves.append({
                    "uuid": data.get("uuid", uuid_str),
                    "name": data.get("name", uuid_str),
                    "round": data.get("round", "?"),
                    "save_time": data.get("save_time", ""),
                    "file": path,
                })
            except (json.JSONDecodeError, OSError):
                saves.append({
                    "uuid": uuid_str,
                    "name": f"[损坏] {uuid_str}",
                    "round": "?",
                    "save_time": "",
                    "file": path,
                    "corrupted": True,
                })
    saves.sort(key=lambda s: s.get("save_time", "") or "", reverse=True)
    return saves


# ======================================================================
# Helpers
# ======================================================================


def _find_seeds() -> List[dict]:
    if not os.path.isdir(SEEDS_DIR):
        return []
    seeds = []
    for f in sorted(os.listdir(SEEDS_DIR)):
        if f.endswith(".json"):
            try:
                with open(os.path.join(SEEDS_DIR, f), encoding="utf-8") as fh:
                    meta = json.load(fh)
                title = meta.get("title", f[:-5])
                content_rel = meta.get("content", "")
                content_path = os.path.join(SEEDS_DIR, content_rel) if content_rel else ""
                if not content_path or not os.path.exists(content_path):
                    continue
                seeds.append({"title": title, "path": content_path})
            except (json.JSONDecodeError, OSError):
                continue
    return seeds


def _format_time(ts: str) -> str:
    if not ts:
        return ""
    try:
        return datetime.datetime.fromisoformat(ts).strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return ts


# ======================================================================
# Mixin: shared game logic
# ======================================================================


class _GameState:
    """Holds game engine and UI state across screens."""

    def __init__(self) -> None:
        settings = load_settings()
        self.api_key: str = os.environ.get("OPENAI_API_KEY") or settings.get("api_key") or ""
        self.base_url: str | None = (
            os.environ.get("OPENAI_BASE_URL") or settings.get("base_url") or None
        )
        self.model: str = os.environ.get("OPENAI_MODEL") or settings.get("model") or DEFAULT_MODEL
        self.temperature: float = float(
            os.environ.get("OPENAI_TEMPERATURE")
            or settings.get("temperature")
            or DEFAULT_TEMPERATURE
        )
        self.engine: GameEngine | None = None
        self.seed_content: str = ""
        self.initialized: bool = False
        self.active_save_uuid: str | None = None
        self.active_save_name: str | None = None


# ======================================================================
# New Save Screen
# ======================================================================


class NewSaveScreen(Screen):
    """Create a new named save, then pick a seed."""

    def compose(self) -> ComposeResult:
        yield Static("\n")
        yield Label("[bold]新建存档[/]", classes="prompt")
        yield Input(placeholder="输入存档名称...", id="save-name")
        yield Button("下一步：选择种子", id="next")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next":
            self._proceed()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._proceed()

    def _proceed(self) -> None:
        name = self.query_one("#save-name", Input).value.strip()
        if not name:
            self.app.notify("请输入存档名称", severity="warning")
            return
        gs: _GameState = self.app.game_state
        gs.active_save_uuid = _new_save_id()
        gs.active_save_name = name
        self.app.push_screen(SeedPickerScreen())


# ======================================================================
# Startup Screen
# ======================================================================


class StartupScreen(Screen):
    """Startup menu."""

    def compose(self) -> ComposeResult:
        yield Static("\n\n\n", classes="spacer")
        yield Static("[bold cyan]U N F R A M E D[/]", id="title")
        yield Static("AI 自举叙事游戏 · 无预设框架\n", classes="subtitle")
        items = [
            ListItem(Label("[bold]新建存档[/]")),
        ]
        if _read_last_played():
            items.append(ListItem(Label("[bold]继续上一个存档[/]")))
        items.append(ListItem(Label("加载存档")))
        items.append(ListItem(Label("存档管理")))
        items.append(ListItem(Label("设置")))
        items.append(ListItem(Label("文档")))
        items.append(ListItem(Label("退出")))
        yield ListView(*items, id="menu")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx == 0:
            self.app.push_screen(NewSaveScreen())
        else:
            has_continue = bool(_read_last_played())
            if has_continue and idx == 1:
                gs: _GameState = self.app.game_state
                uuid_str = _read_last_played()
                if uuid_str:
                    path = _save_path(uuid_str)
                    if os.path.exists(path):
                        gs.engine = GameEngine(
                            api_key=gs.api_key,
                            base_url=gs.base_url,
                            model=gs.model,
                            temperature=gs.temperature,
                        )
                        try:
                            with open(path, encoding="utf-8") as f:
                                state = json.load(f)
                            gs.engine.import_state(state)
                            conv = state.get("conversation", [])
                            if conv:
                                gs.engine.import_conversation(conv)
                            gs.initialized = True
                            gs.active_save_uuid = uuid_str
                            gs.active_save_name = state.get("name", uuid_str)
                            self.app.push_screen(GameScreen())
                            return
                        except (json.JSONDecodeError, OSError) as e:
                            self.app.notify(f"读档失败: {e}", severity="error")
                            return
            # Build action map: skip "continue" when building absolute index
            if has_continue:
                # 0=new, 1=continue, 2=load, 3=save-mgr, 4=settings, 5=docs, 6=quit
                actions = {2: "load", 3: "save-mgr", 4: "settings", 5: "docs", 6: "quit"}
            else:
                # 0=new, 1=load, 2=save-mgr, 3=settings, 4=docs, 5=quit
                actions = {1: "load", 2: "save-mgr", 3: "settings", 4: "docs", 5: "quit"}
            action = actions.get(idx)
            if action == "load":
                self.app.push_screen(LoadScreen())
            elif action == "save-mgr":
                self.app.push_screen(SaveManagerScreen())
            elif action == "settings":
                self.app.push_screen(SettingsScreen())
            elif action == "docs":
                self.app.push_screen(HelpScreen())
            elif action == "quit":
                self.app.exit()


# ======================================================================
# Settings Screen
# ======================================================================


class SettingsScreen(Screen):
    """API key, model, and temperature settings."""

    def compose(self) -> ComposeResult:
        gs: _GameState = self.app.game_state
        yield Static("\n")
        yield Label("[bold]设置[/]", classes="prompt")
        yield Input(placeholder="API Key", value=gs.api_key, id="api-key", password=True)
        yield Input(placeholder="Base URL", value=gs.base_url or "", id="base-url")
        yield Input(placeholder="Model", value=gs.model, id="model")
        yield Input(placeholder="Temperature", value=str(gs.temperature), id="temperature")
        yield Button("保存", id="save-settings")
        yield Button("返回", id="back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        gs: _GameState = self.app.game_state
        if event.button.id == "save-settings":
            gs.api_key = self.query_one("#api-key", Input).value.strip()
            gs.base_url = self.query_one("#base-url", Input).value.strip() or None
            gs.model = self.query_one("#model", Input).value.strip() or DEFAULT_MODEL
            temp_str = self.query_one("#temperature", Input).value.strip()
            try:
                gs.temperature = float(temp_str) if temp_str else DEFAULT_TEMPERATURE
            except ValueError:
                gs.temperature = DEFAULT_TEMPERATURE
            save_settings(
                {
                    "api_key": gs.api_key,
                    "base_url": gs.base_url,
                    "model": gs.model,
                    "temperature": gs.temperature,
                }
            )
            self.app.notify("设置已保存")
            self.app.pop_screen()
        elif event.button.id == "back":
            self.app.pop_screen()


# ======================================================================
# Help Screen
# ======================================================================


class HelpScreen(Screen):
    """Display the player help document."""

    def compose(self) -> ComposeResult:
        yield Static("\n")
        yield Static("[bold cyan]unframed 玩家手册[/]", classes="prompt")
        yield Static("\n")
        yield Static("[bold]什么是 unframed？[/]")
        yield Static("AI 驱动的叙事游戏。没有预设机制——AI 从零构建一切。\n")
        yield Static("[bold]快捷键[/]")
        yield Static("  Ctrl+S  保存  |  Ctrl+L  读档  |  Ctrl+D  删档\n")
        yield Static("[bold]游戏命令（CLI 模式）[/]")
        yield Static("  /save [槽位]   |  /load [槽位]  |  /delete  |  /quit\n")
        yield Static("[bold]给玩家的建议[/]")
        yield Static("  • 主动行动，AI 会根据你的选择推进剧情")
        yield Static("  • 可以随时询问环境信息")
        yield Static("  • 没有预设规则，你觉得合理的事都可以尝试")
        yield Static("  • 想改变方向直接说\n")
        yield Static("完整文档: [dim]docs/HELP.md[/]")
        yield Button("返回", id="back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.pop_screen()


# ======================================================================
# Seed Picker Screen
# ======================================================================


class SeedPickerScreen(Screen):
    """Seed selection."""

    def compose(self) -> ComposeResult:
        seeds = _find_seeds()
        yield Static("\n")
        yield Label("选择种子：", classes="prompt")
        items = [ListItem(Label(f"[bold]《{s['title']}》[/]")) for s in seeds]
        items.append(ListItem(Label("[dim]取消[/]")))
        yield ListView(*items, id="seed_list")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        seeds = _find_seeds()
        idx = event.list_view.index
        if idx < len(seeds):
            try:
                with open(seeds[idx]["path"], encoding="utf-8") as f:
                    self.app.game_state.seed_content = f.read()
                self._start_game()
            except OSError as e:
                self.app.notify(f"无法读取种子: {e}", severity="error")
        else:
            self.app.pop_screen()

    def _start_game(self) -> None:
        gs: _GameState = self.app.game_state
        if not gs.api_key:
            self.app.push_screen(SettingsScreen())
            return
        self.app.push_screen(GameScreen())


# ======================================================================
# Load Screen
# ======================================================================


class LoadScreen(Screen):
    """Load a named save."""

    def compose(self) -> ComposeResult:
        yield Static("\n")
        yield Label("选择存档：", classes="prompt")
        saves = _list_saves()
        if not saves:
            yield Label("[dim]暂无存档[/]")
            yield Button("返回", id="back")
        else:
            items = []
            for s in saves:
                name = s.get("name", s["uuid"])
                info = f"《{name}》 — 第 {s['round']} 轮"
                if s.get("save_time"):
                    info += f"  [{_format_time(s['save_time'])}]"
                if s.get("corrupted"):
                    info += "  [dim]损坏[/]"
                items.append(ListItem(Label(info)))
            items.append(ListItem(Label("[dim]取消[/]")))
            yield ListView(*items, id="load_list")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        saves = _list_saves()
        idx = event.list_view.index
        if idx < len(saves):
            s = saves[idx]
            if s.get("corrupted"):
                self.app.notify("该存档已损坏", severity="error")
                return
            gs: _GameState = self.app.game_state
            gs.engine = GameEngine(
                api_key=gs.api_key, base_url=gs.base_url, model=gs.model, temperature=gs.temperature
            )
            try:
                with open(s["file"], encoding="utf-8") as f:
                    state = json.load(f)
                gs.engine.import_state(state)
                conv = state.get("conversation", [])
                if conv:
                    gs.engine.import_conversation(conv)
                gs.initialized = True
                gs.active_save_uuid = state.get("uuid", s["uuid"])
                gs.active_save_name = state.get("name", s["name"])
                self.app.push_screen(GameScreen())
            except (json.JSONDecodeError, OSError) as e:
                self.app.notify(f"读档失败: {e}", severity="error")
        else:
            self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.pop_screen()


# ======================================================================
# Game Screen
# ======================================================================


class GameScreen(Screen):
    """Main game interface."""

    BINDINGS = [
        ("ctrl+s", "save_menu", "存档"),
        ("ctrl+l", "load_menu", "读档"),
        ("ctrl+d", "delete_menu", "删档"),
        ("escape", "back_to_menu", "返回菜单"),
    ]

    CSS = """
    #narrative {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    #state-panel {
        width: 30%;
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
        content-align: left top;
    }
    #main-area {
        height: 1fr;
    }
    #bottom-bar {
        dock: bottom;
        height: 4;
    }
    #input-bar {
        height: 3;
        padding: 0 1;
    }
    Input {
        width: 1fr;
    }
    Button {
        margin: 0;
    }
    #status-text {
        height: 1;
        content-align: center middle;
        color: $text-disabled;
    }
    #status-text.active {
        color: $success;
    }
    """

    _TOOL_LABELS = {
        "set_var": "正在修改世界状态",
        "get_var": "正在读取变量",
        "pin_var": "正在固定核心变量",
        "unpin_var": "正在释放核心变量",
        "mark_as_end_node": "正在准备结局",
        "set_setting": "正在锁定游戏设定",
        "set_root_plan_node": "正在规划剧情主线",
        "append_plan_node": "正在规划剧情分支",
        "advance_plot": "正在推进剧情",
        "show_var": "正在显示变量",
        "unshow_var": "正在隐藏变量",
        "spawn_agent": "正在创建角色",
        "call_agent": "正在与角色对话",
        "terminate_agent": "正在移除角色",
    }

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, id="header")
        with Horizontal(id="main-area"):
            yield RichLog(id="narrative", markup=True, highlight=True)
            yield RichLog(id="state-panel", markup=True, highlight=True, wrap=True)
        with Vertical(id="bottom-bar"):
            with Horizontal(id="input-bar"):
                yield Input(placeholder="输入你的行动...", id="player-input")
                yield Button("发送", id="send-btn", variant="primary")
            yield Static("就绪", id="status-text")

    def on_mount(self) -> None:
        """Defer engine setup until after mount completes."""
        self.set_timer(0.05, self._setup_engine)

    def _setup_engine(self) -> None:
        """Initialize engine and restore state."""
        gs: _GameState = self.app.game_state

        if not gs.initialized:
            gs.engine = GameEngine(
                api_key=gs.api_key,
                base_url=gs.base_url,
                model=gs.model,
                temperature=gs.temperature,
            )

        engine = gs.engine
        self._engine = engine
        self._running = False
        self._first_round = not gs.initialized

        if gs.initialized:
            self._restore_history(engine)
            self._enable_input()
        else:
            self._show_loading(True)
            log = self.query_one("#narrative", RichLog)
            log.write("[dim]正在展开世界...[/]\n")
            # Auto-send seed after a brief pause
            self.set_timer(0.3, self._auto_send_seed)

    def _enable_input(self) -> None:
        """Focus the input field."""
        self._update_state_panel()
        inp = self.query_one("#player-input", Input)
        inp.disabled = False
        inp.focus()

    def _auto_send_seed(self) -> None:
        """Trigger the first round with seed content."""
        gs: _GameState = self.app.game_state
        if gs.seed_content:
            self._first_round = False
            self._running = True
            self._run_round(gs.seed_content)
            gs.seed_content = ""
        else:
            self._enable_input()

    def _restore_history(self, engine: GameEngine) -> None:
        log = self.query_one("#narrative", RichLog)
        first_user = True
        for msg in engine.export_conversation():
            if msg.get("role") == "user" and msg.get("content"):
                content = msg["content"]
                if "玩家说：" in content:
                    if first_user:
                        first_user = False
                        continue  # skip seed
                    player_said = content.split("玩家说：\"", 1)[1].rsplit("\"", 1)[0]
                    log.write(f"\n[bold green]> {player_said}[/]\n\n")
            elif msg.get("role") == "assistant" and msg.get("content"):
                log.write(Markdown(msg["content"]))

    def _update_state_panel(self) -> None:
        """Update the right panel with player-visible variables."""
        engine = self._engine
        shown = [(n, engine.vars_db[n]) for n in engine.shown_vars if n in engine.vars_db]
        panel = self.query_one("#state-panel", RichLog)
        panel.clear()
        panel.write(Markdown("**角色状态**"))
        if shown:
            for name, entry in shown:
                panel.write(Markdown(f"- **{name}**: {entry.value}"))
                panel.write("")  # blank line between entries
        else:
            panel.write(Markdown("*(空)*"))
        panel.write(Markdown(f"---\n回合 {engine.round_num}"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            self._submit_input()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit_input()

    def action_save_menu(self) -> None:
        self.app.push_screen(SaveManagerScreen(self._engine))

    def action_load_menu(self) -> None:
        self._show_slot_picker("load")

    def action_delete_menu(self) -> None:
        self._show_slot_picker("delete")

    def action_back_to_menu(self) -> None:
        """Auto-save and return to the startup menu."""
        if self._running:
            self.app.notify("请等待当前回合完成", severity="warning")
            return
        # Disable input to prevent race
        inp = self.query_one("#player-input", Input)
        inp.disabled = True
        self._auto_save()
        self.app.pop_screen()

    def _show_slot_picker(self, mode: str) -> None:
        """Show a slot picker for save/load/delete."""
        self.app.push_screen(SlotPickerScreen(mode, self._engine))

    def _submit_input(self) -> None:
        if self._running:
            return

        inp = self.query_one("#player-input", Input)
        text = inp.value.strip()
        if not text:
            return

        inp.value = ""
        self._running = True
        self._show_loading(True)
        self._run_round(text)

    @work(thread=True)
    def _run_round(self, player_input: str) -> None:
        engine = self._engine
        narrative = ""
        user_text = player_input

        try:
            for event in engine.play(player_input):
                if event["type"] == "content":
                    narrative += event["data"]
                elif event["type"] == "tool_call":
                    fn = event["data"]["function"]["name"]
                    label = self._TOOL_LABELS.get(fn, "正在调整世界")
                    self.app.call_from_thread(lambda l=label: self._show_loading(True, l))
                elif event["type"] == "done":
                    pass

            rendered_md = Markdown(narrative) if narrative else None
            end_reason = engine.end_requested
        except Exception as e:
            rendered = ""
            end_reason = None
            err_msg = str(e)

            def _error() -> None:
                log = self.query_one("#narrative", RichLog)
                log.write(f"\n[bold red]╴ 错误: {err_msg}[/]\n")
                self._running = False
                self._show_loading(False)
                self._enable_input()

            self.app.call_from_thread(_error)
            return

        def _update() -> None:
            log = self.query_one("#narrative", RichLog)
            # Don't display seed content as player message
            if len(user_text) < 200:
                log.write(f"\n[bold green]> {user_text}[/]\n\n")
            if rendered_md:
                log.write(rendered_md)

            if end_reason:
                log.write(f"\n[bold yellow]故事结束：{end_reason}[/]\n")
                log.write("[dim]你可以继续输入进行自由探索。[/]\n")

            self._update_state_panel()
            self._running = False
            self._show_loading(False)
            self._auto_save()
            self._enable_input()

        self.app.call_from_thread(_update)

    def _auto_save(self) -> None:
        try:
            gs = self.app.game_state
            uuid_str = gs.active_save_uuid
            if not uuid_str:
                return
            path = _save_path(uuid_str)
            state = self._engine.export_state()
            state["uuid"] = uuid_str
            state["name"] = gs.active_save_name or "未命名"
            state["conversation"] = self._engine.export_conversation()
            state["save_time"] = datetime.datetime.now().isoformat()
            os.makedirs(SAVES_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            _write_last_played(uuid_str)
        except (OSError, TypeError, ValueError) as e:
            self.app.notify(f"自动存档失败: {e}", severity="warning")

    def _show_loading(self, show: bool, status: str = "") -> None:
        """Update the status bar."""
        s = self.query_one("#status-text", Static)
        s.set_class(show, "active")
        if status:
            s.update(f"[bold]{status}...[/]")
        elif show:
            s.update("[bold]AI 正在构思剧情...[/]")
        else:
            s.update("就绪")


# ======================================================================
# Slot Picker (modal overlay for save/load/delete)
# ======================================================================


# ======================================================================
# Save Manager Screen (Ctrl+S: save / delete / rename)
# ======================================================================


class SaveManagerScreen(Screen):
    """Unlimited save manager: Enter=save, Delete=delete, R=rename, new save button."""

    BINDINGS = [
        ("delete", "delete_slot", "删除"),
        ("r", "rename_slot", "重命名"),
        ("escape", "close", "关闭"),
    ]

    def action_close(self) -> None:
        self.app.pop_screen()

    CSS = """
    SaveManagerScreen {
        align: center middle;
    }
    #dialog {
        width: 60;
        height: auto;
        border: thick $primary;
        padding: 1;
        background: $surface;
    }
    .hint {
        color: $text-disabled;
        text-style: dim;
    }
    """

    def __init__(self, engine: GameEngine | None = None) -> None:
        super().__init__()
        self._engine = engine
        self._selectable: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Static("[bold]存档管理[/]", id="dialog-title")

        self._selectable = _list_saves()

        lv_items = []
        current_uuid = self.app.game_state.active_save_uuid
        for s in self._selectable:
            name = s.get("name", s["uuid"])
            info = f"《{name}》 — 第 {s['round']} 轮"
            if s.get("save_time"):
                info += f"  [{_format_time(s['save_time'])}]"
            if s["uuid"] == current_uuid:
                info += "  [bold cyan]◀[/]"
            if s.get("corrupted"):
                info += "  [dim]损坏[/]"
            lv_items.append(ListItem(Label(info)))

        # Empty slot entry for "new save" — always show at top
        lv_items.insert(0, ListItem(Label("[bold]新建存档...[/]")))
        lv_items.append(ListItem(Label("[dim]取消[/]")))
        yield ListView(*lv_items, id="slot-list")
        if self._engine:
            yield Static("[dim]Enter 覆盖保存  |  Delete 删除  |  R 重命名  |  q 关闭[/]", classes="hint")
        else:
            yield Static("[dim]Enter 加载  |  Delete 删除  |  R 重命名  |  q 关闭[/]", classes="hint")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx == 0:
            self.app.push_screen(NewSaveScreen())
            return
        save_idx = idx - 1
        if save_idx < len(self._selectable):
            s = self._selectable[save_idx]
            if s.get("corrupted"):
                self.app.notify("该存档已损坏", severity="error")
                return
            if self._engine:
                self._save_to(s)
                self.app.pop_screen()
            else:
                gs = self.app.game_state
                gs.engine = GameEngine(
                    api_key=gs.api_key,
                    base_url=gs.base_url,
                    model=gs.model,
                    temperature=gs.temperature,
                )
                try:
                    with open(s["file"], encoding="utf-8") as f:
                        state = json.load(f)
                    gs.engine.import_state(state)
                    conv = state.get("conversation", [])
                    if conv:
                        gs.engine.import_conversation(conv)
                    gs.initialized = True
                    gs.active_save_uuid = state.get("uuid", s["uuid"])
                    gs.active_save_name = state.get("name", s["name"])
                    self.app.pop_screen()
                    self.app.push_screen(GameScreen())
                except (json.JSONDecodeError, OSError) as e:
                    self.app.notify(f"读档失败: {e}", severity="error")
        else:
            self.app.pop_screen()

    def action_delete_slot(self) -> None:
        lv = self.query_one("#slot-list", ListView)
        idx = lv.index
        if idx is None or idx <= 0:
            return
        save_idx = idx - 1
        if save_idx >= len(self._selectable):
            return
        s = self._selectable[save_idx]
        path = s["file"]
        if os.path.exists(path):
            os.remove(path)
            self.app.notify(f"已删除《{s.get('name', '未命名')}》")
            self._refresh()

    def action_rename_slot(self) -> None:
        lv = self.query_one("#slot-list", ListView)
        idx = lv.index
        if idx is None or idx <= 0:
            return
        save_idx = idx - 1
        if save_idx >= len(self._selectable):
            return
        s = self._selectable[save_idx]
        if s.get("corrupted"):
            self.app.notify("该存档已损坏，无法重命名", severity="warning")
            return
        self.app.push_screen(RenameScreen(s["uuid"], s["file"]))

    def _save_to(self, save_info: dict) -> None:
        path = save_info["file"]
        os.makedirs(SAVES_DIR, exist_ok=True)
        state = self._engine.export_state()
        state["uuid"] = save_info["uuid"]
        state["name"] = save_info.get("name", "未命名")
        state["conversation"] = self._engine.export_conversation()
        state["save_time"] = datetime.datetime.now().isoformat()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            self.app.notify(f"已保存到《{save_info.get('name', '未命名')}》")
            gs = self.app.game_state
            gs.active_save_uuid = save_info["uuid"]
            gs.active_save_name = save_info.get("name")
            _write_last_played(save_info["uuid"])
        except OSError as e:
            self.app.notify(f"保存失败: {e}", severity="error")

    def _refresh(self) -> None:
        self.app.pop_screen()
        self.app.push_screen(SaveManagerScreen(self._engine))


class RenameScreen(Screen):
    """Inline rename prompt."""

    CSS = """
    RenameScreen {
        align: center middle;
    }
    #dialog {
        width: 50;
        height: auto;
        border: thick $primary;
        padding: 1;
        background: $surface;
    }
    """

    def __init__(self, uuid_str: str, path: str) -> None:
        super().__init__()
        self._uuid = uuid_str
        self._path = path

    def compose(self) -> ComposeResult:
        try:
            with open(self._path, encoding="utf-8") as f:
                meta = json.load(f)
            current = meta.get("name", "")
        except (json.JSONDecodeError, OSError):
            current = ""
        yield Static(f"[bold]重命名存档[/]")
        yield Input(value=current, placeholder="输入新名称...", id="rename-input")
        yield Button("确认", id="confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._save_name()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._save_name()

    def _save_name(self) -> None:
        name = self.query_one("#rename-input", Input).value.strip()
        try:
            with open(self._path, encoding="utf-8") as f:
                state = json.load(f)
            if name:
                state["name"] = name
            else:
                state.pop("name", None)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            self.app.notify(f"已重命名为《{name}》" if name else "已清除名称")
        except (json.JSONDecodeError, OSError) as e:
            self.app.notify(f"重命名失败: {e}", severity="error")
        self.app.pop_screen()


# ======================================================================
# Slot Picker Screen (load / delete via menu)
# ======================================================================


class SlotPickerScreen(Screen):
    """Modal overlay for load/delete via menu (Ctrl+L / Ctrl+D)."""

    CSS = """
    SlotPickerScreen {
        align: center middle;
    }
    #dialog {
        width: 50;
        height: auto;
        border: thick $primary;
        padding: 1;
        background: $surface;
    }
    """

    def __init__(self, mode: str, engine: GameEngine) -> None:
        super().__init__()
        self._mode = mode
        self._engine = engine

    def compose(self) -> ComposeResult:
        labels = {"load": "读档", "delete": "删档"}
        title = labels.get(self._mode, "操作")
        yield Static(f"[bold]{title}[/]", id="dialog-title")

        self._saves = _list_saves()
        if self._saves:
            lv_items = []
            for s in self._saves:
                name = s.get("name", s["uuid"])
                info = f"《{name}》 — 第 {s['round']} 轮"
                if s.get("save_time"):
                    info += f"  [{_format_time(s['save_time'])}]"
                if s.get("corrupted"):
                    info += "  [dim]损坏[/]"
                lv_items.append(ListItem(Label(info)))
            lv_items.append(ListItem(Label("[dim]取消[/]")))
            yield ListView(*lv_items, id="slot-list")
        else:
            yield Label("[dim]暂无存档[/]")
            yield Button("返回", id="close")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx < len(self._saves):
            s = self._saves[idx]

            if self._mode == "load":
                if s.get("corrupted"):
                    self.app.notify("该存档已损坏", severity="error")
                    return
                try:
                    with open(s["file"], encoding="utf-8") as f:
                        state = json.load(f)
                    gs = self.app.game_state
                    gs.engine = GameEngine(
                        api_key=gs.api_key,
                        base_url=gs.base_url,
                        model=gs.model,
                        temperature=gs.temperature,
                    )
                    gs.engine.import_state(state)
                    conv = state.get("conversation", [])
                    if conv:
                        gs.engine.import_conversation(conv)
                    gs.initialized = True
                    gs.active_save_uuid = state.get("uuid", s["uuid"])
                    gs.active_save_name = state.get("name", s["name"])
                    self.app.pop_screen()  # SlotPickerScreen
                    self.app.pop_screen()  # GameScreen
                    self.app.push_screen(GameScreen())
                except (json.JSONDecodeError, OSError) as e:
                    self.app.notify(f"读档失败: {e}", severity="error")

            elif self._mode == "delete":
                try:
                    os.remove(s["file"])
                    self.app.notify(f"已删除《{s.get('name', '未命名')}》")
                except OSError as e:
                    self.app.notify(f"删除失败: {e}", severity="error")
        else:
            # "取消" selected — dismiss the screen
            self.app.pop_screen()
            return

        if self._mode != "load":
            self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.pop_screen()


# ======================================================================
# Main App
# ======================================================================


class UnframedApp(App):
    """Main Textual application."""

    CSS = """
    Screen {
        background: $surface;
    }
    .spacer {
        height: 5;
    }
    #title {
        content-align: center middle;
        text-style: bold;
        color: cyan;
    }
    .subtitle {
        content-align: center middle;
    }
    .prompt {
        content-align: center middle;
        margin: 1 0;
    }
    ListView {
        margin: 0 4;
        height: auto;
        max-height: 12;
    }
    Button {
        margin: 1 4;
    }
    Input {
        margin: 0 4;
    }
    """

    game_state: _GameState

    def __init__(self) -> None:
        super().__init__()
        self.game_state = _GameState()

    def on_ready(self) -> None:
        self.push_screen(StartupScreen())


def main() -> None:
    """Entry point."""
    app = UnframedApp()
    app.run()


if __name__ == "__main__":
    main()
