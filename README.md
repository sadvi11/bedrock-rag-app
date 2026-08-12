# Bedrock Financial RAG — SmartMoney Canada

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://python.org)
[![AWS Bedrock](https://img.shields.io/badge/AWS_Bedrock-Titan_V2_%2B_Claude_Haiku_4.5-FF9900?logo=amazon-aws)](https://aws.amazon.com/bedrock)
[![Flask](https://img.shields.io/badge/Flask-REST_API-000000?logo=flask)](https://flask.palletsprojects.com)
[![Supabase](https://img.shields.io/badge/Supabase-pgvector_1024_dim-3ECF8E?logo=supabase)](https://supabase.com)
[![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?logo=terraform)](https://terraform.io)
[![Status](https://img.shields.io/badge/Status-Deployed_%26_Verified-2ea44f)](https://github.com/sadvi11/bedrock-rag-app)

---

## Try it live

The service is deployed and responding:

```console
$ curl -s https://bedrock-rag-app.onrender.com/health | jq
{
  "service": "bedrock-rag-app",
  "status": "healthy",
  "version": "2.0.0",
  "bedrock_region": "us-east-1",
  "models": {
    "embedding": "amazon.titan-embed-text-v2:0 (1024-dim)",
    "generation": "anthropic.claude-haiku-4-5 via AWS Bedrock"
  },
  "metrics_summary": {
    "total_queries": 0,
    "avg_similarity_score": 0.0,
    "p95_generation_latency_ms": 0.0,
    "error_rate_pct": 0.0
  }
}
```

> Hosted on Render's free tier, so the first request after an idle period takes
> a few seconds to wake the container.

---

## Why I Built This

I sit with people — newcomers to Canada, working professionals, small business owners
— and walk them through exactly how to save taxes and build wealth in Canada.

Every session, the same problem comes up.

The advice exists. TFSA vs RRSP strategy, FHSA for first-time buyers, tax write-offs
for the self-employed, wealth building from a $60k salary — all of this is knowable.
But it is locked behind expensive advisors, buried in CRA documents nobody reads,
or drowned out by generic American financial content that does not apply here.

Most Canadians overpay taxes every year. Not because they are bad with money.
Because nobody ever sat down and showed them the plan.

I do that in person. This project scales it.

SmartMoney Canada is the platform. This RAG system is the AI layer underneath it —
it reads verified Canadian financial content and answers specific questions
grounded in real Canadian tax rules. Not hallucinated. Not generic. Not American.

**If I can only sit with one person at a time, this system can answer a thousand.**

---

## What This Does

Upload any Canadian financial document — tax guide, CRA publication, financial plan,
budget breakdown — and ask questions in plain English.

```
"Should I max my TFSA or RRSP first?"
"What can I write off as a self-employed person in Canada?"
"How does the FHSA work for a first-time buyer?"
"How do I start building wealth on a $60k salary in Alberta?"
```

The system finds the exact relevant section from your document and generates
an answer grounded only in that content. No hallucination. No generic advice.
No American tax rules accidentally applied to a Canadian situation.

---

## Architecture

```mermaid
flowchart TB
    User([User]) -->|"POST /chat"| API["Flask API<br/>app.py"]
    User -->|"POST /upload"| API

    subgraph Ingest ["Ingestion — runs once per document"]
        PDF["pypdf<br/>text extraction"] --> CHUNK["Chunking<br/>overlapping windows"]
        CHUNK --> EMB1["Titan Embeddings V2<br/>1024 dimensions"]
        EMB1 --> STORE[("Supabase pgvector<br/>documents table")]
    end

    subgraph Query ["Retrieval — runs per question"]
        EMB2["Titan Embeddings V2<br/>embed the question"]
        SEARCH["Cosine similarity search<br/>top-k chunks"]
        EMB2 --> SEARCH
        STORE -.->|"vector index"| SEARCH
    end

    API -->|"upload path"| PDF
    API -->|"query path"| EMB2
    SEARCH -->|"retrieved context"| GEN{{"Claude Haiku 4.5<br/>via AWS Bedrock"}}
    GEN -->|"grounded answer + sources"| API
    API --> User

    LAMBDA["Lambda<br/>lambda/ingest.py"] -.->|"batch ingestion"| PDF

    style GEN fill:#D4A27F,color:#000
    style STORE fill:#3ECF8E,color:#000
    style EMB1 fill:#FF9900,color:#000
    style EMB2 fill:#FF9900,color:#000
```

**Why the answers are grounded:** the model never sees the whole corpus. It
sees only the chunks whose embeddings are closest to the question, so an
answer either comes from a retrieved passage or the system reports that it has
none. For financial figures, a confidently wrong answer is worse than no
answer.

---

## Nokia 5G → AWS Bedrock Architecture Mapping

| Nokia 5G Function | AWS Bedrock Equivalent | Purpose |
|---|---|---|
| AMF (Access & Mobility) | Flask API + RAG Pipeline | Routes requests to right service |
| UDM (User Data Management) | Supabase pgvector | Persistent vector storage |
| CBIS (OpenStack private cloud) | AWS Bedrock managed service | Managed infra — no servers to manage |
| CBAM (VNF orchestration) | Lambda + S3 trigger | Event-driven document processing |
| Subscriber dimensioning | Titan Embeddings V2 | Translate content into 1024-dim vectors |
| OAM monitoring | CloudWatch + Lambda logs | Operational monitoring and alerting |
| Nokia Repository Function | IAM least-privilege roles | Resource governance and access control |

---

## Components

| Component | Technology | Purpose |
|---|---|---|
| Embedding Model | Amazon Titan Embeddings V2 (1024-dim) | Converts financial text to semantic vectors |
| Generation Model | Claude Haiku 4.5 via AWS Bedrock | Answers questions grounded in retrieved context |
| Vector Store | Supabase pgvector (1024-dim) | Stores and searches document embeddings |
| Document Storage | AWS S3 | Stores uploaded financial documents |
| Processing | AWS Lambda (S3 trigger) | Serverless document ingestion pipeline |
| Infrastructure | Terraform IaC | S3 + Lambda + IAM + CloudWatch as code |
| CI/CD | GitHub Actions | Lint → test → Lambda package → Terraform deploy |
| API Layer | Flask REST | 4 production endpoints |

---

## RAG Pipeline — How It Works

```
DOCUMENT UPLOAD                    QUESTION ANSWERING
───────────────                    ──────────────────
POST /upload                       User question
      │                                  │
  chunk_text()                    Bedrock Titan V2
  (500-word chunks)               embed question
      │                                  │
  Bedrock Titan V2                cosine similarity
  embed each chunk                search pgvector
  (1024 dimensions)                      │
      │                            top-4 chunks
  store in Supabase               retrieved
  pgvector table                  (best match: 0.789)
                                         │
                                  inject into Claude
                                  system prompt
                                         │
                                  Claude Haiku 4.5
                                  generates answer
                                  grounded in YOUR data
```

---

## Key Design Decisions

**Why AWS Bedrock instead of Anthropic direct API?**
AWS Bedrock is the enterprise deployment pattern — managed scaling, AWS IAM integration,
no API key management, usage tracked in AWS billing. Direct API is for prototypes.
Bedrock is for production. Financial advice tooling needs production-grade reliability.

**Why Titan Embeddings V2 (1024-dim)?**
Runs on AWS infrastructure — same network as S3 and Lambda.
No model download, no local compute, scales automatically.
1024 dimensions chosen for best semantic accuracy on Canadian financial terminology.

**Why pgvector over Amazon OpenSearch Serverless?**
pgvector on Supabase = zero additional AWS cost, familiar PostgreSQL interface,
RLS security already configured. OpenSearch Serverless costs ~$0.24/OCU-hour.
For this stage, pgvector is the right choice. Production at scale uses OpenSearch.

**Why Lambda for document ingestion?**
S3 upload → Lambda trigger = zero servers, scales to zero when idle, no cost between uploads.
Event-driven, serverless, automatic — same pattern Netflix uses for content encoding.

**Why RAG over fine-tuning?**
Canadian tax rules change every year — TFSA limits, FHSA eligibility, CRA updates.
RAG retrieves from an updatable database. Upload a new CRA document today, it is
searchable immediately. Fine-tuning bakes knowledge permanently into model weights
and requires expensive retraining to update. RAG is the only practical choice
for content that changes annually.

---

## Quick Start

```bash
# Clone
git clone https://github.com/sadvi11/bedrock-rag-app.git
cd bedrock-rag-app

# Install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Add: AWS credentials, Supabase URL + key

# Setup Supabase (run once)
# Paste supabase_setup.sql in Supabase SQL Editor

# Run
python app.py

# Upload a financial document
curl -X POST http://localhost:5002/upload \
  -H "Content-Type: application/json" \
  -d '{"text": "TFSA 2024 contribution limit is $7,000...", "source": "cra-tfsa-guide.txt"}'

# Ask a question
curl -X POST http://localhost:5002/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How much can I contribute to my TFSA in 2024?"}'

# Health check
curl http://localhost:5002/health
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/upload` | POST | Upload document → chunk → embed → store |
| `/chat` | POST | Ask question → RAG retrieval → Claude answer |
| `/documents` | GET | List all documents in knowledge base |
| `/health` | GET | Service health + model info + document count |

---

## Security Design

- **IAM least privilege** — Lambda role has only Bedrock InvokeModel + S3 read
- **S3 encryption** — AES-256 server-side encryption on all documents
- **Private S3 bucket** — all public access blocked
- **Supabase RLS** — Row Level Security on financial_documents table
- **No hardcoded credentials** — all secrets via environment variables

---

## It works — here it is working

| Health endpoint | RAG answer with sources |
|---|---|
| ![Health endpoint](screenshots/health-endpoint.png) | ![Chat answer](screenshots/chat-answer.png) |

| Embeddings + similarity score | Vectors in pgvector |
|---|---|
| ![Terminal logs](screenshots/terminal-logs.png) | ![Supabase documents](screenshots/supabase-financial-documents.png) |

| Claude Haiku 4.5 in Bedrock | Architecture |
|---|---|
| ![Bedrock playground](screenshots/bedrock-playground.png) | ![Architecture](screenshots/architecture.png) |

---

## Design Decisions

- **The real problem** — I advise Canadians on tax saving and wealth building in person.
  This system scales that advice. One session at a time becomes thousands simultaneously.
- **Why RAG not fine-tuning** — Canadian tax rules change annually. RAG retrieves from
  an updatable database. Fine-tuning requires expensive retraining to update.
- **Why Bedrock** — enterprise pattern, AWS IAM integration, managed scaling, no API keys
- **Nokia bridge** — CBIS OpenStack → AWS Bedrock; CBAM orchestration → Lambda triggers
- **Production gap I know** — next iteration adds EKS deployment, KEDA autoscaling,
  retrieval quality monitoring in CloudWatch

---

## Repository Structure

```
bedrock-rag-app/
├── app.py                    # Flask REST API — 4 endpoints
├── bedrock_client.py         # AWS Bedrock — Titan V2 + Claude Haiku 4.5
├── rag.py                    # RAG pipeline — chunk, embed, store, retrieve
├── requirements.txt
├── supabase_setup.sql        # One-time Supabase table setup
├── .env.example
├── .gitignore
├── lambda/
│   └── ingest.py             # Lambda — S3 trigger → process → store
├── infrastructure/
│   └── main.tf               # Terraform — S3 + Lambda + IAM + CloudWatch
├── .github/workflows/
│   └── deploy.yml            # GitHub Actions CI/CD
└── screenshots/              # Deployment proof
```

---

## Author

**Sadhvi Sharma** — Cloud & AI Engineer
Nokia India (5G Packet Core) → Cloud & AI Engineering
Calgary, AB, Canada | Permanent Resident | Open to Relocation

I advise newcomers, working professionals, and small business owners on Canadian
tax saving strategies and wealth building — and I build the technology to scale it.

[LinkedIn](https://linkedin.com/in/sadhvi-sharma-5789a6249) | [GitHub](https://github.com/sadvi11) | [@smart_moneycanada](https://instagram.com/smart_moneycanada)
