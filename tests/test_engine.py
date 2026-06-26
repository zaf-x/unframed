"""Tests for the unframed game engine."""

from unframed import GameEngine, VarEntry, SYSTEM_PROMPT


def test_imports():
    assert isinstance(GameEngine, type)
    assert isinstance(VarEntry, type)
    assert isinstance(SYSTEM_PROMPT, str)
    assert len(SYSTEM_PROMPT) > 50


def test_engine_creation():
    engine = GameEngine(api_key="test-key")
    assert engine.round_num == 0
    assert engine.var_count == 0
    assert not engine.is_ending
    assert sorted(engine.tools.list_tools()) == [
        "advance_plot", "append_plan_node", "get_var",
        "mark_as_end_node", "pin_var", "set_root_plan_node",
        "set_setting", "set_var", "show_var",
        "spawn_agent", "unpin_var", "unshow_var",
    ]


def test_set_var_create():
    engine = GameEngine(api_key="test-key")
    r = engine._set_var("hp", "100", "生命值")
    assert "已创建" in r
    assert engine.vars_db["hp"].value == "100"
    assert engine.vars_db["hp"].meta == "生命值"
    assert not engine.vars_db["hp"].pinned


def test_set_var_pin():
    engine = GameEngine(api_key="test-key")
    r = engine._set_var("name", "勇者", "角色名", pin=True)
    assert "核心" in r
    assert engine.vars_db["name"].pinned


def test_set_var_update():
    engine = GameEngine(api_key="test-key")
    engine._set_var("hp", "100", "生命值")
    r = engine._set_var("hp", "80")
    assert "已更新" in r
    assert engine.vars_db["hp"].value == "80"


def test_meta_immutable():
    engine = GameEngine(api_key="test-key")
    engine._set_var("hp", "100", "生命值")
    r = engine._set_var("hp", "80", "生命值")
    assert "已更新" in r  # same meta, OK
    r = engine._set_var("hp", "80", "攻击力")
    assert "meta 已锁定" in r  # different meta, rejected
    assert engine.vars_db["hp"].meta == "生命值"


def test_set_var_no_meta():
    engine = GameEngine(api_key="test-key")
    r = engine._set_var("x", "1")
    assert "必须提供 meta" in r


def test_set_var_invalid_name():
    engine = GameEngine(api_key="test-key")
    r = engine._set_var("bad name!", "x", "test")
    assert "只能包含字母" in r


def test_get_var():
    engine = GameEngine(api_key="test-key")
    engine._set_var("hp", "100", "生命值")
    r = engine._get_var("hp")
    assert "hp = 100" in r
    assert "生命值" in r


def test_get_var_nonexistent():
    engine = GameEngine(api_key="test-key")
    r = engine._get_var("nonexistent")
    assert "不存在" in r


def test_pin_var():
    engine = GameEngine(api_key="test-key")
    engine._set_var("hp", "100", "生命值")
    r = engine._pin_var("hp")
    assert "加入核心区" in r
    assert engine.vars_db["hp"].pinned


def test_pin_var_already_pinned():
    engine = GameEngine(api_key="test-key")
    engine._set_var("hp", "100", "生命值", pin=True)
    r = engine._pin_var("hp")
    assert "已在核心区" in r


def test_pin_var_nonexistent():
    engine = GameEngine(api_key="test-key")
    r = engine._pin_var("nope")
    assert "不存在" in r


def test_pin_limit():
    engine = GameEngine(api_key="test-key")
    for i in range(10):
        engine._set_var(f"pin_{i}", str(i), f"var {i}", pin=True)
    r = engine._set_var("overflow", "x", "overflow", pin=True)
    assert "已满" in r


def test_unpin_var():
    engine = GameEngine(api_key="test-key")
    engine._set_var("hp", "100", "生命值", pin=True)
    r = engine._unpin_var("hp")
    assert "释放" in r
    assert not engine.vars_db["hp"].pinned


def test_unpin_var_not_pinned():
    engine = GameEngine(api_key="test-key")
    engine._set_var("hp", "100", "生命值")
    r = engine._unpin_var("hp")
    assert "不在核心区" in r


def test_mark_as_end_node():
    engine = GameEngine(api_key="test-key")
    r = engine._mark_as_end_node("玩家死亡")
    assert "已记录" in r
    assert engine.is_ending
    assert engine.end_requested == "玩家死亡"


def test_build_prompt():
    engine = GameEngine(api_key="test-key")
    engine._set_var("hp", "100", "生命值")
    engine._set_var("name", "勇者", "角色名", pin=True)
    prompt = engine.build_prompt("我向前走。")

    assert "=== 核心区 ===" in prompt
    assert "name: 勇者" in prompt
    assert "=== 活跃区" in prompt
    assert "hp: 100" in prompt
    assert "玩家说：" in prompt
    assert "我向前走。" in prompt


def test_catalog_zone():
    engine = GameEngine(api_key="test-key")
    for i in range(25):
        engine._set_var(f"var_{i}", str(i), f"var {i}")
    prompt = engine.build_prompt("test")
    # 25 vars created, 0 pinned. Last 20 accessed should be active.
    # var_0 through var_4 (5 vars) should be in catalog (least recently accessed)
    assert "=== 目录区（其余变量）" in prompt
    # The active zone and catalog zone should collectively mention all 25
    assert "var_0" in prompt
    assert "var_24" in prompt


def test_export_import():
    engine = GameEngine(api_key="test-key")
    engine._set_var("hp", "100", "生命值", pin=True)
    engine._set_var("mana", "50", "魔法值")
    engine._get_var("mana")

    state = engine.export_state()
    assert state["round"] == 0
    assert "hp" in state["vars"]
    assert "mana" in state["vars"]

    engine2 = GameEngine(api_key="test-key")
    engine2.import_state(state)
    assert engine2.vars_db["hp"].value == "100"
    assert engine2.vars_db["hp"].pinned
    assert engine2.vars_db["mana"].meta == "魔法值"
    assert not engine2.vars_db["mana"].pinned


def test_prompt_round_consistency():
    """Test that prompt assembly works correctly with round tracking."""
    engine = GameEngine(api_key="test-key")
    engine._set_var("hp", "100", "生命值")
    engine._get_var("hp")
    assert engine.vars_db["hp"].last_accessed == 0

    engine.round_num = 5
    engine._get_var("hp")
    assert engine.vars_db["hp"].last_accessed == 5


def test_catalog_hint_on_update():
    """Catalog hint should fire when updating a catalog-zone variable."""
    engine = GameEngine(api_key="test-key")
    # Create 25 vars. First 20 inserted are in active zone (all last_accessed=0).
    # Last 5 (var_20..var_24) are in catalog.
    for i in range(25):
        engine._set_var(f"var_{i}", str(i), f"var {i}")
    # var_24 is in the catalog (last inserted, all have same last_accessed=0)
    r = engine._set_var("var_24", "updated")
    assert "此前在目录区" in r, f"Expected catalog hint, got: {r}"


def test_catalog_hint_not_on_active_var():
    """No catalog hint when updating an active-zone variable."""
    engine = GameEngine(api_key="test-key")
    engine._set_var("hp", "100", "生命值")
    engine._get_var("hp")  # activate it
    engine.round_num = 2
    r = engine._set_var("hp", "80")
    assert "此前在目录区" not in r, f"Unexpected catalog hint: {r}"


def test_conversation_export_import():
    """Conversation can be exported and re-imported."""
    engine = GameEngine(api_key="test-key")
    # Simulate a few rounds of history
    engine.bot.messages.append({"role": "user", "content": "hello"})
    engine.bot.messages.append({"role": "assistant", "content": "hi there"})

    conv = engine.export_conversation()
    assert len(conv) >= 3  # system + user + assistant

    engine2 = GameEngine(api_key="test-key")
    engine2.import_conversation(conv)
    assert len(engine2.bot.messages) == len(conv)


def test_history_trimming():
    """History trimming keeps only the last N user rounds."""
    engine = GameEngine(api_key="test-key", max_history_rounds=3)
    # Simulate 10 rounds of history
    for i in range(10):
        engine.bot.messages.append({"role": "user", "content": f"msg {i}"})
        engine.bot.messages.append({"role": "assistant", "content": f"reply {i}"})

    engine._trim_history()

    # Count user messages — should be at most max_history_rounds
    user_count = sum(
        1 for m in engine.bot.messages if m.get("role") == "user"
    )
    assert user_count <= 3, f"Expected <=3 user msgs, got {user_count}"
    # The most recent user message should be preserved
    assert engine.bot.messages[-2]["content"] == "msg 9"


def test_history_trimming_no_trim_needed():
    """No trimming when history is under the limit."""
    engine = GameEngine(api_key="test-key", max_history_rounds=10)
    for i in range(3):
        engine.bot.messages.append({"role": "user", "content": f"msg {i}"})
        engine.bot.messages.append({"role": "assistant", "content": f"reply {i}"})

    count_before = len(engine.bot.messages)
    engine._trim_history()
    assert len(engine.bot.messages) == count_before


def test_empty_state_prompt():
    """Prompt assembly works with no variables at all."""
    engine = GameEngine(api_key="test-key")
    prompt = engine.build_prompt("hello")
    assert "核心区" in prompt
    assert "活跃区" in prompt
    assert "目录区" in prompt
    assert "玩家说" in prompt


def test_max_active_zone_cap():
    """Active zone caps at MAX_ACTIVE = 20 non-pinned vars."""
    engine = GameEngine(api_key="test-key")
    for i in range(25):
        engine._set_var(f"var_{i}", str(i), f"var {i}")
    prompt = engine.build_prompt("test")

    # Active zone should show exactly 20 vars
    active_section = prompt.split("=== 活跃区")[1].split("=== 目录区")[0]
    var_lines = [l for l in active_section.split("\n") if l.startswith("var_")]
    assert len(var_lines) == 20, f"Expected 20 active vars, got {len(var_lines)}"


def test_pin_limit_on_update():
    """Pin limit also enforced when updating an existing var with pin=True."""
    engine = GameEngine(api_key="test-key")
    for i in range(10):
        engine._set_var(f"pin_{i}", str(i), f"var {i}", pin=True)
    # Create an unpinned var
    engine._set_var("extra", "x", "extra")
    # Try to pin update it — should fail
    r = engine._set_var("extra", "y", pin=True)
    assert "已满" in r


if __name__ == "__main__":
    # Run tests manually
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  PASS  {name}")
            except Exception as e:
                print(f"  FAIL  {name}: {e}")
