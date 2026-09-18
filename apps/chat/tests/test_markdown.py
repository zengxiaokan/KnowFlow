from apps.chat.markdown import render_assistant_markdown


def test_render_assistant_markdown_formats_common_markdown():
    output = render_assistant_markdown("这是 **重点**。\n\n- 第一项\n- 第二项\n\n`代码`")

    assert "<strong>重点</strong>" in output
    assert "<ul>" in output
    assert "<code>代码</code>" in output


def test_render_assistant_markdown_removes_unsafe_html_and_urls():
    output = render_assistant_markdown(
        '<script>alert("xss")</script> [危险链接](javascript:alert("xss"))'
    )

    assert "<script" not in output
    assert "javascript:" not in output
