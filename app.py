import logging
from flask import Flask, request, jsonify
from datetime import datetime
import os
from functools import wraps
import time
import numpy as np
import json
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

class Config:
    DEBUG = os.getenv("FLASK_ENV", "production") == "development"
    BEDROCK_REGION = os.getenv("AWS_REGION", "us-east-1")

app.config.from_object(Config)

metrics = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "embedding_latencies_ms": [],
    "retrieval_latencies_ms": [],
    "generation_latencies_ms": [],
    "similarity_scores": [],
    "documents_uploaded": 0,
    "health_checks": 0
}

def compute_p95(values):
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * 0.95)
    return round(sorted_vals[min(idx, len(sorted_vals) - 1)], 2)

def compute_avg(values):
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)

def track_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        metrics["total_requests"] += 1
        try:
            result = f(*args, **kwargs)
            metrics["successful_requests"] += 1
            return result
        except Exception as e:
            metrics["failed_requests"] += 1
            logger.error(f"Request error in {f.__name__}: {e}", exc_info=True)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"[TIMING] {f.__name__} total={duration_ms:.2f}ms")
    return decorated_function

def validate_rag_input(required_fields):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json()
            if not data:
                return {"error": "Missing JSON body", "status": "error"}, 400
            missing = [field for field in required_fields if field not in data]
            if missing:
                return {"error": f"Missing fields: {missing}", "status": "error"}, 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator

_rag = None
def get_rag():
    global _rag
    if _rag is None:
        from rag import RAGPipeline
        _rag = RAGPipeline()
        logger.info("RAGPipeline loaded")
    return _rag

@app.route("/health", methods=["GET"])
def health_check():
    metrics["health_checks"] += 1
    return jsonify({
        "status": "healthy",
        "service": "bedrock-rag-app",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "bedrock_region": Config.BEDROCK_REGION,
        "models": {
            "embedding": "amazon.titan-embed-text-v2:0 (1024-dim)",
            "generation": "anthropic.claude-haiku-4-5 via AWS Bedrock"
        },
        "metrics_summary": {
            "total_requests": metrics["total_requests"],
            "successful_requests": metrics["successful_requests"],
            "failed_requests": metrics["failed_requests"],
            "error_rate_pct": round(metrics["failed_requests"] / max(metrics["total_requests"], 1) * 100, 2),
            "documents_uploaded": metrics["documents_uploaded"],
            "avg_embedding_latency_ms": compute_avg(metrics["embedding_latencies_ms"]),
            "avg_retrieval_latency_ms": compute_avg(metrics["retrieval_latencies_ms"]),
            "avg_generation_latency_ms": compute_avg(metrics["generation_latencies_ms"]),
            "p95_embedding_latency_ms": compute_p95(metrics["embedding_latencies_ms"]),
            "p95_generation_latency_ms": compute_p95(metrics["generation_latencies_ms"]),
            "avg_similarity_score": compute_avg(metrics["similarity_scores"]),
            "total_queries": len(metrics["similarity_scores"])
        }
    }), 200

@app.route("/upload", methods=["POST"])
@track_request
@validate_rag_input(["text", "source"])
def upload():
    try:
        data = request.get_json()
        text = data.get("text", "").strip()
        source = data.get("source", "").strip()
        if len(text) == 0 or len(text) > 100000:
            return {"error": "Text must be 1-100000 characters", "status": "error"}, 400
        if len(source) == 0 or len(source) > 255:
            return {"error": "Source must be 1-255 characters", "status": "error"}, 400
        logger.info(f"[UPLOAD] source={source} text_length={len(text)}")
        ingest_start = time.time()
        result = get_rag().store_document(text, source)
        ingest_ms = (time.time() - ingest_start) * 1000
        metrics["documents_uploaded"] += 1
        logger.info(f"[UPLOAD] stored={result['stored']} chunks ingest_time={ingest_ms:.2f}ms")
        return jsonify({
            "status": "success",
            "message": f"Document '{source}' uploaded and processed",
            "source": source,
            "chunks_created": result["total_chunks"],
            "embeddings_stored": result["stored"],
            "ingest_latency_ms": round(ingest_ms, 2),
            "timestamp": datetime.now().isoformat()
        }), 201
    except Exception as e:
        logger.error(f"[UPLOAD] error: {e}", exc_info=True)
        return {"error": "Internal server error", "status": "error"}, 500

@app.route("/chat", methods=["POST"])
@track_request
@validate_rag_input(["question"])
def chat():
    try:
        data = request.get_json()
        question = data.get("question", "").strip()
        if len(question) == 0 or len(question) > 1000:
            return {"error": "Question must be 1-1000 characters", "status": "error"}, 400
        logger.info(f"[CHAT] question_length={len(question)}")
        rag = get_rag()

        t0 = time.time()
        query_embedding = rag.bedrock.embed(question)
        embedding_ms = (time.time() - t0) * 1000
        metrics["embedding_latencies_ms"].append(embedding_ms)

        t1 = time.time()
        query_vec = np.array(query_embedding)
        result = rag.supabase.table("financial_documents").select("content, source, embedding").execute()
        scored = []
        if result.data:
            for row in result.data:
                emb = row["embedding"]
                if isinstance(emb, str):
                    emb = json.loads(emb)
                doc_vec = np.array(emb)
                norm = np.linalg.norm(query_vec) * np.linalg.norm(doc_vec)
                if norm == 0:
                    continue
                sim = float(np.dot(query_vec, doc_vec) / norm)
                scored.append((sim, row["content"], row["source"]))
        scored.sort(reverse=True)
        top = scored[:rag.TOP_K]
        retrieval_ms = (time.time() - t1) * 1000
        metrics["retrieval_latencies_ms"].append(retrieval_ms)

        if not top:
            return jsonify({
                "status": "success",
                "answer": "No documents in knowledge base. Upload via POST /upload first.",
                "sources": [],
                "rag_metrics": {"embedding_latency_ms": round(embedding_ms, 2), "retrieval_latency_ms": round(retrieval_ms, 2), "generation_latency_ms": 0, "chunks_retrieved": 0},
                "timestamp": datetime.now().isoformat()
            }), 200

        top_similarity = top[0][0]
        metrics["similarity_scores"].append(top_similarity)
        context_parts = [f"[Source: {src}]\n{content}" for _, content, src in top]
        context = "\n\n---\n\n".join(context_parts)
        sources = list({src for _, _, src in top})

        t2 = time.time()
        answer = rag.bedrock.generate(question, context)
        generation_ms = (time.time() - t2) * 1000
        metrics["generation_latencies_ms"].append(generation_ms)

        total_ms = embedding_ms + retrieval_ms + generation_ms
        logger.info(f"[CHAT] embed={embedding_ms:.0f}ms retrieve={retrieval_ms:.0f}ms generate={generation_ms:.0f}ms total={total_ms:.0f}ms similarity={top_similarity:.3f}")

        return jsonify({
            "status": "success",
            "answer": answer,
            "question": question,
            "source_documents": [{"source": src, "similarity": round(sim, 3)} for sim, _, src in top],
            "rag_metrics": {
                "embedding_latency_ms": round(embedding_ms, 2),
                "retrieval_latency_ms": round(retrieval_ms, 2),
                "generation_latency_ms": round(generation_ms, 2),
                "total_latency_ms": round(total_ms, 2),
                "top_similarity_score": round(top_similarity, 3),
                "chunks_retrieved": len(top)
            },
            "timestamp": datetime.now().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"[CHAT] error: {e}", exc_info=True)
        return {"error": "Internal server error", "status": "error"}, 500

@app.route("/documents", methods=["GET"])
@track_request
def documents():
    try:
        docs = get_rag().list_documents()
        return jsonify({"status": "success", "count": len(docs), "documents": docs}), 200
    except Exception as e:
        logger.error(f"[DOCUMENTS] error: {e}", exc_info=True)
        return {"error": "Internal server error", "status": "error"}, 500

@app.route("/metrics", methods=["GET"])
def get_metrics():
    return jsonify({
        "status": "success",
        "counters": {
            "total_requests": metrics["total_requests"],
            "successful_requests": metrics["successful_requests"],
            "failed_requests": metrics["failed_requests"],
            "documents_uploaded": metrics["documents_uploaded"],
            "total_queries": len(metrics["similarity_scores"])
        },
        "latency_ms": {
            "embedding": {"avg": compute_avg(metrics["embedding_latencies_ms"]), "p95": compute_p95(metrics["embedding_latencies_ms"])},
            "retrieval": {"avg": compute_avg(metrics["retrieval_latencies_ms"]), "p95": compute_p95(metrics["retrieval_latencies_ms"])},
            "generation": {"avg": compute_avg(metrics["generation_latencies_ms"]), "p95": compute_p95(metrics["generation_latencies_ms"])}
        },
        "quality": {
            "avg_similarity_score": compute_avg(metrics["similarity_scores"]),
            "min_similarity_score": round(min(metrics["similarity_scores"]), 3) if metrics["similarity_scores"] else 0,
            "max_similarity_score": round(max(metrics["similarity_scores"]), 3) if metrics["similarity_scores"] else 0
        },
        "timestamp": datetime.now().isoformat()
    }), 200

@app.errorhandler(404)
def not_found(error):
    return {"error": "Not found", "path": request.path, "status": "error"}, 404

@app.errorhandler(500)
def server_error(error):
    return {"error": "Internal server error", "status": "error"}, 500

@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

if __name__ == "__main__":
    logger.info("Starting Bedrock RAG Server v2.0")
    logger.info(f"AWS Region: {Config.BEDROCK_REGION}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5002)), debug=Config.DEBUG, threaded=True)

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "Bedrock Financial RAG API",
        "version": "2.0.0",
        "live_demo": "https://bedrock-rag-app.onrender.com",
        "github": "https://github.com/sadvi11/bedrock-rag-app",
        "built_by": "Sadhvi Sharma — Nokia 5G → Cloud & AI Engineer",
        "endpoints": {
            "health": "GET /health",
            "upload": "POST /upload",
            "chat": "POST /chat",
            "documents": "GET /documents",
            "metrics": "GET /metrics"
        },
        "stack": "AWS Bedrock Titan V2 + Claude Haiku 4.5 + pgvector + Flask",
        "try_it": "POST /chat with {question: 'What is TD Bank dividend?'}"
    }), 200
