"""
Bedrock Financial RAG — Flask REST API
Financial Document Intelligence powered by AWS Bedrock

Endpoints:
  POST /upload       Upload a financial document (.txt or .pdf)
  POST /chat         Ask a question about uploaded documents
  GET  /documents    List all documents in knowledge base
  DELETE /documents/<source>  Remove a document
  GET  /health       Service health check
"""

import os
import uuid
import logging
import tempfile
import boto3
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from rag import RAGPipeline
load_dotenv()

# ── PDF support ───────────────────────────────────────────────────────────────
try:
    import pypdf
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
rag = RAGPipeline()

S3_BUCKET = os.getenv("S3_BUCKET_NAME", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

s3_client = boto3.client("s3", region_name=AWS_REGION) if S3_BUCKET else None

ALLOWED_EXTENSIONS = {"txt", "pdf", "csv", "md"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text(filepath: str, filename: str) -> str:
    """Extract text from uploaded file."""
    ext = filename.rsplit(".", 1)[1].lower()

    if ext == "pdf" and PDF_SUPPORT:
        reader = pypdf.PdfReader(filepath)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


# ── Health ────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    doc_count = len(rag.list_documents())
    return jsonify({
        "service": "bedrock-financial-rag",
        "version": "1.0",
        "status": "healthy",
        "models": {
            "embedding": "amazon.titan-embed-text-v2:0",
            "generation": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        },
        "vector_store": "Supabase pgvector",
        "documents_in_knowledge_base": doc_count,
        "s3_bucket": S3_BUCKET or "local — see infrastructure/main.tf",
        "use_case": "Financial Document Q&A — SmartMoney Canada",
    }), 200


# ── Upload ────────────────────────────────────────────────────────────────────

@app.route("/upload", methods=["POST"])
def upload():
    """
    Upload a financial document.
    Accepts: multipart/form-data with 'file' field
    OR: JSON with 'text' and 'source' fields (direct text upload)
    """

    # Option 1: Direct text upload (for testing)
    if request.is_json:
        data = request.get_json()
        text = data.get("text", "")
        source = data.get("source", f"document_{uuid.uuid4().hex[:8]}.txt")
        doc_type = data.get("doc_type", "financial_report")

        if not text:
            return jsonify({"error": "text field required"}), 400

        result = rag.store_document(text, source=source, doc_type=doc_type)
        summary = "Summary will be available once Anthropic form is approved"

        return jsonify({
            "status": "success",
            "source": source,
            "chunks_stored": result["stored"],
            "summary": summary,
            "model": "amazon.titan-embed-text-v2 via AWS Bedrock",
        }), 200

    # Option 2: File upload
    if "file" not in request.files:
        return jsonify({"error": "No file provided. Use 'file' field in multipart form."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({
            "error": f"File type not supported. Allowed: {ALLOWED_EXTENSIONS}"
        }), 400

    filename = secure_filename(file.filename)
    doc_type = request.form.get("doc_type", "financial_report")

    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}") as tmp:
        file.save(tmp.name)
        text = extract_text(tmp.name, filename)

    if not text.strip():
        return jsonify({"error": "Could not extract text from file"}), 400

    # Upload to S3 if configured
    s3_key = None
    if s3_client and S3_BUCKET:
        try:
            s3_key = f"documents/{filename}"
            s3_client.upload_file(tmp.name, S3_BUCKET, s3_key)
            logger.info(f"Uploaded {filename} to s3://{S3_BUCKET}/{s3_key}")
        except Exception as e:
            logger.warning(f"S3 upload failed (continuing): {e}")

    # Store in pgvector
    result = rag.store_document(text, source=filename, doc_type=doc_type)
    summary = rag.bedrock.summarise_document(text, filename)

    return jsonify({
        "status": "success",
        "source": filename,
        "chunks_stored": result["stored"],
        "characters_processed": len(text),
        "s3_key": s3_key,
        "summary": summary,
        "embedding_model": "amazon.titan-embed-text-v2:0",
    }), 200


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
def chat():
    """
    Ask a question about uploaded financial documents.
    Request: {"question": "What was the revenue in Q3?"}
    """
    data = request.get_json()
    if not data or "question" not in data:
        return jsonify({"error": "question field required"}), 400

    question = data["question"].strip()
    if not question:
        return jsonify({"error": "question cannot be empty"}), 400

    logger.info(f"Question: {question}")
    result = rag.query(question)

    return jsonify({
        "status": "success",
        "question": question,
        "answer": result["answer"],
        "sources": result["sources"],
        "powered_by": {
            "embedding": result.get("embedding_model", "amazon.titan-embed-text-v2"),
            "generation": result.get("model", "claude-3-haiku via AWS Bedrock"),
        },
    }), 200


# ── Documents ─────────────────────────────────────────────────────────────────

@app.route("/documents", methods=["GET"])
def list_documents():
    """List all documents in the knowledge base."""
    docs = rag.list_documents()
    return jsonify({
        "status": "success",
        "count": len(docs),
        "documents": docs,
    }), 200


@app.route("/documents/<path:source>", methods=["DELETE"])
def delete_document(source: str):
    """Remove a document from the knowledge base."""
    result = rag.delete_document(source)
    return jsonify(result), 200


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5002))
    logger.info(f"Starting Bedrock Financial RAG on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
