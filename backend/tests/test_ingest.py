from __future__ import annotations

from ingestion.ingest import chunk_document


def test_chunk_document_keeps_source_and_indexes():
    text = ("Paragraph one. " * 120) + "\n\n" + ("Paragraph two. " * 120)

    chunks = chunk_document(text, source="mas_notice_626")

    assert len(chunks) >= 2
    assert all(chunk["source"] == "mas_notice_626" for chunk in chunks)
    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk["id"] for chunk in chunks)

