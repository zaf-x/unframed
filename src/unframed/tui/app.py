"""
unframed TUI — Textual-based frontend for the AI narrative game.
"""

from __future__ import annotations

import datetime
import json
import os
from typing import List

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
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

AUTOSAVE_PATH = os.path.expanduser("~/.unframed_autosave.json")
SAVES_DIR = os.path.expanduser("~/.unframed_saves")
SEEDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "seeds"))


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
        self.api_key: str = os.environ.get("OPENAI_API_KEY", "")
        self.base_url: str = os.environ.get("OPENAI_BASE_URL", "") or None
        self.model: str = os.environ.get("OPENAI_MODEL", "gpt-4o")
        self.engine: GameEngine | None = None
        self.seed_content: str = ""
        self.initialized: bool = False


# ======================================================================
# Startup Screen
# ======================================================================


class StartupScreen(Screen):
    """Startup menu."""

    def compose(self) -> ComposeResult:
        yield Static("\n\n\n", classes="spacer")
        yield Static("[bold cyan]U N F R A M E D[/]", id="title")
        yield Static("AI 自举叙事游戏 · 无预设框架\n", classes="subtitle")
        yield ListView(
            ListItem(Label("[bold]新游戏[/]")),
            ListItem(Label("加载存档")),
            ListItem(Label("设置")),
            ListItem(Label("退出")),
            id="menu",
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx == 0:
            self.app.push_screen(SeedPickerScreen())
        elif idx == 1:
            self.app.push_screen(LoadScreen())
        elif idx == 2:
            self.app.push_screen(SettingsScreen())
        elif idx == 3:
            self.app.exit()


# ======================================================================
# Settings Screen
# ======================================================================


class SettingsScreen(Screen):
    """API key and model settings."""

    def compose(self) -> ComposeResult:
        gs: _GameState = self.app.game_state
        yield Static("\n")
        yield Label("[bold]设置[/]", classes="prompt")
        yield Input(placeholder="API Key", value=gs.api_key, id="api-key", password=True)
        yield Input(placeholder="Base URL", value=gs.base_url or "", id="base-url")
        yield Input(placeholder="Model", value=gs.model, id="model")
        yield Button("保存", id="save-settings")
        yield Button("返回", id="back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        gs: _GameState = self.app.game_state
        if event.button.id == "save-settings":
            gs.api_key = self.query_one("#api-key", Input).value.strip()
            gs.base_url = self.query_one("#base-url", Input).value.strip() or None
            gs.model = self.query_one("#model", Input).value.strip() or "gpt-4o"
            self.app.notify("设置已保存")
            self.app.pop_screen()
        elif event.button.id == "back":
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
    """Save slot selection."""

    def compose(self) -> ComposeResult:
        yield Static("\n")
        yield Label("选择存档：", classes="prompt")
        items = []
        if os.path.isdir(SAVES_DIR):
            for f in sorted(os.listdir(SAVES_DIR)):
                if f.startswith("slot_") and f.endswith(".json"):
                    slot = f.replace("slot_", "").replace(".json", "")
                    try:
                        with open(os.path.join(SAVES_DIR, f), encoding="utf-8") as fh:
                            meta = json.load(fh)
                        info = f"槽位 {slot} — 第 {meta.get('round', '?')} 轮"
                        if meta.get("save_time"):
                            info += f"  [{_format_time(meta['save_time'])}]"
                        items.append((os.path.join(SAVES_DIR, f), info))
                    except (json.JSONDecodeError, OSError):
                        items.append((os.path.join(SAVES_DIR, f), f"槽位 {slot} — [dim]损坏[/]"))
        if not items:
            yield Label("[dim]暂无存档[/]")
            yield Button("返回", id="back")
        else:
            lv_items = [ListItem(Label(info)) for _, info in items]
            lv_items.append(ListItem(Label("[dim]取消[/]")))
            yield ListView(*lv_items, id="load_list")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        items = []
        if os.path.isdir(SAVES_DIR):
            for f in sorted(os.listdir(SAVES_DIR)):
                if f.startswith("slot_") and f.endswith(".json"):
                    items.append(os.path.join(SAVES_DIR, f))
        if idx < len(items):
            gs: _GameState = self.app.game_state
            gs.engine = GameEngine(api_key=gs.api_key, base_url=gs.base_url, model=gs.model)
            try:
                with open(items[idx], encoding="utf-8") as f:
                    state = json.load(f)
                gs.engine.import_state(state)
                conv = state.get("conversation", [])
                if conv:
                    gs.engine.import_conversation(conv)
                gs.initialized = True
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
    ]

    CSS = """
    #narrative {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    #state-panel {
        width: 30%;
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    #input-bar {
        dock: bottom;
        height: 3;
        padding: 0 1;
    }
    Input {
        width: 1fr;
    }
    #status-text {
        dock: bottom;
        height: 1;
        content-align: center middle;
        color: $text-disabled;
    }
    #status-text.hidden {
        display: none;
    }
    .hidden {
        display: none;
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
    }

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, id="header")
        with Horizontal():
            yield RichLog(id="narrative", markup=True, highlight=True)
            yield Static(id="state-panel")
        yield Static(id="status-text", classes="hidden")
        with Horizontal(id="input-bar"):
            yield Input(placeholder="输入你的行动...", id="player-input")
            yield Button("发送", id="send-btn", variant="primary")

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
        for msg in engine.export_conversation():
            if msg.get("role") == "assistant" and msg.get("content"):
                log.write(Markdown(msg["content"]))

    def _update_state_panel(self) -> None:
        engine = self._engine
        lines: List[str] = []

        lines.append("[bold cyan]角色状态[/]")
        shown = [(n, engine.vars_db[n]) for n in engine.shown_vars if n in engine.vars_db]
        if shown:
            for name, entry in shown:
                lines.append(f"  {name}: {entry.value}")
        else:
            lines.append("  [dim]（空）[/]")

        lines.append("")
        lines.append(f"[dim]回合 {engine.round_num}[/]")

        self.query_one("#state-panel", Static).update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            self._submit_input()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit_input()

    def action_save_menu(self) -> None:
        self._show_slot_picker("save")

    def action_load_menu(self) -> None:
        self._show_slot_picker("load")

    def action_delete_menu(self) -> None:
        self._show_slot_picker("delete")

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
            state = self._engine.export_state()
            state["conversation"] = self._engine.export_conversation()
            state["save_time"] = datetime.datetime.now().isoformat()
            os.makedirs(os.path.dirname(AUTOSAVE_PATH), exist_ok=True)
            with open(AUTOSAVE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.app.notify(f"自动存档失败: {e}", severity="warning")

    def _show_loading(self, show: bool, status: str = "") -> None:
        """Toggle the status indicator."""
        s = self.query_one("#status-text", Static)
        s.set_class(not show, "hidden")
        if status:
            s.update(f"[bold green]{status}...[/]")
        elif show:
            s.update("[bold green]AI 正在构思剧情...[/]")


# ======================================================================
# Slot Picker (modal overlay for save/load/delete)
# ======================================================================


class SlotPickerScreen(Screen):
    """Modal overlay for selecting a save slot."""

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
        labels = {"save": "存档", "load": "读档", "delete": "删档"}
        title = labels.get(self._mode, "操作")
        yield Static(f"[bold]{title}[/]", id="dialog-title")

        items = []
        if os.path.isdir(SAVES_DIR):
            for f in sorted(os.listdir(SAVES_DIR)):
                if f.startswith("slot_") and f.endswith(".json"):
                    slot = f.replace("slot_", "").replace(".json", "")
                    try:
                        with open(os.path.join(SAVES_DIR, f), encoding="utf-8") as fh:
                            meta = json.load(fh)
                        info = f"槽位 {slot} — 第 {meta.get('round', '?')} 轮"
                        if meta.get("save_time"):
                            info += f"  [{_format_time(meta['save_time'])}]"
                        items.append((slot, info))
                    except (json.JSONDecodeError, OSError):
                        items.append((slot, f"槽位 {slot} — [dim]损坏[/]"))

        # Always show empty slots up to 5 for saving
        if self._mode == "save":
            existing = {s for s, _ in items}
            for i in range(1, 6):
                si = str(i)
                if si not in existing:
                    items.append((si, f"槽位 {si} — [dim]空[/]"))
            items.sort(key=lambda x: int(x[0]))

        if items:
            lv_items = [ListItem(Label(info)) for _, info in items]
            lv_items.append(ListItem(Label("[dim]取消[/]")))
            yield ListView(*lv_items, id="slot-list")
        else:
            yield Label("[dim]暂无存档[/]")
            yield Button("返回", id="close")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index

        # Collect all slots
        items = []
        if os.path.isdir(SAVES_DIR):
            for f in sorted(os.listdir(SAVES_DIR)):
                if f.startswith("slot_") and f.endswith(".json"):
                    slot = f.replace("slot_", "").replace(".json", "")
                    items.append(slot)

        if self._mode == "save":
            # For save, show slots 1-5
            items = [str(i) for i in range(1, 6)]

        if idx < len(items):
            slot = items[idx]
            path = os.path.join(SAVES_DIR, f"slot_{slot}.json")

            if self._mode == "save":
                os.makedirs(SAVES_DIR, exist_ok=True)
                state = self._engine.export_state()
                state["conversation"] = self._engine.export_conversation()
                state["save_time"] = datetime.datetime.now().isoformat()
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(state, f, ensure_ascii=False, indent=2)
                    self.app.notify(f"已保存到槽位 {slot}")
                except OSError as e:
                    self.app.notify(f"保存失败: {e}", severity="error")

            elif self._mode == "load":
                try:
                    with open(path, encoding="utf-8") as f:
                        state = json.load(f)
                    gs = self.app.game_state
                    gs.engine = GameEngine(
                        api_key=gs.api_key, base_url=gs.base_url, model=gs.model,
                    )
                    gs.engine.import_state(state)
                    conv = state.get("conversation", [])
                    if conv:
                        gs.engine.import_conversation(conv)
                    gs.initialized = True
                    self.app.pop_screen()  # SlotPickerScreen
                    self.app.pop_screen()  # GameScreen
                    self.app.push_screen(GameScreen())
                except (json.JSONDecodeError, OSError) as e:
                    self.app.notify(f"读档失败: {e}", severity="error")

            elif self._mode == "delete":
                try:
                    os.remove(path)
                    self.app.notify(f"已删除槽位 {slot}")
                except OSError as e:
                    self.app.notify(f"删除失败: {e}", severity="error")

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
