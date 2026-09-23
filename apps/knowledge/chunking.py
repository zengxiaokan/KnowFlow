import re
from dataclasses import dataclass

from django.conf import settings

PAGE_MARKER_RE = re.compile(r"^---\s*第\s*(\d+)\s*页\s*---$")
MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+\S+")
NUMBERED_HEADING_RE = re.compile(
    r"^(?:第\s*[一二三四五六七八九十百千万0-9]+\s*[章节篇部分]|"
    r"\d+(?:[.．、]\d+)*[.．、)]\s+).{1,80}$"
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])(?:\s+|(?=\S))|\n+")
COMPARISON_LABELS = {"特性", "指标", "对比项", "对比维度", "比较项", "比较维度"}
COMPARISON_COLUMN_RE = re.compile(r"[A-Za-z0-9]")
TABLE_PUNCTUATION = "。！？!?；;，,：:（）()"


@dataclass(frozen=True)
class ChunkPayload:
    ordinal: int
    content: str
    heading: str
    page_start: int | None = None
    page_end: int | None = None


@dataclass(frozen=True)
class _TextUnit:
    content: str
    heading: str
    page_start: int | None
    page_end: int | None
    kind: str = "text"


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    # Keep PDF page markers as standalone paragraphs so page metadata can be recovered.
    text = re.sub(r"(?m)^\s*(---\s*第\s*\d+\s*页\s*---)\s*", r"\n\n\1\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_chunks(text: str) -> list[ChunkPayload]:
    units = _extract_units(text)
    if not units:
        return []

    chunks: list[ChunkPayload] = []
    pending: list[_TextUnit] = []
    target_size = max(1, int(settings.CHUNK_SIZE))
    max_size = max(target_size, int(getattr(settings, "CHUNK_MAX_SIZE", target_size)))

    def emit(units_to_emit: list[_TextUnit]) -> None:
        if not units_to_emit:
            return
        content = _join_units(units_to_emit)
        if content:
            chunks.append(
                _payload_from_units(
                    ordinal=len(chunks), content=content, units=units_to_emit
                )
            )

    for unit in units:
        if unit.kind == "comparison":
            emit(pending)
            pending = []
            if len(unit.content) <= max_size:
                emit([unit])
            else:
                for piece in _split_long_text(unit.content, max_size=max_size):
                    chunks.append(
                        ChunkPayload(
                            ordinal=len(chunks),
                            content=piece,
                            heading=unit.heading,
                            page_start=unit.page_start,
                            page_end=unit.page_end,
                        )
                    )
            continue

        if len(unit.content) > max_size:
            emit(pending)
            pending = []
            for piece in _split_long_text(unit.content, max_size=max_size):
                chunks.append(
                    ChunkPayload(
                        ordinal=len(chunks),
                        content=piece,
                        heading=unit.heading,
                        page_start=unit.page_start,
                        page_end=unit.page_end,
                    )
                )
            continue

        candidate = _join_units([*pending, unit])
        if pending and len(candidate) > target_size:
            emit(pending)
            overlap = _overlap_unit(pending)
            pending = [overlap] if overlap else []
            if len(_join_units([*pending, unit])) > max_size:
                pending = [unit]
            else:
                pending.append(unit)
        else:
            pending.append(unit)

    emit(pending)
    return chunks


def _extract_units(text: str) -> list[_TextUnit]:
    paragraphs = [paragraph.strip() for paragraph in normalize_text(text).split("\n\n")]
    units: list[_TextUnit] = []
    heading = ""
    current_page: int | None = None
    for paragraph in paragraphs:
        if not paragraph:
            continue
        page_match = PAGE_MARKER_RE.match(paragraph)
        if page_match:
            current_page = int(page_match.group(1))
            continue
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        prose_lines: list[str] = []

        line_index = 0
        while line_index < len(lines):
            line = lines[line_index]
            if _is_heading(line):
                _append_text_units(units, prose_lines, heading=heading, page=current_page)
                prose_lines.clear()
                heading = _clean_heading(line)
                line_index += 1
                continue

            comparison = _extract_comparison_block(
                lines, line_index, heading=heading, page=current_page
            )
            if comparison:
                comparison_unit, consumed = comparison
                comparison_intro = " ".join(prose_lines).strip()
                if (
                    not comparison_intro
                    and units
                    and units[-1].kind == "text"
                    and units[-1].heading == heading
                    and units[-1].page_start == current_page
                    and _is_comparison_introduction(units[-1].content)
                ):
                    comparison_intro = units.pop().content
                if _is_comparison_introduction(comparison_intro):
                    prose_lines.clear()
                    comparison_unit = _TextUnit(
                        content=f"{comparison_intro}\n{comparison_unit.content}",
                        heading=comparison_unit.heading,
                        page_start=comparison_unit.page_start,
                        page_end=comparison_unit.page_end,
                        kind=comparison_unit.kind,
                    )
                else:
                    _append_text_units(units, prose_lines, heading=heading, page=current_page)
                    prose_lines.clear()
                units.append(comparison_unit)
                line_index += consumed
                continue

            prose_lines.append(line)
            line_index += 1
        _append_text_units(units, prose_lines, heading=heading, page=current_page)
        prose_lines.clear()
    return units


def _append_text_units(
    units: list[_TextUnit], lines: list[str], *, heading: str, page: int | None
) -> None:
    if not lines:
        return
    for sentence in _split_sentences(" ".join(lines)):
        units.append(
            _TextUnit(
                content=sentence,
                heading=heading,
                page_start=page,
                page_end=page,
            )
        )


def _is_heading(paragraph: str) -> bool:
    if "\n" in paragraph:
        return False
    if MARKDOWN_HEADING_RE.match(paragraph):
        return True
    if NUMBERED_HEADING_RE.match(paragraph):
        return True
    return False


def _clean_heading(paragraph: str) -> str:
    return paragraph.lstrip("#").strip()


def _extract_comparison_block(
    lines: list[str], start: int, *, heading: str, page: int | None
) -> tuple[_TextUnit, int] | None:
    if lines[start] not in COMPARISON_LABELS:
        return None

    columns: list[str] = []
    cursor = start + 1
    while cursor < len(lines) and len(columns) < 8:
        candidate = lines[cursor]
        if not _looks_like_comparison_column(candidate):
            break
        columns.append(candidate)
        cursor += 1
    if len(columns) < 2:
        return None

    rows: list[tuple[str, list[str]]] = []
    while cursor < len(lines):
        label = lines[cursor]
        values = lines[cursor + 1 : cursor + 1 + len(columns)]
        if not _looks_like_table_label(label) or len(values) != len(columns):
            break
        if any(_is_heading(value) or PAGE_MARKER_RE.match(value) for value in values):
            break
        rows.append((label, values))
        cursor += 1 + len(columns)
    if not rows:
        return None

    lines_out = [
        f"对比项：{lines[start]}",
        "对比对象：" + "、".join(columns),
    ]
    for label, values in rows:
        pairs = "；".join(
            f"{column}={value}" for column, value in zip(columns, values, strict=True)
        )
        lines_out.append(f"{label}：{pairs}")
    return (
        _TextUnit(
            content="\n".join(lines_out),
            heading=heading,
            page_start=page,
            page_end=page,
            kind="comparison",
        ),
        cursor - start,
    )


def _looks_like_comparison_column(line: str) -> bool:
    return (
        bool(line)
        and len(line) <= 40
        and bool(COMPARISON_COLUMN_RE.search(line))
        and not any(mark in line for mark in TABLE_PUNCTUATION)
    )


def _looks_like_table_label(line: str) -> bool:
    return bool(line) and len(line) <= 32 and not any(mark in line for mark in TABLE_PUNCTUATION)


def _is_comparison_introduction(text: str) -> bool:
    return bool(text) and len(text) <= 160 and any(word in text for word in ("对比", "比较"))


def _split_sentences(paragraph: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", paragraph).strip()
    return [piece.strip() for piece in SENTENCE_SPLIT_RE.split(normalized) if piece.strip()]


def _split_long_text(text: str, *, max_size: int) -> list[str]:
    pieces: list[str] = []
    start = 0
    overlap = max(0, int(getattr(settings, "CHUNK_OVERLAP", 0)))
    while start < len(text):
        end = min(start + max_size, len(text))
        if end < len(text):
            boundary = max(text.rfind(mark, start, end) for mark in "。！？；;,. ")
            if boundary > start + max_size // 2:
                end = boundary + 1
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return pieces


def _join_units(units: list[_TextUnit]) -> str:
    return "\n\n".join(unit.content for unit in units if unit.content).strip()


def _overlap_unit(units: list[_TextUnit]) -> _TextUnit | None:
    overlap = max(0, int(getattr(settings, "CHUNK_OVERLAP", 0)))
    if overlap == 0:
        return None
    content = _join_units(units)
    if not content:
        return None
    last = units[-1]
    return _TextUnit(
        content=content[-overlap:].strip(),
        heading=last.heading,
        page_start=last.page_end,
        page_end=last.page_end,
    )


def _payload_from_units(*, ordinal: int, content: str, units: list[_TextUnit]) -> ChunkPayload:
    pages = [page for unit in units for page in (unit.page_start, unit.page_end) if page]
    heading = next((unit.heading for unit in reversed(units) if unit.heading), "")
    return ChunkPayload(
        ordinal=ordinal,
        content=content,
        heading=heading,
        page_start=min(pages) if pages else None,
        page_end=max(pages) if pages else None,
    )
