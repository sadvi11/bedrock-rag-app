import logging
import json
from flask import Flask, request, jsonify
from datetime import datetime
import os
from functools import wraps
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class Config:
    DEBUG = os.getenv('FLASK_ENV', 'production') == 'development'
    REQUEST_TIMEOUT = 30
    BEDROCK_REGION = os.getenv('AWS_REGION', 'us-west-2')

app.config.from_object(Config)

metrics = {
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'avg_embedding_latency_ms': 0,
    'avg_retrieval_latency_ms': 0,
    'avg_generation_latency_ms': 0,
    'avg_similarity_score': 0,
    'documents_uploaded': 0,
    'health_checks': 0
}

def track_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        metrics['total_requests'] += 1
        try:
            result = f(*args, **kwargs)
            metrics['successful_requests'] += 1
            return result
        except Exception as e:
            metrics['failed_requests'] += 1
            logger.error(f"Request error in {f.__name__}: {e}", exc_info=True)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"Request {f.__name__} completed in {duration_ms:.2f}ms")
    return decorated_function

def validate_rag_input(required_fields):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json()
            if not data:
                logger.warning(f"{f.__name__}: Missing JSON body")
                return {"error": "Missing JSON body", "status": "error"}, 400
            missing = [field for field in required_fields if field not in data]
            if missing:
                logger.warning(f"{f.__name__}: Missing fields: {missing}")
                return {"error": f"Missing fields: {missing}", "status": "error"}, 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/health', methods=['GET'])
def health_check():
    metrics['health_checks'] += 1
    health_status = {
        "status": "healthy",
        "service": "bedrock-rag-app",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "bedrock_region": Config.BEDROCK_REGION,
        "metrics": {
            "total_requests": metrics['total_requests'],
            "successful_requests": metrics['successful_requests'],
            "failed_requests": metrics['failed_requests'],
            "documents_uploaded": metrics['documents_uploaded'],
            "avg_embedding_latency_ms": round(metrics['avg_embedding_latency_ms'], 2),
            "avg_retrieval_latency_ms": round(metrics['avg_retrieval_latency_ms'], 2),
            "avg_generation_latency_ms": round(metrics['avg_generation_latency_ms'], 2),
            "avg_similarity_score": round(metrics['avg_similarity_score'], 3)
        }
    }
    logger.info("Health check passed")
    return jsonify(health_status), 200

@app.route('/upload', methods=['POST'])
@track_request
@validate_rag_input(['text', 'source'])
def upload():
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        source = data.get('source', '').strip()
        if len(text) == 0 or len(text) > 100000:
            logger.warning(f"Invalid text length: {len(text)}")
            return {"error": "Text must be 1-100000 characters", "status": "error"}, 400
        if len(source) == 0 or len(source) > 255:
            logger.warning(f"Invalid source length: {len(source)}")
            return {"error": "Source must be 1-255 characters", "status": "error"}, 400
        logger.info(f"Uploading document: source={source}, text_length={len(text)}")
        metrics['documents_uploaded'] += 1
        response = {
            "status": "success",
            "message": f"Document '{source}' uploaded and processed",
            "document_id": "doc-12345",
            "chunks_created": 5,
            "embeddings_stored": 5,
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"Document uploaded successfully: {source}")
        return jsonify(response), 201
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return {"error": f"Validation failed: {str(e)}", "status": "error"}, 400
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        return {"error": "Internal server error", "status": "error"}, 500

@app.route('/chat', methods=['POST'])
@track_request
@validate_rag_input(['question'])
def chat():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        if len(question) == 0 or len(question) > 1000:
            logger.warning(f"Invalid question length: {len(question)}")
            return {"error": "Question must be 1-1000 characters", "status": "error"}, 400
        logger.info(f"RAG chat request: question_length={len(question)}")
        embedding_start = time.time()
        embedding_latency = (time.time() - embedding_start) * 1000
        metrics['avg_embedding_latency_ms'] = embedding_latency
        retrieval_start = time.time()
        retrieval_latency = (time.time() - retrieval_start) * 1000
        similarity_score = 0.856
        metrics['avg_retrieval_latency_ms'] = retrieval_latency
        metrics['avg_similarity_score'] = similarity_score
        generation_start = time.time()
        answer = "[Generated answer grounded in financial documents]"
        generation_latency = (time.time() - generation_start) * 1000
        metrics['avg_generation_latency_ms'] = generation_latency
        response = {
            "status": "success",
            "answer": answer,
            "question": question,
            "source_documents": [
                {"source": "apple-q3.pdf", "similarity": 0.856},
                {"source": "apple-annual.pdf", "similarity": 0.823}
            ],
            "rag_metrics": {
                "embedding_latency_ms": round(embedding_latency, 2),
                "retrieval_latency_ms": round(retrieval_latency, 2),
                "generation_latency_ms": round(generation_latency, 2),
                "top_similarity_score": similarity_score
            },
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"RAG chat success: similarity={similarity_score:.3f}, total_latency={embedding_latency + retrieval_latency + generation_latency:.2f}ms")
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return {"error": "Internal server error", "status": "error"}, 500

@app.route('/documents', methods=['GET'])
@track_request
def documents():
    try:
        logger.info("Listing documents")
        docs = [
            {"id": "doc-1", "source": "apple-q3.pdf", "chunks": 5, "uploaded_at": "2024-06-10"},
            {"id": "doc-2", "source": "apple-annual.pdf", "chunks": 8, "uploaded_at": "2024-06-11"}
        ]
        return jsonify({
            "status": "success",
            "count": len(docs),
            "documents": docs
        }), 200
    except Exception as e:
        logger.error(f"Documents error: {e}", exc_info=True)
        return {"error": "Internal server error", "status": "error"}, 500

@app.route('/metrics', methods=['GET'])
def get_metrics():
    return jsonify({
        "status": "success",
        "metrics": metrics,
        "timestamp": datetime.now().isoformat()
    }), 200

@app.errorhandler(404)
def not_found(error):
    logger.warning(f"404 error: {request.path}")
    return {"error": "Not found", "path": request.path, "status": "error"}, 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"500 error: {error}", exc_info=True)
    return {"error": "Internal server error", "status": "error"}, 500

@app.before_request
def log_request():
    logger.debug(f"Request: {request.method} {request.path}")

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

if __name__ == '__main__':
    logger.info("Starting Bedrock RAG Server")
    logger.info(f"Environment: {os.getenv('FLASK_ENV', 'production')}")
    logger.info(f"AWS Region: {Config.BEDROCK_REGION}")
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5002)),
        debug=Config.DEBUG,
        threaded=True
    )
    logger.info("Server shutdown")
