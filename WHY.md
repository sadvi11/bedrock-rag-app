# WHY.md — The Decisions Behind This Project

> Most portfolios show *what* was built. This document explains *why* every major decision was made — the thinking behind the architecture, not just the architecture itself.

---

## Why I Built This Project

Canada has a financial literacy problem.

The average Canadian receives a 200-page annual report, a 40-page insurance policy, or a multi-page mortgage document — and cannot understand it. The language is dense, the numbers are buried, and the structure assumes a finance degree.

SmartMoney Canada (@smart_moneycanada, 100K+ views) exists to fix this. This project is the technical foundation of that mission — upload any financial document, ask a plain English question, get a clear answer grounded in the document itself.

The secondary reason: every cloud + AI role in Canada asks about AWS Bedrock. Building a real working Bedrock project — not a tutorial, not a clone, a production RAG pipeline — is the fastest way to prove hands-on experience that most candidates only claim.

---

## Why AWS Bedrock Instead of the Anthropic API Directly

My smart-ai-agent project already uses the Anthropic API directly. Building another project the same way adds nothing to a CV.

AWS Bedrock is how enterprises actually deploy AI. When a Canadian bank, insurance company, or telecoms firm builds an AI product, they use Bedrock — not because it is better in every way, but because it lives inside AWS where their data, security, and compliance infrastructure already lives. IAM controls, VPC boundaries, CloudTrail audit logs, billing consolidation — all of that works automatically when you use Bedrock.

Direct Anthropic API: right for prototypes and startups.
AWS Bedrock: right for production enterprise workloads.

A candidate who has only used the direct API tells a recruiter they understand AI. A candidate who has used Bedrock tells a recruiter they understand enterprise AI on AWS — which is a different, more valuable thing.

---

## Why Amazon Titan Embeddings V2 Instead of sentence-transformers

sentence-transformers downloads a model to your local machine and runs inference locally. That is fine for a laptop demo.

Titan Embeddings V2 runs inside AWS infrastructure via a single API call. No model download. No local GPU. No version management. Scales to millions of documents automatically. The same call that costs milliseconds on a laptop costs milliseconds on a Lambda function handling 10,000 concurrent users.

The 1024-dimension output was chosen over 256 or 512 because financial terminology is dense and domain-specific. Words like "amortisation", "yield", "covenant", "tranche" need high-dimensional space to be separated from their everyday meanings. More dimensions = better semantic precision for specialist domains.

---

## Why pgvector Instead of Amazon OpenSearch Serverless

OpenSearch Serverless costs approximately $0.24 per OCU-hour with a minimum of two OCUs — roughly $350/month minimum even with zero traffic. For a portfolio project that demonstrates the same architectural pattern, that cost is unjustifiable.

pgvector on Supabase free tier costs $0. The cosine similarity search is identical. The RLS security model is identical. The pgvector extension running on PostgreSQL is the same technology used by companies like Shopify and GitHub for their own vector search features.

The honest answer: pgvector was chosen because it costs nothing and demonstrates the same engineering pattern. In a production system handling millions of documents with strict latency SLAs, OpenSearch Serverless would be the right choice. The decision framework is the same — the infrastructure choice scales with the requirements.

---

## Why Financial Documents as the Use Case

Three reasons:

**It is real.** SmartMoney Canada is a real platform I run with real followers. This is not a toy use case invented to have something to demo — it is a genuine problem I am trying to solve.

**It is verifiable.** When a recruiter asks "what does this do?", I can say "upload Apple's Q3 earnings report and ask what iPhone revenue was." They can test it immediately. The answer is either right or wrong. There is no ambiguity about whether the system works.

**It matches target roles.** Fintech, banking, and insurance companies in Canada — the largest employers of cloud and AI engineers — immediately understand why financial document intelligence matters. The use case is their use case.

---

## Why Flask Instead of FastAPI

FastAPI would be the more technically impressive choice. It is faster, has automatic OpenAPI documentation, and has better async support.

Flask was chosen because the Bedrock boto3 client is synchronous. Building async FastAPI endpoints around a synchronous Bedrock client requires either running the sync calls in a thread pool executor or blocking the event loop — both of which add complexity without adding clarity.

For a project whose purpose is to demonstrate RAG architecture clearly, Flask's synchronous simplicity is the right tradeoff. The architecture is the point, not the web framework.

---

## Why Lambda for Document Ingestion

The alternative is a background thread or celery worker inside the Flask app. That means a server running continuously, even when nobody is uploading documents.

Lambda runs only when an S3 upload event fires. Zero cost between uploads. No server to manage. No idle compute. Scales from 1 to 10,000 concurrent uploads automatically.

This is exactly the pattern Netflix uses for video encoding — a new movie is uploaded to S3, Lambda triggers, encoding begins. No server sits idle waiting for the next movie. The pattern is identical; the workload is different.

---

## Why Terraform for Infrastructure

AWS CLI commands to create S3 buckets and Lambda functions work fine. They also leave no record of what was created, make it impossible to reproduce the environment, and create drift between what was intended and what exists.

Terraform treats infrastructure as code — the same version control, review, and reproducibility that code gets. The entire AWS infrastructure for this project (S3 bucket, Lambda function, IAM roles, CloudWatch log group, SNS alarm) is defined in 120 lines of HCL. Anyone can clone the repository, run `terraform apply`, and have an identical environment in three minutes.

For cloud engineering roles specifically, showing Terraform is not optional. It is the first thing infrastructure teams ask about.

---

## Why This Project Instead of Another Tutorial

Tutorials teach you to follow instructions. Portfolio projects teach you to make decisions.

Every section of this document represents a decision I had to research, evaluate, and own. Why Bedrock vs direct API. Why Titan vs sentence-transformers. Why pgvector vs OpenSearch. Why Flask vs FastAPI. Why Lambda vs a background worker.

A candidate who followed a tutorial can describe what the code does. A candidate who built something original can explain why every line of code is the way it is. That difference is what separates a junior candidate from a mid-level one — and mid-level is where the jobs are.

---

## The Nokia Bridge — Why My Background Is Relevant

I spent 2.5 years at Nokia deploying enterprise cloud infrastructure for 5G Packet Core networks — 10+ operator deployments, 100K+ subscribers per deployment, 99.9% SLA.

Nokia CBIS is OpenStack private cloud. AWS is public cloud. The concepts are identical: virtual compute, software-defined networking, lifecycle management, capacity planning, operational monitoring. The tools are different; the thinking is the same.

Nokia CBAM orchestrates VNF lifecycle — deploy, scale, update, monitor. AWS EKS and Lambda do the same for containers and functions. The orchestration pattern is identical.

The 99.9% SLA I maintained at Nokia is not a number on a CV. It is the result of ITIL-aligned incident management, zero-downtime deployment procedures, capacity planning, and operational discipline. Every AWS architecture I design is built on that foundation — because I have seen what happens when infrastructure fails at scale, with real subscribers on the other end.

---

*This document exists because architecture without reasoning is just code. The reasoning is the engineering.*

**Sadhvi Sharma** | Calgary, AB | github.com/sadvi11
