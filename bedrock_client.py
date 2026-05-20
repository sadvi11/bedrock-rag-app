"""
AWS Bedrock Client
- Amazon Titan Embeddings V2 for document embeddings (1024 dimensions)
- Anthropic Claude 3 Haiku via Bedrock for response generation
"""

import boto3
import json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BedrockClient:
    """
    Wrapper for AWS Bedrock API calls.
    Handles both embedding generation (Titan V2) and text generation (Claude 3 Haiku).
    """

    EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
    LLM_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    EMBEDDING_DIMENSIONS = 1024

    def __init__(self):
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        logger.info(f"BedrockClient initialised — region: {os.getenv('AWS_REGION', 'us-east-1')}")

    def embed(self, text: str) -> list[float]:
        """
        Generate embedding vector using Amazon Titan Embeddings V2.
        Returns 1024-dimensional normalised float vector.
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        # Titan V2 supports up to 8192 tokens — truncate if needed
        text = text[:8000]

        response = self.client.invoke_model(
            modelId=self.EMBEDDING_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "inputText": text,
                "dimensions": self.EMBEDDING_DIMENSIONS,
                "normalize": True,          # L2-normalised — cosine similarity = dot product
            }),
        )

        result = json.loads(response["body"].read())
        embedding = result["embedding"]
        logger.info(f"Embedded text — {len(embedding)} dimensions")
        return embedding

    def generate(self, question: str, context: str) -> str:
        """
        Generate answer using Claude 3 Haiku via AWS Bedrock.
        Uses retrieved RAG context as grounding.
        """
        system_prompt = f"""You are a financial document analyst assistant for SmartMoney Canada.

Your job: answer questions about uploaded financial documents accurately and clearly.
Audience: everyday Canadians learning about personal finance and investing.

INSTRUCTIONS:
- Answer ONLY from the context provided below
- If the answer is not in the context, say: "This information is not in the uploaded documents"
- Use simple, clear language — avoid financial jargon unless explaining it
- Cite the source document when possible
- Format numbers clearly (e.g., $1.2M, 15.3% growth)

CONTEXT FROM FINANCIAL DOCUMENTS:
{context}
"""

        response = self.client.invoke_model(
            modelId=self.LLM_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": question}
                ],
            }),
        )

        result = json.loads(response["body"].read())
        answer = result["content"][0]["text"]
        logger.info(f"Generated answer — {len(answer)} characters")
        return answer

    def summarise_document(self, text: str, source: str) -> str:
        """Generate a brief summary of a financial document on upload."""
        prompt = f"""Summarise this financial document in 3-4 bullet points.
Focus on: key financial figures, time period covered, main insights.
Document: {source}

Text (first 2000 chars):
{text[:2000]}"""

        response = self.client.invoke_model(
            modelId=self.LLM_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )

        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
