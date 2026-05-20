"""
RAG Pipeline — Financial Document Intelligence
- Chunks documents into 500-word overlapping segments
- Embeds with Amazon Titan Embeddings V2 (via Bedrock)
- Stores vectors in Supabase pgvector (1024 dimensions)
- Retrieves via Python-side cosine similarity
- Generates answers with Claude 3 Haiku via Bedrock
"""

import os
import numpy as np
import logging
from supabase import create_client, Client
from bedrock_client import BedrockClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TABLE = "financial_documents"


class RAGPipeline:
    """
    Financial document RAG pipeline using AWS Bedrock.

    Architecture:
    Document → Chunk → Titan Embed → pgvector store
    Query → Titan Embed → Cosine similarity → Claude 3 Haiku → Answer
    """

    CHUNK_SIZE = 500          # words per chunk
    CHUNK_OVERLAP = 50        # overlap between chunks for context continuity
    TOP_K = 4                 # number of chunks to retrieve

    def __init__(self):
        self.bedrock = BedrockClient()
        self.supabase: Client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY"),
        )
        logger.info("RAGPipeline initialised — Bedrock + Supabase pgvector")

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping word-based chunks."""
        words = text.split()
        chunks = []
        step = self.CHUNK_SIZE - self.CHUNK_OVERLAP

        for i in range(0, len(words), step):
            chunk = " ".join(words[i: i + self.CHUNK_SIZE])
            if chunk.strip():
                chunks.append(chunk)

        logger.info(f"Chunked into {len(chunks)} segments")
        return chunks

    def store_document(
        self,
        text: str,
        source: str,
        doc_type: str = "financial_report",
    ) -> dict:
        """
        Full ingestion pipeline:
        1. Chunk text
        2. Embed each chunk via Bedrock Titan V2
        3. Store chunk + embedding + metadata in Supabase pgvector
        """
        chunks = self.chunk_text(text)
        stored = 0

        for idx, chunk in enumerate(chunks):
            try:
                embedding = self.bedrock.embed(chunk)
                self.supabase.table(TABLE).insert({
                    "content": chunk,
                    "source": source,
                    "doc_type": doc_type,
                    "chunk_index": idx,
                    "embedding": embedding,
                }).execute()
                stored += 1
            except Exception as e:
                logger.error(f"Failed to store chunk {idx}: {e}")

        logger.info(f"Stored {stored}/{len(chunks)} chunks for '{source}'")
        return {
            "stored": stored,
            "total_chunks": len(chunks),
            "source": source,
        }

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve_context(self, query: str) -> tuple[str, list[str]]:
        """
        Find most relevant chunks using cosine similarity.
        Returns: formatted context string + list of source documents used.
        """
        query_embedding = self.bedrock.embed(query)
        query_vec = np.array(query_embedding)

        result = self.supabase.table(TABLE).select(
            "content, source, embedding"
        ).execute()

        if not result.data:
            return "", []

        # Compute cosine similarity (Python-side — same as smart-ai-agent)
        scored = []
        for row in result.data:
            emb = row["embedding"]
            if isinstance(emb, str):
                import json
                emb = json.loads(emb)
            doc_vec = np.array(emb)
            norm_product = np.linalg.norm(query_vec) * np.linalg.norm(doc_vec)
            if norm_product == 0:
                continue
            similarity = float(np.dot(query_vec, doc_vec) / norm_product)
            scored.append((similarity, row["content"], row["source"]))

        scored.sort(reverse=True)
        top = scored[: self.TOP_K]

        logger.info(
            f"Retrieved {len(top)} chunks — best similarity: {top[0][0]:.3f}"
        )

        context_parts = [
            f"[Source: {src}]\n{content}"
            for _, content, src in top
        ]
        sources = list({src for _, _, src in top})
        context = "\n\n---\n\n".join(context_parts)
        return context, sources

    # ── Generation ────────────────────────────────────────────────────────────

    def query(self, question: str) -> dict:
        """
        Full RAG pipeline:
        question → embed → retrieve → generate → return
        """
        context, sources = self.retrieve_context(question)

        if not context:
            return {
                "answer": (
                    "No financial documents found in the knowledge base. "
                    "Please upload documents first via POST /upload."
                ),
                "sources": [],
                "model": "claude-3-haiku via AWS Bedrock",
            }

        answer = self.bedrock.generate(question, context)

        return {
            "answer": answer,
            "sources": sources,
            "model": "claude-3-haiku via AWS Bedrock",
            "embedding_model": "amazon.titan-embed-text-v2",
        }

    # ── Utilities ─────────────────────────────────────────────────────────────

    def list_documents(self) -> list[dict]:
        """List all unique documents in the knowledge base."""
        result = self.supabase.table(TABLE).select(
            "source, doc_type, created_at"
        ).execute()
        seen = {}
        for row in result.data:
            if row["source"] not in seen:
                seen[row["source"]] = {
                    "source": row["source"],
                    "doc_type": row["doc_type"],
                    "uploaded_at": row["created_at"],
                }
        return list(seen.values())

    def delete_document(self, source: str) -> dict:
        """Remove all chunks for a specific document."""
        self.supabase.table(TABLE).delete().eq(
            "source", source
        ).execute()
        return {"deleted": source, "status": "success"}
