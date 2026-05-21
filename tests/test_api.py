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
    assert data["service"] == "bedrock-financial-rag"


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
