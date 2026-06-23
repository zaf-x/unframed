"""Tests for setting and plot planning features."""

from unframed import GameEngine


def _make_engine():
    return GameEngine(api_key="test")


def test_set_setting():
    e = _make_engine()
    r = e._set_setting("世界观：赛博朋克\n时间：2087年")
    assert "已锁定" in r
    assert e.setting == "世界观：赛博朋克\n时间：2087年"


def test_set_setting_immutable():
    e = _make_engine()
    e._set_setting("世界观 X")
    r = e._set_setting("世界观 Y")
    assert "不可更改" in r
    assert e.setting == "世界观 X"


def test_set_root_plan_node():
    e = _make_engine()
    r = e._set_root_plan_node("主线剧情")
    assert r is not None
    assert e.plot_root is not None
    assert e.plot_current is not None
    assert e.plot_root.name == "主线剧情"


def test_set_root_plan_node_twice():
    e = _make_engine()
    e._set_root_plan_node("第一版")
    r = e._set_root_plan_node("第二版")
    assert "已存在" in r


def test_append_plan_node():
    e = _make_engine()
    root_id = e._set_root_plan_node("Root")
    r = e._append_plan_node(root_id, "Child")
    assert "创建成功" in r
    assert "层级：1" in r
    assert len(e.plot_root.children) == 1


def test_append_plan_node_invalid_father():
    e = _make_engine()
    r = e._append_plan_node("999", "Ghost")
    assert "未找到" in r


def test_advance_plot():
    e = _make_engine()
    root_id = e._set_root_plan_node("Root")
    child_id = e.plot_root.children[0].node_id if e.plot_root.children else None
    # Create child
    e._append_plan_node(root_id, "Step 1")
    child_id = e.plot_root.children[0].node_id
    r = e._advance_plot(child_id)
    assert "推进" in r
    assert e.plot_current.node_id == child_id


def test_advance_plot_invalid_target():
    e = _make_engine()
    e._set_root_plan_node("Root")
    r = e._advance_plot("999")
    assert "未找到" in r


def test_advance_plot_wrong_level():
    e = _make_engine()
    root_id = e._set_root_plan_node("Root")
    r = e._advance_plot(root_id)
    assert "必须为 1" in r


def test_advance_plot_not_direct_child():
    """Cannot advance to a node that is not a direct child of the current node."""
    e = _make_engine()
    e._set_root_plan_node("Root")
    e._append_plan_node(e.plot_root.node_id, "A")
    a_id = e.plot_root.children[0].node_id
    e._append_plan_node(a_id, "A1")
    a1_id = e.plot_root.children[0].children[0].node_id
    # Root (level 0) → advance to A1 (level 2) — wrong level AND not direct child
    r = e._advance_plot(a1_id)
    assert "不是当前节点的直接子节点" in r or "必须为 1" in r


def test_prune_on_advance():
    e = _make_engine()
    root_id = e._set_root_plan_node("Root")
    e._append_plan_node(root_id, "A")
    e._append_plan_node(root_id, "B")
    # Advance to A → B should be pruned
    a_id = e.plot_root.children[0].node_id
    e._append_plan_node(a_id, "A1")
    e._advance_plot(a_id)
    assert len(e.plot_root.children) == 1  # B pruned
    assert e.plot_root.children[0].name == "A"


def test_build_prompt_with_setting():
    e = _make_engine()
    e._set_setting("地点：月球基地")
    prompt = e.build_prompt("hello")
    assert "[设定]" in prompt
    assert "地点：月球基地" in prompt


def test_build_prompt_with_plot():
    e = _make_engine()
    e._set_root_plan_node("冒险")
    prompt = e.build_prompt("hello")
    assert "=== 剧情规划树" in prompt
    assert "当前节点" in prompt


def test_export_import_with_setting():
    e = _make_engine()
    e._set_setting("年代：1984")
    e._set_root_plan_node("Start")
    state = e.export_state()
    assert state["setting"] == "年代：1984"

    e2 = _make_engine()
    e2.import_state(state)
    assert e2.setting == "年代：1984"
    assert e2.plot_root is not None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  PASS  {name}")
            except Exception as e:
                print(f"  FAIL  {name}: {e}")
                import traceback
                traceback.print_exc()
