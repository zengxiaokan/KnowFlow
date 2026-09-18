import re
from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class ChunkPayload:
    ordinal: int
    content: str
    heading: str


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    # PDF extraction adds page markers.  Make them paragraph boundaries so a Markdown
    # title on the following line is kept as the chunk heading rather than merged into text.
    text = re.sub(r"(?m)^(--- 第 \d+ 页 ---)\s*", r"\1\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_chunks(text: str) -> list[ChunkPayload]:
    text = normalize_text(text)
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    sections: list[tuple[str, str]] = []
    heading = ""
    for paragraph in paragraphs:
        if _is_heading(paragraph):
            heading = paragraph.lstrip("#").strip()
            continue
        sections.append((heading, paragraph))

    chunks: list[ChunkPayload] = []
    buffer = ""
    buffer_heading = ""
    for section_heading, paragraph in sections:
        candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if buffer and len(candidate) > settings.CHUNK_SIZE:
            chunks.append(ChunkPayload(len(chunks), buffer, buffer_heading))
            overlap = buffer[-settings.CHUNK_OVERLAP :]
            buffer = f"{overlap}\n\n{paragraph}".strip()
            buffer_heading = section_heading or buffer_heading
        elif not buffer and len(paragraph) > settings.CHUNK_SIZE:
            for piece in _split_long_paragraph(paragraph):
                chunks.append(ChunkPayload(len(chunks), piece, section_heading))
            buffer = ""
            buffer_heading = ""
        else:
            buffer = candidate
            buffer_heading = section_heading or buffer_heading

    if buffer:
        chunks.append(ChunkPayload(len(chunks), buffer, buffer_heading))
    return chunks


def _is_heading(paragraph: str) -> bool:
    return paragraph.startswith("#") or (
        len(paragraph) <= 48 and not paragraph.endswith(("。", "！", "？", ".", "!", "?"))
    )


def _split_long_paragraph(paragraph: str) -> list[str]:
    pieces = []
    start = 0
    while start < len(paragraph):
        end = min(start + settings.CHUNK_SIZE, len(paragraph))
        if end < len(paragraph):
            punctuation = max(paragraph.rfind(mark, start, end) for mark in "。！？；;,. ")
            if punctuation > start + settings.CHUNK_SIZE // 2:
                end = punctuation + 1
        pieces.append(paragraph[start:end].strip())
        if end >= len(paragraph):
            break
        start = max(end - settings.CHUNK_OVERLAP, start + 1)
    return [piece for piece in pieces if piece]
