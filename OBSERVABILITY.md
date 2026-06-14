# RAG Observability Guide — Netflix L3 Production Patterns

## RAG-Specific Metrics

Netflix engineers monitoring RAG systems track:

### 1. Embedding Latency
- Time to embed user question via Bedrock Titan V2
- Target: <500ms
- If >1000ms: Bedrock overloaded or region far

### 2. Retrieval Latency
- Time to search pgvector and return top-4 chunks
- Target: <200ms
- If >500ms: Database query slow or index missing

### 3. Similarity Score
- Cosine similarity of retrieved chunks (0-1 scale)
- Target: >0.75 (high semantic relevance)
- If <0.60: Question not well-represented in knowledge base

### 4. Generation Latency
- Time for Claude Haiku 4.5 to generate answer
- Target: <2000ms
- If >5000ms: Bedrock inference slow or context too large

### 5. Total Pipeline Latency
- Sum of embedding + retrieval + generation
- Target: <3000ms (3 seconds)
- User-facing: if >5000ms, show "Loading..." spinner

### 6. Document Retrieval Success Rate
- Percentage of questions that return relevant documents
- Target: >95%
- If <80%: Knowledge base too small or chunking bad

## CloudWatch Dashboard

Monitor these metrics:
- Embedding latency (P50, P99)
- Retrieval latency (P50, P99)
- Generation latency (P50, P99)
- Similarity score (avg, min)
- Documents in knowledge base
- Chat requests (success/error)
- Error rate (%)
- Total pipeline latency (P99)

## Alarms

Alert if:
- Embedding latency > 1000ms for 5 min → Page L4
- Retrieval latency > 500ms for 5 min → Page L4
- Generation latency > 5000ms for 5 min → Page L4
- Total pipeline latency > 5000ms for 10 min → Page L4
- Error rate > 2% for 5 min → Page on-call
- Similarity score < 0.60 (avg) → Alert (not page)
- Documents < 1 → Page (knowledge base empty!)

## Why Netflix Cares About RAG Observability

Netflix uses RAG for:
- Content recommendations (find movies similar to X)
- User support (answer questions about plan features)
- Internal tools (search engineering docs quickly)

If RAG latency breaks:
- Recommendations take 30sec instead of 200ms = 50% abandonment
- Support chatbot timeouts = customers call support = cost increase
- Internal tools slow = engineers context-switch = productivity loss

## Production RAG Debugging

**Problem: Similarity score < 0.60**
- Add synonyms to system prompt
- Upload more comprehensive documents
- Fine-tune Titan Embeddings (L4 does this)

**Problem: Generation latency > 5000ms**
- Limit retrieved chunks to top-2 instead of top-4
- Compress context (summarize instead of full text)
- Use Haiku instead of Opus (faster)

**Problem: Embedding latency > 1000ms**
- Move app to same region as Bedrock
- Request rate limit increase from AWS
- Batch embeddings if possible

## Netflix L3 Responsibility

As L3, you:
✅ Monitor RAG metrics daily
✅ Alert L4 if P99 latency > target
✅ Document why latencies changed in standup
✅ Propose optimizations (chunk size, similarity threshold)

You DON'T:
❌ Fine-tune embedding models (L4 does that)
❌ Redesign RAG architecture (L4 decides)
❌ Make Bedrock API calls directly (use wrapper)

## References

- AWS Bedrock docs: https://docs.aws.amazon.com/bedrock/
- RAG best practices: https://aws.amazon.com/bedrock/
