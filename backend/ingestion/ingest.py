"""
One-time ingestion script: chunks regulatory documents, generates embeddings,
and upserts them into the Qdrant vector store.

Usage:
    python -m ingestion.ingest --corpus-dir data/regulatory_corpus
"""

import argparse
import hashlib
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF
import structlog
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
)

from core.config import settings

log = structlog.get_logger()

# ── Constants ──────────────────────────────────────────────────────────────────
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
VECTOR_SIZE = 3072

BATCH_SIZE = 100        # free tier limit: 100 requests per minute
RATE_LIMIT_DELAY = 61   # seconds to wait between batches due to rate limits (set to 61 to be safe)


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract all text from a PDF file using PyMuPDF."""
    doc = fitz.open(str(pdf_path))
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


def chunk_document(text: str, source: str) -> list[dict]:
    """
    Split document text into overlapping chunks.
    Each chunk retains its source filename as metadata for citation.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunks = splitter.split_text(text)
    return [
        {
            "text": chunk,
            "source": source,
            "chunk_index": i,
            "id": hashlib.md5(f"{source}_{i}_{chunk[:50]}".encode()).hexdigest(),
        }
        for i, chunk in enumerate(chunks)
    ]


def ingest(corpus_dir: Path) -> None:
    pdf_files = list(corpus_dir.glob("*.pdf"))
    if not pdf_files:
        log.error("no_pdfs_found", directory=str(corpus_dir))
        sys.exit(1)

    log.info("ingestion_started", file_count=len(pdf_files))

    embedder = GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        google_api_key=settings.google_api_key,
        task_type="retrieval_document",
    )
    qdrant = QdrantClient(
        url=settings.qdrant_url,
        **( {"api_key": settings.qdrant_api_key} if settings.qdrant_api_key else {} )
    )

    # Create collection only if it doesn't already exist
    # This preserves previously ingested documents across runs
    if not qdrant.collection_exists(settings.qdrant_collection_name):
        qdrant.create_collection(
            collection_name=settings.qdrant_collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        log.info("collection_created", name=settings.qdrant_collection_name)
    else:
        log.info("collection_exists", name=settings.qdrant_collection_name)

    # Fetch all chunk IDs already present in the collection
    # so we can skip re-embedding documents that are already ingested
    existing_ids = _get_existing_ids(qdrant)
    log.info("existing_chunks_found", count=len(existing_ids))

    # Chunk all documents and filter to only new chunks
    all_chunks: list[dict] = []
    skipped_files = []

    for pdf_path in pdf_files:
        log.info("processing_file", file=pdf_path.name)
        text = extract_text_from_pdf(pdf_path)
        chunks = chunk_document(text, source=pdf_path.stem)

        # Check if ANY chunk from this file is already in the collection
        # If all chunks exist, skip the entire file
        new_chunks = [c for c in chunks if c["id"] not in existing_ids]

        if not new_chunks:
            log.info("file_skipped_already_ingested", file=pdf_path.name, chunks=len(chunks))
            skipped_files.append(pdf_path.name)
            continue

        log.info(
            "file_chunked",
            file=pdf_path.name,
            total_chunks=len(chunks),
            new_chunks=len(new_chunks),
            skipped_chunks=len(chunks) - len(new_chunks),
        )
        all_chunks.extend(new_chunks)

    if not all_chunks:
        log.info("nothing_to_ingest", skipped_files=skipped_files)
        return

    total_chunks = len(all_chunks)
    total_batches = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE
    estimated_minutes = round(total_batches * RATE_LIMIT_DELAY / 60, 1)

    log.info(
        "embedding_started",
        total_chunks=total_chunks,
        batch_size=BATCH_SIZE,
        total_batches=total_batches,
        estimated_minutes=estimated_minutes,
        skipped_files=skipped_files,
    )

    for batch_num, i in enumerate(range(0, total_chunks, BATCH_SIZE), start=1):
        batch = all_chunks[i : i + BATCH_SIZE]
        texts = [c["text"] for c in batch]

        log.info(
            "batch_embedding",
            batch=batch_num,
            of=total_batches,
            chunks_in_batch=len(batch),
        )

        vectors = embedder.embed_documents(texts)

        points = [
            PointStruct(
                id=c["id"],
                vector=v,
                payload={
                    "text": c["text"],
                    "source": c["source"],
                    "chunk_index": c["chunk_index"],
                },
            )
            for c, v in zip(batch, vectors)
        ]

        qdrant.upsert(collection_name=settings.qdrant_collection_name, points=points)

        log.info(
            "batch_upserted",
            batch=batch_num,
            of=total_batches,
            progress=f"{i + len(batch)}/{total_chunks}",
        )

        if batch_num < total_batches:
            log.info(
                "rate_limit_pause",
                seconds=RATE_LIMIT_DELAY,
                next_batch=batch_num + 1,
                of=total_batches,
            )
            time.sleep(RATE_LIMIT_DELAY)

    log.info("ingestion_complete", new_chunks_ingested=total_chunks)


def _get_existing_ids(qdrant: QdrantClient) -> set[str]:
    """
    Scroll through all points in the collection and return their IDs.
    Used to determine which chunks have already been ingested so we
    can skip re-embedding them on subsequent runs.
    """
    existing_ids = set()
    next_offset = None

    while True:
        results, next_offset = qdrant.scroll(
            collection_name=settings.qdrant_collection_name,
            offset=next_offset,
            limit=1000,         # fetch 1000 IDs at a time
            with_payload=False, # we only need IDs, not the full payload
            with_vectors=False, # we don't need vectors either
        )
        for point in results:
            existing_ids.add(point.id)

        if next_offset is None:
            break

    return existing_ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest regulatory corpus into Qdrant")
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("data/regulatory_corpus"),
    )
    args = parser.parse_args()
    ingest(args.corpus_dir)