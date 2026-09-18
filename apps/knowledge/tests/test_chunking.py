from apps.knowledge.chunking import normalize_text, split_into_chunks


def test_normalize_text_collapses_unneeded_whitespace():
    assert normalize_text("A   B\r\n\r\n\r\nC") == "A B\n\nC"


def test_split_chunks_keeps_heading_and_unique_ordinals(settings):
    settings.CHUNK_SIZE = 30
    settings.CHUNK_OVERLAP = 5
    chunks = split_into_chunks(
        "# 标题\n\n第一段内容足够长，需要拆分。\n\n第二段内容也足够长，需要继续拆分。"
    )
    assert chunks
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.heading == "标题" for chunk in chunks)
    assert all(chunk.content for chunk in chunks)


def test_pdf_page_marker_keeps_following_markdown_title_as_heading():
    chunks = split_into_chunks("--- 第 12 页 ---\n# Java基础面试篇\n\n说一下 Java 的特点。")

    assert chunks[0].heading == "Java基础面试篇"
    assert chunks[0].content == "说一下 Java 的特点。"
