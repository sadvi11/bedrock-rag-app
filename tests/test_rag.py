"""Unit tests for RAG pipeline configuration"""
from unittest.mock import MagicMock
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


def test_search_uses_match_documents_rpc():
    """search() must delegate ranking to the server-side match_documents RPC."""
    rag = RAGPipeline.__new__(RAGPipeline)
    rag.TOP_K = 4
    rag.supabase = MagicMock()
    rag.supabase.rpc.return_value.execute.return_value.data = [
        {"similarity": 0.9, "content": "chunk one", "source": "s1"},
        {"similarity": 0.7, "content": "chunk two", "source": "s2"},
    ]

    top = rag.search([0.1, 0.2, 0.3])

    name, params = rag.supabase.rpc.call_args.args
    assert name == "match_documents"
    assert params["match_count"] == 4
    assert top[0] == (0.9, "chunk one", "s1")


def test_search_returns_empty_when_no_rows():
    rag = RAGPipeline.__new__(RAGPipeline)
    rag.TOP_K = 4
    rag.supabase = MagicMock()
    rag.supabase.rpc.return_value.execute.return_value.data = []
    assert rag.search([0.1, 0.2]) == []
