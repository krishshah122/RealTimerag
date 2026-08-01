# Real-Time RAG: Exhaustive Module & Function Reference

This document serves as an exhaustive codebase dictionary for engineering interviews and technical dive-in rounds. It outlines the responsibilities, classes, methods, inputs, outputs, and internal algorithms for every python module and core frontend React component in the Real-Time RAG repository.

---

## Table of Contents
1. [API & Controller Layer (`rag/app/`)](#1-api--controller-layer-ragapp)
2. [Core Business & Storage Services (`rag/core/`)](#2-core-business--storage-services-ragcore)
3. [Retrieval & Ranking Engine (`rag/retrieval/`)](#3-retrieval--ranking-engine-ragretrieval)
4. [LangGraph Orchestration (`rag/agents/`)](#4-langgraph-orchestration-ragagents)
5. [Async Stream Architecture (`rag/stream/`)](#5-async-stream-architecture-ragstream)
6. [Background Jobs & Automation (`rag/jobs/` & `rag/simulation/`)](#6-background-jobs--automation-ragjobs--ragsimulation)
7. [Frontend Interactive Layer (`rag/frontend/src/`)](#7-frontend-interactive-layer-ragfrontendsrc)

---

## 1. API & Controller Layer (`rag/app/`)

This layer exposes RESTful endpoints, handles serialization, injects dependencies, enforces authentication, and triggers async execution.

### A. `app/main.py`
The API gateway application initializer and primary LLM interrogation route handler.
* **Key Functions / Routes**:
  * `create_app() -> FastAPI`: Configures CORS middleware, registers lifecycle routers, initializes SQLite schemas, and boots scheduled background cleaning tasks.
  * `POST /register`: Accepts `{email, password, team, role}`. Connects to Supabase admin client to establish user identities, setting custom metadata and fallback SQL profile population via triggers.
  * `POST /ask` (`ask(query_req: QueryRequest, user: UserContext = Depends(get_current_user))`): 
    * *Inputs*: `QueryRequest` (query string, mode=`"ask"|"summarize"`, lifecycle filters: `status`, `severity`).
    * *Outputs*: JSON containing generated LLM text answer, citation document fragments, and execution latency.
    * *Internal Flow*: Instantiates LangGraph state, passes query to `graph.ainvoke(initial_state)`, calculates elapsed processing time, and invokes `AnalyticsTracker.log_query()` before responding.

### B. `app/auth.py`
Handles zero-trust authentication via JSON Web Token (JWT) inspection and user state reconstruction.
* **Key Classes & Functions**:
  * `class UserContext(BaseModel)`: Immutable data structure storing authenticated state: `id`, `email`, `role`, and `team_name`.
  * `async def get_current_user(authorization: str = Header(...)) -> UserContext`:
    * *Logic*: Extracts Bearer token from header. Queries Supabase Auth REST endpoint (`/rest/v1/profiles?select=*&id=eq.{user_id}`) to pull verified role and team assignment. Rejects expired or tampered signatures with HTTP 401 Unauthorized.

### C. `app/rbac.py`
Role-Based Access Control dependency factory.
* **Key Functions**:
  * `def require_roles(allowed_roles: list[str])`: Returns an async dependency function that evaluates `UserContext.role`. If the user's role (e.g., `'analyst'`) is not in `allowed_roles` (e.g., `['admin', 'sre']`), raises HTTP 403 Forbidden.

### D. `app/issues.py` & `app/analytics.py` & `app/notifications.py`
* **`POST /log_issue`** (`issues.py`): Receives real-time alert event descriptions. Invokes Kafka producer `send("live_issues", event)` and simultaneously persists stateful record in SQLite via `IncidentManager.create()`.
* **`GET /analytics`** (`analytics.py`): Queries SQLite analytical engine to aggregate latency distributions, total query counts, keyword trending distributions, and total incident breakdowns per team.
* **`GET /notifications`** (`notifications.py`): Polling endpoint fetching unread real-time web socket style incident notifications assigned to the user's UUID or team domain.

---

## 2. Core Business & Storage Services (`rag/core/`)

### A. `core/vector_backends/qdrant_backend.py` (Default Production Backend)
Implements high-speed vector retrieval and index management over REST and gRPC protocols using Qdrant client library.
* **Class: `QdrantBackend`**:
  * `__init__()`: Establishes connections via `config.QDRANT_HOST` and triggers collection assurance routines.
  * `_ensure_collection()`: Checks if collection (`incidents`) exists. If missing, configures an **HNSW (Hierarchical Navigable Small World)** graph index using 384 dimensions and **Cosine Distance Metric**.
  * `_ensure_payload_indexes()`: Iterates over critical metadata fields (`team_tag`, `status`, `severity`, `service`) and executes `create_payload_index(..., field_schema=KEYWORD)` to enable instant pre-filtering before cosine distance checks.
  * `add_document(text: str, metadata: dict | None) -> int`: Calls `EmbeddingModel.encode()`, bundles vector array with document text payload, and commits atomic upsert via `client.upsert(points=[PointStruct(...)])`.
  * `search(query: str, k: int = 4, team_tag: str | None = None, status: str | None = None, severity: str | None = None) -> list[dict]`: 
    * *Core Magic*: Constructs Qdrant `Filter` utilizing `FieldCondition` array (e.g. matching exact team and uppercase status). Executes `.query_points(collection_name, query=vec, limit=k, query_filter=query_filter)`. Returns JSON list containing text, cosine similarity score (0.0 to 1.0), and unmasked metadata.
  * `all_docs() -> dict`: Uses pagination pointer (`client.scroll()`) without loading vector arrays (`with_vectors=False`) to export memory-light textual dictionaries for BM25 sparse evaluations.

### B. `core/vector_backends/faiss_backend.py` (Local Fallback Backend)
Provides entirely standalone memory/disk vector management without Docker dependencies.
* **Class: `FaissBackend`**:
  * Utilizes `faiss.IndexFlatIP` (Inner Product, which simulates Cosine Similarity when vectors are L2 normalized prior to insertion).
  * `_save()` & `reload()`: Synchronizes multi-process writes between ingestion worker and FastAPI server by atomically incrementing an ASCII timestamp integer within `data/version.txt` and dumping indexes via `faiss.write_index(self.index, "data/faiss.index")`.

### C. `core/vector_store.py` & `core/embeddings.py`
* **`class EmbeddingModel`** (`embeddings.py`): Singleton encapsulation of HuggingFace's `SentenceTransformer("BAAI/bge-small-en-v1.5")`. Enforces device agnostic compilation (CPU optimized, automatically offloading to CUDA if GPU detected).
* **`class VectorStore`** (`vector_store.py`): Factory router architecture. Dynamically loads `QdrantBackend` or `FaissBackend` based on runtime environmental toggles, shielding high-level LangGraph nodes from database-specific implementation syntax.

### D. `core/incidents.py` & `core/correlation.py`
* **`class IncidentStatus(str, Enum)`**: Validates finite state machines: `OPEN` -> `INVESTIGATING` -> `MITIGATED` -> `RESOLVED` -> `CLOSED`. Prevent forbidden state shifts (e.g., jumping from `CLOSED` directly to `INVESTIGATING` without reopening).
* **`class IncidentManager`**: CRUD orchestrator operating over SQLAlchemy ORM mapped models (`Incident`, `IncidentTimelineEvent`, `WebNotification`). Handles automated timeline audit trailing on every status change or RCA generation event.
* **`class IncidentCorrelator`** (`correlation.py`): Evaluates newly submitted alerts against historical records in Qdrant. If cosine similarity exceeds threshold ($\ge 0.85$) and occurs within a short duration window, automatically assigns matching `correlation_group` UUIDs to consolidate redundant alerting firestorms.

### E. `core/summarizer.py` & `core/notifications.py`
* **`async def summarize_incident(incident_id: str)`** (`summarizer.py`): Gathers all historical timeline logs and raw telemetry, calls Groq (`llama-3.1-8b-instant`), and populates structured RCA attributes (`summary`, `root_cause`, `impact`, `recommendation`) back into SQLite.
* **`class NotificationDispatcher`** (`notifications.py`): Multi-channel observer pattern routing critical alerts simultaneously to WebSocket queue tables (`web_notifications`), SMTP corporate email relays, and Slack/MS Teams webhook URLs.

---

## 3. Retrieval & Ranking Engine (`rag/retrieval/`)

This module houses the custom hybrid search mathematics and contextual relevance boosting pipelines.

### A. `retrieval/dense.py`
* **`class DenseRetriever`**: Minimalist wrapper that delegates semantic similarity queries down to the active vector database backend (`VectorStore.search(query, k=8)`). Captures contextual intent even when vocabulary diverges completely from source docs.

### B. `retrieval/bm.py` (Lexical Sparse Retriever)
* **`class SparseRetriever`**: Implements pure lexical TF-IDF keyword matching using **BM25Okapi** (`rank_bm25`). 
  * *Why needed*: Resolves semantic model weaknesses when queries search for highly specific alphanumeric UUIDs, Error codes (e.g., `ORA-12154`, `HTTP 502`), or specific machine hostnames (`db-prod-mumbai-01`).
  * *Algorithm*: Tokenizes all documents within the isolated team domain using case-folding and punctuation separation, computes inverse document frequency weights, and scores candidate strings against token occurrences.

### C. `retrieval/rrf.py` (Reciprocal Rank Fusion)
* **`def rrf(dense: list[dict], sparse: list[tuple[str, float]], k=60) -> list[str]`**:
  * *Purpose*: Merges disparate score scales (Cosine Similarity ranging $[0,1]$ vs BM25 unbounded positive scores $[0, \infty)$) without fragile mathematical score normalizations.
  * *Formula*: For every document $d$ present across rankings:
    $$RRF\_Score(d) = \sum_{m \in \{dense, sparse\}} \frac{1}{k + \text{rank}_m(d)}$$
  * Where $\text{rank}_m(d)$ is the 1-indexed ordinal position of the document in retriever $m$, and $k$ is a standard smoothing constant ($k=60$) preventing high ranking outliers in one system from obliterating consensus matches.

### D. `retrieval/recency.py` (Temporal Severity Weighting)
* **`def apply_recency_boost(docs: list[dict], decay_factor=0.1) -> list[dict]`**:
  * *Operational Realism*: A P99 latency outage occurring 5 minutes ago is infinitely more critical than an identically worded outage from 3 weeks ago.
  * *Algorithm*: Evaluates timestamps against severity class expiration tolerances (`CRITICAL` -> 48h, `HIGH` -> 24h, `MEDIUM` -> 12h, `LOW` -> 6h). Applies exponential temporal decay math: $\text{final\_score} = \text{base\_score} \times \exp(-\lambda \times \text{hours\_elapsed})$, forcing fresh emergency events to the very top of the ranking context.

### E. `retrieval/rerank.py`
* **`def simple_rerank(query: str, docs: list[dict]) -> list[dict]`**: A zero-cost CPU token overlap sorter applied as a final polish stage. Sorts candidates primarily by normalized RRF & Recency combined weight, breaking ties by counting exact word set intersections between query strings and retrieved incident narratives.

---

## 4. LangGraph Orchestration (`rag/agents/`)

Instead of linear procedural scripting, execution flows through an explicit, auditable State Machine Graph capable of multi-step reasoning cycles.

### A. `agents/state.py`
* **`class RAGState(TypedDict)`**: Strongly typed state mapping containing: `query`, `mode` (`"ask"` vs `"summarize"`), `team`, `user_context`, lifecycle filters (`status_filter`, `severity_filter`), `docs` (array of selected top text blocks), and `answer` (final output text).

### B. `agents/graph.py`
* **`def build_graph(vector_store, mode="ask") -> CompiledGraph`**: 
  * Constructs LangGraph `StateGraph(RAGState)`.
  * Injects executable node functions: adds `"retrieve"` node pointing to `retrieve_node`, and conditionally registers `"answer"` or `"summarize"` nodes based on execution modality. 
  * Connects direct transitions (`graph.add_edge("retrieve", "answer")`) and compiles runnable Directed Acyclic Graph (DAG).

### C. `agents/nodes.py`
* **`def retrieve_node(state, _)`**: Executes steps 1-6 of the RAG data pipeline: queries dense vectors, calls BM25, merges via RRF, calculates temporal decay weights, reranks candidates, and populates `state["docs"]` exclusively with the **Top 3 scoring contextual narratives** to prevent context window dilution.
* **`def _system_prompt_for_team(team, user_context)`**: Dynamic persona builder. Customizes LLM framing based on team assignment (e.g., instructing the model to act as a *DevOps SRE Reliability Assistant* vs a *Cybersecurity Forensics Investigator*), reinforcing professional operational etiquette and addressing the querying user by explicit role and email identity.
* **`async def answer_node(state)`**: Initiates async HTTPS communication via `AsyncGroq(api_key)` client. Enforces stringent system constraints: *"Using ONLY the incident context below: Explain relevant incidents in your own words. Note severity, status, and recency when available. Do NOT add external assumptions."* Generates non-hallucinatory synthesized responses.

---

## 5. Async Stream Architecture (`rag/stream/`)

### A. `stream/producer.py` & `stream/consumer.py`
* **`producer.py`**: Exports `KafkaProducer` singleton tied to Redpanda TCP sockets (`localhost:9092`). Configures automatic UTF-8 stringification and JSON byte payload serialization.
* **`consumer.py`**: Autonomous background processing loop. Binds to consumer group monitoring topic `"live_issues"` with offset reset strategy set to `"latest"`. On event interception, extracts core text, applies intelligent fallback tagging for missing timestamps or severity metrics, and feeds vectors directly into `VectorStore.add_document()`.

---

## 6. Background Jobs & Automation (`rag/jobs/` & `rag/simulation/`)

### A. `jobs/scheduler.py` & `jobs/cleanup.py`
* **`scheduler.py`**: Initializes background **APScheduler** instance tied directly into FastAPI server lifecycle events.
* **`cleanup.py`**: Registers recurring midnight cleanup task (`@scheduler.scheduled_job('cron', hour=0)`). Scans relational SQLite incident databases for alerts lingering in `CLOSED` state for over 30 days, archiving rows and purging associated stale Qdrant vector coordinates to maintain optimal vector RAM utilization and search accuracy.

### B. `simulation/alert_generator.py`
* **`class AlertSimulator`**: Provides automated testing harness and demonstration engine. Generates continuous multi-cloud simulated incident scenarios across specialized team domains (e.g., simulating Kubernetes `CrashLoopBackOff` failures, RDS PostgreSQL connection saturation, Kafka broker partition disk exhaustion, and external brute-force login Splunk pattern recognitions).

---

## 7. Frontend Interactive Layer (`rag/frontend/src/`)

### A. Core Pages & Dashboards
* **`App.jsx`**: Main navigation routing wrapper using React Router. Enforces protective session guarding (redirecting unauthenticated visitors to `/login` via Supabase OAuth state watchers).
* **`IssuesDashboard.jsx` & `IncidentsPage.jsx`**: Rich visual operational command centers. Displays live filtering badges (severity tags, status transitions, team designations). Integrates directly with backend APIs to render interactive incident lifecycles, enabling engineers to advance incidents through operational states (`OPEN` -> `MITIGATED` -> `RESOLVED`) with real-time UI synchronization.
* **`AnalyticsPage.jsx` & `QueryAnalyticsChart.jsx`**: Data observation decks utilizing visual rendering libraries to display response latency charts, RAG query accuracy approximations, and team activity heatmaps over time.
* **`NotificationsBell.jsx`**: Header indicator component continuously pinging backend polling routers (`/notifications?unread_only=true`) to display emergency numerical alert badges on incident trigger occurrences.

### B. API Transport Layer (`api.js` & `supabaseClient.js`)
* **`supabaseClient.js`**: Instantiates global public frontend Supabase connection handles utilizing project URL and Anon keys for client-side authentication handshakes.
* **`api.js`**: Universal HTTP interception utility utilizing `axios` / standard browser fetch APIs. Dynamically injects fresh cryptographic Supabase session JWTs directly into outgoing request header blocks (`Authorization: Bearer <session.access_token>`), ensuring foolproof identity transfer to FastAPI security guards.
