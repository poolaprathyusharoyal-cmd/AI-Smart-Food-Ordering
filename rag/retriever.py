from pathlib import Path
import re

from config.settings import settings
from rag.embeddings import embed_texts


def _collection():
    import chromadb
    Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=settings.chroma_path)
    return client.get_or_create_collection("restaurant_knowledge")


def index_chunks(filename: str, chunks: list[dict], document_id: int):
    if not settings.openai_api_key:
        return False
    embeddings = embed_texts([chunk["text"] for chunk in chunks])
    collection = _collection()
    ids = [f"doc-{document_id}-chunk-{chunk['chunk']}" for chunk in chunks]
    collection.upsert(ids=ids, documents=[chunk["text"] for chunk in chunks], embeddings=embeddings,
                      metadatas=[{"filename": filename, "reference": chunk["reference"], "document_id": document_id} for chunk in chunks])
    return True


def retrieve(question: str, limit: int = 4) -> list[dict]:
    if settings.openai_api_key:
        try:
            embedding = embed_texts([question])[0]
            results = _collection().query(query_embeddings=[embedding], n_results=limit, include=["documents", "metadatas", "distances"])
            docs = []
            for index, text in enumerate(results.get("documents", [[]])[0]):
                metadata = results.get("metadatas", [[]])[0][index]
                docs.append({"text": text, "filename": metadata.get("filename", "Unknown"), "reference": metadata.get("reference", "document"), "score": 1 - results.get("distances", [[1]])[0][index]})
            if docs:
                return docs
        except Exception:
            pass
    return _keyword_retrieve(question, limit)


def _keyword_retrieve(question: str, limit: int) -> list[dict]:
    roots = list(dict.fromkeys(path.resolve() for path in [Path("knowledge_base"), Path(__file__).resolve().parents[1] / "knowledge_base", Path("uploads")]))
    stop_words = {"the", "and", "for", "what", "are", "how", "does", "with", "from", "this", "that", "listed", "about"}
    terms = {word for word in re.findall(r"[a-z0-9]+", question.lower()) if len(word) > 2 and word not in stop_words}
    matches = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.glob("*.txt"):
            content = path.read_text(encoding="utf-8", errors="replace")
            for index, paragraph in enumerate(content.split("\n\n")):
                paragraph = paragraph.strip()
                if paragraph:
                    paragraph_terms = set(re.findall(r"[a-z0-9]+", paragraph.lower()))
                    score = len(terms & paragraph_terms)
                    if score:
                        matches.append((score, {"text": paragraph[:900], "filename": path.name, "reference": f"section {index + 1}", "score": score}))
    unique = {}
    for score, source in sorted(matches, key=lambda match: match[0], reverse=True):
        unique.setdefault((source["filename"], source["reference"], source["text"]), source)
    return list(unique.values())[:limit]
