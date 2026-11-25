def split_chunks(pages: list[dict], size: int = 700, overlap: int = 100) -> list[dict]:
    if size < 500 or size > 900 or overlap < 0 or overlap >= size:
        raise ValueError("Chunk size must be 500-900 characters with a smaller overlap")
    chunks = []
    for page in pages:
        text = str(page["text"]).strip()
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append({"text": chunk, "reference": str(page.get("reference", "document")), "chunk": len(chunks)})
            if end == len(text):
                break
            start = end - overlap
    return chunks
