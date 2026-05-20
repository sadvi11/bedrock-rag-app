"""Unit tests for RAG pipeline configuration"""
import pytest
from rag import RAGPipeline

def test_chunk_size():
    assert RAGPipeline.CHUNK_SIZE == 500

def test_chunk_overlap():
    assert RAGPipeline.CHUNK_OVERLAP == 50

def test_top_k():
    assert RAGPipeline.TOP_K == 4

def test_chunk_text_splits_correctly():
    rag = RAGPipeline.__new__(RAGPipeline)
    rag.CHUNK_SIZE = 5
    rag.CHUNK_OVERLAP = 1
    text = "one two three four five six seven eight nine ten"
    chunks = rag.chunk_text(text)
    assert len(chunks) > 1
    assert "one" in chunks[0]
