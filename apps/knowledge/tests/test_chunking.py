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


def test_pdf_page_markers_become_chunk_page_ranges_and_leave_content(settings):
    settings.CHUNK_SIZE = 34
    settings.CHUNK_MAX_SIZE = 64
    settings.CHUNK_OVERLAP = 8
    chunks = split_into_chunks(
        "--- 第 3 页 ---\n# 介绍\n\n第一句说明项目背景。第二句说明使用场景。"
        "\n\n--- 第 4 页 ---\n第三句说明部署方式。第四句说明运行结果。"
    )

    assert chunks
    assert all("--- 第" not in chunk.content for chunk in chunks)
    assert chunks[0].page_start == 3
    assert any(chunk.page_start == 4 for chunk in chunks)
    assert all(len(chunk.content) <= settings.CHUNK_MAX_SIZE for chunk in chunks)


def test_sentence_aware_chunks_prefer_sentence_boundaries(settings):
    settings.CHUNK_SIZE = 36
    settings.CHUNK_MAX_SIZE = 70
    settings.CHUNK_OVERLAP = 6
    chunks = split_into_chunks(
        "# 说明\n\n这是第一句内容，用来介绍系统。"
        "这是第二句内容，用来介绍数据。"
        "这是第三句内容，用来介绍检索。"
    )

    assert len(chunks) > 1
    assert all(chunk.content[-1] in "。！？!?；;" for chunk in chunks[:-1])


def test_plain_short_sentence_is_not_mistaken_for_heading():
    chunks = split_into_chunks("系统可以快速检索\n\n这是正文内容。")

    assert chunks[0].heading == ""
    assert "系统可以快速检索" in chunks[0].content


def test_comparison_table_is_kept_separate_from_following_explanation(settings):
    settings.CHUNK_SIZE = 180
    settings.CHUNK_MAX_SIZE = 260
    settings.CHUNK_OVERLAP = 20
    chunks = split_into_chunks(
        "# 消息队列怎么选型？\n"
        "Kafka、ActiveMQ、RabbitMQ、RocketMQ来进行不同维度对比。\n"
        "\n特性\nActiveMQ\nRabbitMQ\nRocketMQ\nKafka\n"
        "单机吞吐量\n万级\n万级\n10 万级\n10 万级\n"
        "时效性\n毫秒级\n微秒级\n毫秒级\n毫秒级\n"
        "选型的时候，我们需要根据业务场景进行选择。"
    )

    comparison_chunks = [chunk for chunk in chunks if "ActiveMQ" in chunk.content]
    assert len(comparison_chunks) == 1
    assert comparison_chunks[0].heading == "消息队列怎么选型？"
    assert "单机吞吐量" in comparison_chunks[0].content
    assert "时效性" in comparison_chunks[0].content
    assert "选型的时候" not in comparison_chunks[0].content
