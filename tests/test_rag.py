from pathlib import Path

from rag.chunker import split_chunks
from rag.loader import extract_text
from rag.retriever import retrieve


def test_chunking_respects_size_and_overlap():
    text = "0123456789" * 140
    chunks = split_chunks([{"text": text, "reference": "page 1"}], size=500, overlap=100)
    assert len(chunks) > 1
    assert all(len(chunk["text"]) <= 500 for chunk in chunks)
    assert chunks[0]["text"][-100:] == chunks[1]["text"][:100]


def test_txt_loader_and_policy_retrieval_citations():
    page = extract_text("policy.txt", b"Cancel before preparation begins.")[0]
    assert page["reference"] == "text"
    results = retrieve("What allergens are listed for Masala Dosa?", 4)
    assert results
    assert any("Ingredients_and_Allergens.txt" == source["filename"] for source in results)
    assert all("Refund_Policy.txt" != source["filename"] for source in results)
    assert len({(source["filename"], source["reference"]) for source in results}) == len(results)
    assert all("reference" in source for source in results)


def test_admin_can_upload_and_index_starter_pdf(client):
    pdf = (Path("knowledge_base") / "Restaurant_Policy.pdf").read_bytes()
    response = client.post("/api/documents", auth=("admin", "Admin123!"), files={"file": ("Restaurant_Policy.pdf", pdf, "application/pdf")})
    assert response.status_code == 201, response.text
    assert response.json()["chunks"] >= 1
    assert response.json()["vector_indexed"] is False
