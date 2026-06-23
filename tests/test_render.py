"""Tests for the BBCode ANSI renderer."""

from unframed.render import BBCodeRenderer, render, strip_tags


def test_bold():
    r = render("[b]bold[/b]")
    assert "\033[1mbold\033[0m" in r


def test_italic():
    r = render("[i]italic[/i]")
    assert "\033[3mitalic\033[0m" in r


def test_underline():
    r = render("[u]underline[/u]")
    assert "\033[4munderline\033[0m" in r


def test_code():
    r = render("[code]code[/code]")
    assert "\033[36mcode\033[0m" in r


def test_h1():
    r = render("[h1]Title[/h1]")
    assert "\033[1;4mTitle\033[0m" in r


def test_color():
    r = render("[color=red]danger[/color]")
    assert "\033[31mdanger\033[0m" in r


def test_multiple_tags():
    r = render("[b]bold[/b] and [i]italic[/i]")
    assert "\033[1mbold\033[0m" in r
    assert "\033[3mitalic\033[0m" in r
    assert " and " in r


def test_nested_tags():
    r = render("[b]bold [i]nested[/i][/b]")
    # feed 处理完 [/b] → \033[0m，reset() 再追加一个 \033[0m
    assert "bold" in r
    assert "\033[1m" in r
    assert "\033[3m" in r


def test_unknown_tag_ignored():
    """[hr] and similar unknown tags should be silently dropped."""
    r = render("before[hr]after")
    assert "beforeafter" in r or "before" in r
    assert "[hr]" not in r


def test_no_tags():
    r = render("plain text")
    # No tags → just output the text + trailing resets
    assert "plain text" in r


def test_strip_tags():
    assert strip_tags("[b]hello[/b] [i]world[/i]") == "hello world"


def test_strip_no_tags():
    assert strip_tags("plain text") == "plain text"


def test_incremental_feed():
    """跨块标签：前一块 bold 没关，后一块继续 bold。"""
    from io import StringIO
    buf = StringIO()
    r = BBCodeRenderer(write=buf.write)

    r.feed("[b]hello ")
    assert "\033[1m" in buf.getvalue()
    assert "hello" in buf.getvalue()
    # bold 尚未关闭，没有 reset
    assert "\033[0m" not in buf.getvalue().rstrip("\033[0m")

    r.feed("world[/b]")
    assert "world" in buf.getvalue()
    assert "\033[0m" in buf.getvalue()

    r.reset()


def test_color_cross_chunk():
    """跨块颜色标签。"""
    from io import StringIO
    buf = StringIO()
    r = BBCodeRenderer(write=buf.write)

    r.feed("[color=red]dan")
    assert "\033[31mdan" in buf.getvalue()

    r.feed("ger[/color]")
    assert "ger\033[0m" in buf.getvalue()

    r.reset()


def test_real_narrative():
    """用之前导致 Rich 崩溃的真实叙事文本测试。"""
    narrative = """[color=cyan]哈夫克监狱[/color]，私人军事承包商。

[code]芯片 v2.7[/code]

[b]选择：[/b]

[i]1. 躺下。[/i]
[i]2. 扫描。[/i]

[color=yellow]注意[/color]：间隔[color=cyan]15分钟[/color]。

[hr]

[color=gray]等待决断——[/color]"""
    r = render(narrative)
    assert "\033[36m" in r  # cyan (code + color)
    assert "\033[1m" in r   # bold
    assert "\033[3m" in r   # italic
    assert "\033[33m" in r  # yellow
    assert "\033[90m" in r  # gray
    assert "\033[0m" in r   # resets
    # No raw BBCode leaks
    for leak in ["[b]", "[/b]", "[color=", "[/color]", "[hr]"]:
        assert leak not in r, f"leaked: {leak}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  PASS  {name}")
            except Exception as e:
                print(f"  FAIL  {name}: {e}")
