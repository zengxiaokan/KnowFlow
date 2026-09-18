from types import SimpleNamespace

from apps.chat.tasks import select_context_chunks


def candidate(document_id, title, ordinal):
    return SimpleNamespace(
        document_version=SimpleNamespace(
            document_id=document_id,
            document=SimpleNamespace(title=title),
        ),
        ordinal=ordinal,
    )


def test_context_selection_uses_more_than_one_document_before_repeating():
    # This mirrors the regression: four introduction chunks ranked ahead of the
    # Java basics page, which used to keep the requested chapter out of context.
    candidates = [candidate(1, "Java面试题介绍", ordinal) for ordinal in range(4)]
    candidates += [candidate(2, "Java基础面试篇", ordinal) for ordinal in range(4)]

    selected = select_context_chunks(candidates, limit=4)

    assert [chunk.document_version.document.title for chunk in selected] == [
        "Java面试题介绍",
        "Java基础面试篇",
        "Java面试题介绍",
        "Java基础面试篇",
    ]
