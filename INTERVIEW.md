# Real-Time RAG Interview Guide

This document is a project-specific interview preparation guide for the Real-Time RAG system in this repository. It covers architecture, design decisions, technology choices, tradeoffs, and likely viva or interview questions with strong sample answers.

## 1. Project Summary

### Q: What is this project?

This project is a real-time retrieval-augmented generation system for operational incident intelligence. It allows authenticated users to log incidents, ingest them through a Kafka-compatible stream, store them in a FAISS vector index, retrieve relevant incidents using hybrid retrieval, and generate grounded answers using an LLM. The system is also team-aware, so users receive context relevant to their own team such as DevOps, Security, or Operations.

### Q: What problem does it solve?

Traditional RAG systems are often static. Once the documents are indexed, new information is not immediately available unless the system is re-indexed or restarted. In operations and incident management, that is a major problem because incidents change rapidly. This project solves that by supporting near real-time ingestion, team-based filtering, and live querying on newly added incidents.

### Q: What makes this project different from a basic chatbot?

A normal chatbot answers using a general model and may hallucinate. This project grounds answers in retrieved operational incidents. It also supports streaming ingestion, authentication, analytics, and team-aware access, which makes it closer to an internal operational intelligence system than a generic chatbot.

## 2. Elevator Pitch

### Q: Give me a 30-second explanation of your project.

I built a real-time RAG platform for operational incident analysis. Users can simulate or log incidents, those incidents are streamed through Kafka/Redpanda and embedded into a FAISS vector store, and authenticated users can then ask natural language questions through a React dashboard. The retrieval pipeline combines semantic search, BM25, rank fusion, and reranking, and the answer generation is personalized by team context such as DevOps or Security.

## 3. End-to-End Flow

### Q: Walk me through the system flow from issue creation to answer generation.

1. A user logs in using Supabase authentication.
2. From the simulation page or a client, the user sends an issue to `POST /log_issue`.
3. The backend attaches the user's `team_tag`, stores issue analytics, and publishes the event to Kafka/Redpanda.
4. The consumer reads the event and stores the issue text and metadata in FAISS and `docs.json`.
5. When the user asks a question using `POST /ask`, the backend authenticates the JWT and resolves the user profile.
6. LangGraph executes the retrieval node and then the answer node.
7. The retrieval node loads the latest vector store, runs dense retrieval, runs sparse retrieval on the team-scoped corpus, fuses results with RRF, reranks them, and selects top documents.
8. The answer node sends those documents plus the user query to Groq and returns a grounded answer.
9. Query analytics such as response time and approximate answer quality are stored in SQLite.

## 4. Architecture Questions

### Q: Why did you separate ingestion and querying?

I separated them so ingestion does not block question answering. Incident logging is fast because the API only accepts the issue and pushes it into the stream. Embedding generation and vector-store update happen in the consumer process. This makes the system more scalable and better aligned with real-time operational workloads.

### Q: Why use Kafka or Redpanda here?

Kafka-style streaming decouples producers from consumers. It improves reliability and throughput because the API can accept events quickly while downstream processing happens asynchronously. I used Redpanda because it is Kafka-compatible and simpler to run locally with Docker.

### Q: Why use LangGraph instead of plain function calls?

LangGraph gives a clean workflow structure around the RAG pipeline. Even though the current graph is small with `retrieve -> answer`, it is easy to extend later with moderation, routing, summarization, approval, or fallback nodes.

### Q: Why is this called real-time if Kafka consumer processing is asynchronous?

It is real-time in the practical application sense: newly logged incidents become queryable without restarting the server and with low delay. The system is not hard real-time, but it supports near real-time ingestion and retrieval, which is the right model for incident intelligence systems.

## 5. Retrieval Questions

### Q: What retrieval strategy did you use?

I used hybrid retrieval:

- dense retrieval through FAISS and sentence-transformer embeddings
- sparse retrieval through BM25
- reciprocal rank fusion to combine both rankings
- a simple overlap-based reranker to prioritize documents sharing query terms

This balances semantic understanding with exact keyword matching.

### Q: Why not use only vector search?

Vector search is strong for semantic similarity, but it can miss documents that contain exact important keywords such as service names, error codes, regions, or ticket IDs. BM25 is good at lexical matching, so combining both gives better retrieval quality.

### Q: Why use RRF?

Dense and sparse retrievers produce different rankings with different score scales. Reciprocal Rank Fusion is simple and effective because it merges rankings based on position rather than raw scores. That avoids difficult score normalization and works well in hybrid retrieval setups.

### Q: Why did you add a reranking step after fusion?

Rank fusion gives a stronger combined candidate set, but a lightweight reranking step helps prioritize documents with higher overlap to the user query. It is a cheap way to improve relevance before sending context to the LLM.

### Q: How is team filtering handled?

Each issue carries `team_tag` metadata. In the retrieval node, dense results are filtered by `team_tag`, and the sparse retrieval corpus is also built from documents belonging to that team. That ensures both retrieval paths are team-aware.

### Q: Why is team filtering important?

It improves relevance and supports access isolation. A DevOps user should mainly see infrastructure and deployment issues, while a Security user should see threats and login anomalies. Without filtering, answers would be noisy and potentially expose irrelevant or sensitive information.

## 6. Vector Database and Storage Questions

### Q: Why did you use FAISS?

FAISS is fast, lightweight, and easy to run locally. It is a good fit for a project or interview setting where I want vector retrieval without depending on an external managed vector database.

### Q: How do you persist the data?

The vector index is stored in `data/faiss.index`, document metadata is stored in `data/docs.json`, and a version counter is stored in `data/version.txt`. The version counter allows the API-side vector store to detect changes and reload from disk automatically.

### Q: Why is the version file useful?

The API and the Kafka consumer are separate processes. If the consumer updates the FAISS index, the API process needs a lightweight way to detect that new data is available. The version file is a simple synchronization signal that lets the vector store reload without restarting the server.

### Q: What are the limitations of this storage design?

- local disk storage is not ideal for distributed deployment
- there is limited concurrency control
- there is no managed durability or backup strategy
- FAISS on local disk works well for demos but would need a more production-ready storage architecture later

## 7. LLM Questions

### Q: Why did you use Groq?

Groq provides fast inference and is a good choice for real-time interactive responses. In this project, latency matters because the user expects quick operational answers after retrieval.

### Q: What model are you using?

The config currently uses `llama-3.1-8b-instant`.

### Q: How do you reduce hallucination?

I reduce hallucination by:

- using retrieved context
- instructing the model to use only the provided context
- keeping the context small and focused
- adding team-specific prompting to narrow the scope

This does not eliminate hallucination completely, but it significantly reduces it compared to open-ended generation.

### Q: Why did you personalize the system prompt by team?

Different teams care about different things. DevOps focuses on reliability and deployments, Security focuses on threats and anomalies, and Operations focuses on process and customer impact. A team-specific prompt helps the model frame the answer appropriately for the user's domain.

## 8. Backend Questions

### Q: Why FastAPI?

FastAPI is a strong choice because it is simple, fast, and works well with async Python. It provides automatic request parsing, dependency injection, and clean route definitions, which made it a good fit for auth-protected APIs and AI endpoints.

### Q: What are the main backend modules?

- `app/main.py` defines the FastAPI app and the main routes
- `app/auth.py` handles JWT decoding and user resolution
- `app/issues.py` handles ingestion requests
- `app/analytics.py` exposes analytics APIs
- `agents/` defines the LangGraph flow
- `core/` contains vector, embeddings, analytics, and persistence logic
- `stream/` handles Kafka production and consumption

### Q: How is authentication implemented?

The frontend uses Supabase auth to log users in and get a JWT. The backend reads the JWT from the `Authorization` header, decodes it, verifies it, and then queries the `profiles` table in Supabase to resolve the user's email, role, and team.

### Q: Why use dependency injection for auth?

FastAPI dependencies make it easy to protect specific routes cleanly. It also avoids repeating auth logic in every endpoint.

## 9. Frontend Questions

### Q: Why did you use React and Vite?

React is a strong choice for building interactive dashboards and protected routes. Vite gives a fast development experience and simple frontend setup.

### Q: What does the frontend provide?

- login page
- signup page
- direct ask page
- multi-team dashboard page
- simulation page for generating incidents
- analytics page for system insights

### Q: How does the frontend call the backend securely?

It gets the Supabase session and includes the access token in the `Authorization: Bearer <token>` header when calling protected backend endpoints.

### Q: What is the purpose of the simulation page?

The simulation page helps demonstrate the system end to end. It generates realistic incidents such as database CPU alerts, failed deployments, and security warnings, which are then ingested by the backend and made available to the RAG system.

## 10. Database and Analytics Questions

### Q: Why use SQLite for analytics?

SQLite is lightweight and requires no additional infrastructure. For project demos and local development, it is enough to store metrics such as issue counts, query counts, response times, and trends.

### Q: What analytics do you capture?

- query count
- query response time
- approximate answer accuracy score
- issue count by team
- issue count by type
- trending issue categories
- time-series issue activity

### Q: Why track analytics in a RAG system?

Analytics help measure whether the system is useful. In a production setting, we would want to know response latency, popular questions, overloaded teams, trending issues, and whether retrieval quality is improving or degrading over time.

## 11. Technology Choice Questions

### Q: Why use SentenceTransformers `all-MiniLM-L6-v2`?

It is a practical embedding model because it is lightweight, fast, and produces 384-dimensional vectors. That makes it a good fit for local development

### Q: Why use BM25 if embeddings already exist?

Embeddings capture meaning, but BM25 captures direct term importance. Operational queries often contain precise identifiers, so BM25 helps recover those exact matches.

### Q: Why use SQLAlchemy instead of raw SQLite queries?

SQLAlchemy makes the analytics layer cleaner and easier to extend. It also separates schema definitions from query logic and is more maintainable than raw SQL strings scattered through the codebase.

### Q: Why use Supabase instead of building auth from scratch?

Supabase reduces boilerplate for signup, login, session handling, and token management. It allowed me to focus on the RAG and streaming architecture instead of spending most of the project building authentication infrastructure.

## 12. Design Tradeoff Questions

### Q: What tradeoffs did you make in this project?

I chose simplicity and demoability over full production hardening. For example:

- FAISS on local disk instead of a distributed vector database
- SQLite analytics instead of PostgreSQL or a warehouse
- simple reranking instead of a learned reranker
- direct Groq prompting instead of more advanced safety or citation layers
- lightweight team filtering rather than full row-level authorization enforcement everywhere

These choices made the system easier to build, explain, and run locally while still demonstrating strong system design ideas.

### Q: What are the biggest current limitations?

- authorization can be tightened further, especially around team switching and admin-only actions
- ingestion reliability can be improved with retries and dead-letter queues
- analytics are basic and local only
- the answer quality metric is only a proxy, not a true evaluation score
- there are limited automated tests

## 13. Security Questions

### Q: How does the system prevent unauthorized access?

Protected routes require authentication in both frontend and backend. The backend resolves the JWT and profile to determine user context. Team-based retrieval filtering further reduces access to irrelevant data.

### Q: Is this enough for production security?

Not fully. For production, I would strengthen role-based authorization, enforce allowed team access at the backend more strictly, lock down destructive routes like reset, add audit logging, and validate every privilege escalation path carefully.

### Q: What sensitive data could exist in a system like this?

Incident logs can contain infrastructure names, internal service information, security anomalies, or customer-impact data. That is why team-aware filtering and authenticated access are important.

## 14. Scaling Questions

### Q: How would you scale this system?

I would scale it in stages:

1. Move from local FAISS files to a shared vector database or service.
2. Run multiple API instances behind a load balancer.
3. Run consumer groups for ingestion scaling.
4. Add caching for repeated queries and profile lookups.
5. Use a more robust analytics backend such as PostgreSQL or ClickHouse.
6. Add background jobs, retries, and monitoring around stream processing.

### Q: What happens if issue volume grows significantly?

The current design benefits from asynchronous streaming, which already helps. But higher volume would require stronger partitioning, better consumer scaling, more efficient indexing strategy, and potentially a more advanced vector database.

## 15. Production Improvement Questions

### Q: If you had one more week, what would you improve?

- add test coverage for auth, retrieval, and ingestion
- enforce team authorization more strictly on the backend
- add citations or source snippets in answers
- improve reranking quality
- add retry and failure handling for Kafka operations
- add Docker support for the full stack
- improve observability dashboards

### Q: If you had one more month, what would you improve?

- production-grade deployment architecture
- managed database and vector infrastructure
- role-based admin tooling
- better evaluation datasets and retrieval benchmarks
- event schemas and schema validation
- per-team dashboards with richer analytics and alerting

## 16. Common "Why" Questions

### Q: Why not directly query the database instead of using RAG?

Structured databases are good for exact fields, but operational incident text is often semi-structured and descriptive. RAG helps answer natural-language questions over incident narratives, not just rigid columns.

### Q: Why not fine-tune a model instead of using RAG?

RAG is better when knowledge changes frequently. Fine-tuning is slower to update and is not ideal for live incident streams.

### Q: Why not use only keyword search?

Keyword search works for exact matches, but it fails when the user phrases the problem differently from the original incident text. Hybrid retrieval gives both semantic and lexical strength.

### Q: Why not make everything synchronous?

If embedding, indexing, and analytics were all synchronous inside the request path, ingestion latency would increase and the API would be less resilient under load. Streaming decouples those concerns.

## 17. Behavioral / Ownership Questions

### Q: What part of this project are you most proud of?

I am most proud of making the RAG system actually live instead of static. The combination of streaming ingestion, vector-store reloads, and team-aware retrieval makes the project more realistic and more aligned with real operational use cases.

### Q: What was the hardest part?

The hardest part was coordinating multiple concerns together: auth, retrieval, streaming, persistence, and frontend UX. Each one is manageable alone, but combining them into a coherent product is the challenging and interesting part.

### Q: What did you learn from building this?

I learned how important system boundaries are. Good AI output depends not only on the model, but also on ingestion design, retrieval quality, metadata quality, access control, and observability.

## 18. Strong Closing Answer

### Q: Why is this project a good demonstration of your skills?

This project demonstrates full-stack engineering, not just model usage. It includes frontend development, backend APIs, authentication, streaming, vector search, retrieval design, analytics, and system tradeoffs. It shows that I can build an end-to-end AI product, reason about architecture, and make practical decisions based on real constraints.
