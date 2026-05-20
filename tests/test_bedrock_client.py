"""Unit tests for BedrockClient configuration"""
from bedrock_client import BedrockClient


def test_embedding_model_id():
    bc = BedrockClient()
    assert bc.EMBEDDING_MODEL == "amazon.titan-embed-text-v2:0"


def test_llm_model_uses_inference_profile():
    bc = BedrockClient()
    assert bc.LLM_MODEL.startswith("us.")


def test_embedding_dimensions():
    assert BedrockClient.EMBEDDING_DIMENSIONS == 1024


def test_llm_is_haiku():
    bc = BedrockClient()
    assert "haiku" in bc.LLM_MODEL.lower()
