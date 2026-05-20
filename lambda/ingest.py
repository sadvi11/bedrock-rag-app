"""
AWS Lambda — S3 Document Ingestion Trigger
Triggered automatically when a file is uploaded to S3.
Processes document → chunks → Bedrock Titan embeddings → Supabase pgvector
"""

import json
import urllib.parse
import logging
import boto3
from rag import RAGPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_text_from_s3(s3_client, bucket: str, key: str) -> str:
    """Read and decode file content from S3."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read()

    # Try PDF extraction if pypdf available
    if key.lower().endswith(".pdf"):
        try:
            import pypdf
            import io
            reader = pypdf.PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            logger.warning(f"PDF extraction failed, using raw text: {e}")

    return content.decode("utf-8", errors="ignore")


def handler(event, context):
    """
    Lambda handler triggered by S3 ObjectCreated events.

    Flow:
    S3 Upload → Lambda triggered → Read file → Chunk → Embed via Bedrock → Store in pgvector
    """
    s3_client = boto3.client("s3")
    rag = RAGPipeline()

    processed = []
    errors = []

    for record in event.get("Records", []):
        try:
            bucket = record["s3"]["bucket"]["name"]
            key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

            # Only process documents/ prefix
            if not key.startswith("documents/"):
                logger.info(f"Skipping non-document key: {key}")
                continue

            filename = key.split("/")[-1]
            logger.info(f"Processing: s3://{bucket}/{key}")

            # Extract text
            text = extract_text_from_s3(s3_client, bucket, key)
            if not text.strip():
                logger.warning(f"No text extracted from {key}")
                continue

            # Ingest via RAG pipeline
            result = rag.store_document(text, source=filename)
            logger.info(f"Stored {result['stored']} chunks for {filename}")

            processed.append({
                "key": key,
                "chunks_stored": result["stored"],
            })

        except Exception as e:
            logger.error(f"Error processing record: {e}")
            errors.append({"key": key if "key" in dir() else "unknown", "error": str(e)})

    response_body = {
        "processed": processed,
        "errors": errors,
        "total_processed": len(processed),
    }

    logger.info(f"Lambda complete: {json.dumps(response_body)}")
    return {
        "statusCode": 200,
        "body": json.dumps(response_body),
    }
