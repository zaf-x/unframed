"""
unframed TUI — Textual-based frontend for the AI narrative game.

Run with::

    unframed --tui
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import sys
from typing import Dict, List, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    RichLog,
    Static,
)

from ..engine import GameEngine
from ..render import render

# Paths
AUTOSAVE_PATH = os.path.expanduser("~/.unframed_autosave.json")
SAVES_DIR = os.path.expanduser("~/.unframed_saves")
SEEDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "seeds"))


# ======================================================================
# Helpers
# ======================================================================

def _find_seeds() -> List[dict]:
    """Scan seeds directory for .json seed files."""
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


# ======================================================================
# Screens
# ======================================================================


class StartupScreen(Screen):
    """Startup menu: new game or load."""

    def compose(self) -> ComposeResult:
        yield Static("\n\n\n", classes="spacer")
        yield Static("[bold cyan]U N F R A M E D[/]", id="title")
        yield Static("AI 自举叙事游戏 · 无预设框架\n", classes="subtitle")
        yield Label("启动选项：", classes="prompt")
        yield ListView(
            ListItem(Label("[bold]新游戏[/]")),
            ListItem(Label("加载存档")),
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
            self.app.exit()


class SeedPickerScreen(Screen):
    """Seed selection screen."""

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
            path = seeds[idx]["path"]
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                self.app.seed_content = content
                self.app.push_screen(GameScreen())
            except OSError as e:
                self.app.notify(f"无法读取种子: {e}", severity="error")
        else:
            self.app.pop_screen()


class LoadScreen(Screen):
    """Save slot selection screen."""

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
                        items.append(ListItem(Label(f"槽位 {slot} — 第 {meta.get('round', '?')} 轮")))
                    except (json.JSONDecodeError, OSError):
                        items.append(ListItem(Label(f"槽位 {slot} — [dim]损坏[/]")))
        items.append(ListItem(Label("[dim]取消[/]")))
        yield ListView(*items, id="load_list")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        items = []
        if os.path.isdir(SAVES_DIR):
            for f in sorted(os.listdir(SAVES_DIR)):
                if f.startswith("slot_") and f.endswith(".json"):
                    items.append(os.path.join(SAVES_DIR, f))
        if idx < len(items):
            self.app.load_path = items[idx]
            self.app.push_screen(GameScreen())
        else:
            self.app.pop_screen()


# ======================================================================
# Game Screen
# ======================================================================


class GameScreen(Screen):
    """Main game interface."""

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
    #loading {
        dock: bottom;
        height: 1;
        display: none;
    }
    #loading.-visible {
        display: block;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            yield RichLog(id="narrative", markup=True, highlight=True)
            yield Static(id="state-panel")
        yield LoadingIndicator(id="loading")
        with Horizontal(id="input-bar"):
            yield Input(placeholder="输入你的行动...", id="player-input")
            yield Button("发送", id="send-btn")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the game engine on mount."""
        engine = GameEngine(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            base_url=os.environ.get("OPENAI_BASE_URL"),
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        )

        # Load from save if provided
        if hasattr(self.app, "load_path") and self.app.load_path:
            path = self.app.load_path
            try:
                with open(path, encoding="utf-8") as f:
                    state = json.load(f)
                engine.import_state(state)
                conv = state.get("conversation", [])
                if conv:
                    engine.import_conversation(conv)
                self.app.notify(f"已读档：第 {engine.round_num} 轮")
                self._restore_history(engine)
            except (json.JSONDecodeError, OSError) as e:
                self.app.notify(f"读档失败: {e}", severity="error")

        # Seed content from picker
        seed_content = getattr(self.app, "seed_content", None)

        self._engine = engine
        self._seed_content = seed_content
        self._first_round = True
        self._running = False

        self._update_state_panel()
        self.query_one("#player-input", Input).focus()

    def _restore_history(self, engine: GameEngine) -> None:
        """Restore previous narrative to the log."""
        narrative = self.query_one("#narrative", RichLog)
        for msg in engine.export_conversation():
            if msg.get("role") == "assistant" and msg.get("content"):
                narrative.write(render(msg["content"]) + "\n")

    def _update_state_panel(self) -> None:
        """Refresh the state sidebar."""
        engine = self._engine
        lines = []

        # Core zone
        lines.append("[bold cyan]核心区[/]")
        pinned = [(n, e) for n, e in engine.vars_db.items() if e.pinned]
        if pinned:
            for name, entry in pinned:
                lines.append(f"  {name}: {entry.value}")
        else:
            lines.append("  [dim]（空）[/]")

        # Plot tree
        if engine.plot_root:
            lines.append("")
            lines.append("[bold cyan]剧情树[/]")
            if engine.plot_current:
                lines.append(f"  当前: {engine.plot_current.name}")
            lines.append(f"  节点数: {engine.var_count}")

        lines.append("")
        lines.append(f"[dim]回合 {engine.round_num}[/]")

        self.query_one("#state-panel", Static).update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle send button."""
        if event.button.id == "send-btn":
            self._submit_input()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in input field."""
        self._submit_input()

    def _submit_input(self) -> None:
        """Process player input in a worker thread."""
        if self._running:
            return

        inp = self.query_one("#player-input", Input)
        text = inp.value.strip()
        if not text:
            return

        # Seed: auto-send on first round
        if self._first_round and self._seed_content:
            text = self._seed_content
            self._seed_content = None
            inp.value = ""
        else:
            inp.value = ""

        self._first_round = False
        self._running = True
        self._show_loading(True)

        # Run game round in thread
        self._run_round(text)

    @work(thread=True)
    def _run_round(self, player_input: str) -> None:
        """Execute a game round in a background thread."""
        engine = self._engine
        narrative = ""
        narrative_rendered = ""

        for event in engine.play(player_input):
            if event["type"] == "content":
                narrative += event["data"]
            elif event["type"] == "done":
                if narrative:
                    narrative_rendered = render(narrative)

        # Update UI from thread
        def _update() -> None:
            nonlocal narrative_rendered
            log = self.query_one("#narrative", RichLog)
            if narrative_rendered:
                log.write(narrative_rendered + "\n")
            self._update_state_panel()
            self._running = False
            self._show_loading(False)
            self.query_one("#player-input", Input).focus()

            # Auto-save
            try:
                state = engine.export_state()
                state["conversation"] = engine.export_conversation()
                state["save_time"] = datetime.datetime.now().isoformat()
                os.makedirs(os.path.dirname(AUTOSAVE_PATH), exist_ok=True)
                with open(AUTOSAVE_PATH, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
            except OSError:
                pass

        self.app.call_from_thread(_update)

    def _show_loading(self, show: bool) -> None:
        """Toggle the loading indicator."""
        loading = self.query_one("#loading", LoadingIndicator)
        loading.set_class(show, "-visible")


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
    """

    seed_content: str = ""
    load_path: str = ""

    def __init__(self) -> None:
        super().__init__()
        self.seed_content = ""
        self.load_path = ""

    def on_ready(self) -> None:
        self.push_screen(StartupScreen())


def main() -> None:
    """Entry point for the TUI."""
    app = UnframedApp()
    app.run()


if __name__ == "__main__":
    main()
