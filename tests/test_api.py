"""Integration smoke tests for Flask API endpoints"""
import json
from unittest.mock import patch, MagicMock
from app import app


def get_client():
    app.config["TESTING"] = True
    return app.test_client()


def test_health_returns_200():
    client = get_client()
    r = client.get("/health")
    assert r.status_code == 200


def test_health_has_service_name():
    client = get_client()
    data = json.loads(client.get("/health").data)
    assert data["service"] == "bedrock-rag-app"


def test_chat_requires_question():
    client = get_client()
    r = client.post("/chat",
                    data=json.dumps({}),
                    content_type="application/json")
    assert r.status_code == 400


def test_upload_requires_file():
    client = get_client()
    r = client.post("/upload",
                    data=json.dumps({}),
                    content_type="application/json")
    assert r.status_code == 400


def test_chat_uses_real_pipeline():
    """/chat must embed, run the pipeline search, and generate — not fake data."""
    fake = MagicMock()
    fake.embed_query.return_value = [0.1, 0.2, 0.3]
    fake.search.return_value = [(0.91, "TD Bank paid $1.02/share.", "td-q1.pdf")]
    fake.bedrock.generate.return_value = "TD Bank's dividend is $1.02 per share."

    with patch("app.get_rag", return_value=fake):
        client = get_client()
        r = client.post("/chat",
                        data=json.dumps({"question": "What is TD's dividend?"}),
                        content_type="application/json")

    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["answer"] == "TD Bank's dividend is $1.02 per share."
    assert data["source_documents"][0]["source"] == "td-q1.pdf"
    assert data["source_documents"][0]["similarity"] == 0.91
    fake.embed_query.assert_called_once()
    fake.search.assert_called_once()
    fake.bedrock.generate.assert_called_once()


def test_chat_handles_empty_knowledge_base():
    fake = MagicMock()
    fake.embed_query.return_value = [0.1, 0.2, 0.3]
    fake.search.return_value = []

    with patch("app.get_rag", return_value=fake):
        client = get_client()
        r = client.post("/chat",
                        data=json.dumps({"question": "anything?"}),
                        content_type="application/json")

    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["sources"] == []
    fake.bedrock.generate.assert_not_called()
