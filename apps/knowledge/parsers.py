from pathlib import Path

import pymupdf
from django.conf import settings
from docx import Document as WordDocument

from .exceptions import ScannedPdfError, UnsupportedDocumentError

SUPPORTED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx", ".md": "markdown", ".markdown": "markdown"}


def file_type_for(name: str) -> str:
    extension = Path(name).suffix.lower()
    try:
        return SUPPORTED_EXTENSIONS[extension]
    except KeyError as exc:
        allowed = "、".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedDocumentError(f"只支持 {allowed} 文件") from exc


def extract_text(source_file, file_type: str) -> tuple[str, dict]:
    source_file.open("rb")
    try:
        if file_type == "pdf":
            return _extract_pdf(source_file)
        if file_type == "docx":
            return _extract_docx(source_file)
        if file_type == "markdown":
            return _extract_markdown(source_file)
    finally:
        source_file.close()
    raise UnsupportedDocumentError("未识别的文档类型")


def _extract_pdf(source_file) -> tuple[str, dict]:
    pdf = pymupdf.open(stream=source_file.read(), filetype="pdf")
    try:
        if pdf.page_count > settings.MAX_DOCUMENT_PAGES:
            raise UnsupportedDocumentError(f"PDF 超过 {settings.MAX_DOCUMENT_PAGES} 页限制")
        pages = []
        for index, page in enumerate(pdf, start=1):
            page_text = page.get_text("text").strip()
            if page_text:
                pages.append(f"\n\n--- 第 {index} 页 ---\n{page_text}")
        text = "".join(pages).strip()
        if len(text) < 20:
            raise ScannedPdfError("未提取到文本；扫描件 PDF 暂不支持，请上传可复制文字的 PDF")
        return text, {"page_count": pdf.page_count}
    finally:
        pdf.close()


def _extract_docx(source_file) -> tuple[str, dict]:
    document = WordDocument(source_file)
    paragraphs = [
        paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()
    ]
    text = "\n\n".join(paragraphs)
    if not text:
        raise UnsupportedDocumentError("Word 文档没有可提取的正文")
    return text, {"paragraph_count": len(paragraphs)}


def _extract_markdown(source_file) -> tuple[str, dict]:
    text = source_file.read().decode("utf-8-sig").strip()
    if not text:
        raise UnsupportedDocumentError("Markdown 文档为空")
    return text, {}
