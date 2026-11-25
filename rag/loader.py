from io import BytesIO
from pathlib import Path


def extract_text(filename: str, content: bytes) -> list[dict[str, str | int]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt":
        return [{"text": content.decode("utf-8", errors="replace"), "reference": "text"}]
    if suffix == ".pdf":
        import fitz
        document = fitz.open(stream=content, filetype="pdf")
        return [{"text": page.get_text(), "reference": f"page {index + 1}"} for index, page in enumerate(document)]
    if suffix == ".docx":
        from docx import Document as WordDocument
        document = WordDocument(BytesIO(content))
        blocks = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        return [{"text": "\n".join(blocks), "reference": "document"}]
    raise ValueError("Only PDF, DOCX, and TXT documents are accepted")
