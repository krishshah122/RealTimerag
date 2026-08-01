# Real-Time Incident Intelligence Platform

**Version 2.0.0**

A production-inspired Retrieval-Augmented Generation (RAG) system for engineering and operations teams to monitor, investigate, and understand operational incidents in real time.

Unlike traditional RAG systems that rely on static documents, this platform continuously ingests incident events, indexes them with lifecycle metadata, and enables team-specific question answering through a secure dashboard.

> **Interview positioning:** Describe this as *"a production-inspired incident intelligence system demonstrating real-time ingestion, team-aware retrieval, hybrid search, authenticated access, analytics, and LLM-powered incident investigation workflows."*

---

## What This Platform Does

| Capability | Description |
|---|---|
| Real-time ingestion | Incidents flow through Kafka/Redpanda into the vector index |
| Incident lifecycle | OPEN ? INVESTIGATING ? MITIGATED ? RESOLVED ? CLOSED |
| Time-aware retrieval | Recency-weighted hybrid search (semantic + BM25 + decay) |
| Summarization agent | Auto-generates summary, root cause, impact, recommendation |
| Smart correlation | Groups related incidents by service + error pattern |
| Similar incidents | "Have we seen this before?" via semantic search |
| Resolution recommendations | LLM suggestions from historical similar incidents |
| RCA generation | Automated Root Cause Analysis reports |
| Notifications | Web, Slack, Teams, Email channels |
| RBAC | Admin, Team Lead, SRE, Engineer, Analyst roles |
| Analytics | MTTR, severity distribution, top services, trends |
| Auto cleanup | Background job archives and purges expired incidents |
| Alert generator | Simulates 500+ realistic monitoring alerts |

---

## Architecture

```text
Alert Generator / Simulation / Client
        ?
        ?
  FastAPI /log_issue
        ?
        ???? Incident DB (SQLite lifecycle)
        ???? Summarization Agent (Groq)
        ???? Correlation Engine
        ???? Notification Service
        ?
        ?
 Kafka / Redpanda (live_issues)
        ?
        ?
   stream/consumer.py
        ?
        ?
 Embeddings (BGE) ? Qdrant (default)

Authenticated User
        ?
        ?
 React Dashboard ? /ask, /incidents, /analytics
        ?
        ?
 LangGraph: retrieve ? answer | summarize
        ?
        ??? Dense (Qdrant)
        ??? Sparse (BM25)
        ??? RRF fusion
        ??? Recency weighting
        ??? Reranking
        ?
        ?
 Groq LLM response
```

---

## Tech Stack & Versions

### Backend
| Component | Technology | Version |
|---|---|---|
| API | FastAPI | ? 0.115 |
| Orchestration | LangGraph | ? 0.2 |
| LLM | Groq (llama-3.1-8b-instant) | ? 0.13 |
| Embeddings | BGE-small-en-v1.5 (SentenceTransformers) | ? 3.3 |
| Vector DB | **Qdrant** (default) or FAISS (optional fallback) | qdrant v1.12 / faiss-cpu optional |
| Lexical search | rank-bm25 | ? 0.2 |
| Streaming | Kafka-python + Redpanda | v24.2 |
| Analytics | SQLAlchemy + SQLite | ? 2.0 |
| Auth | Supabase + JWT | ? 2.10 |
| Scheduler | APScheduler | ? 3.10 |

### Frontend
| Component | Technology | Version |
|---|---|---|
| UI | React | 19 |
| Build | Vite | latest |
| Routing | React Router | latest |
| Auth | Supabase JS | latest |
| Styling | Tailwind + custom CSS | � |

---

## Project Structure

```text
rag/
??? agents/              # LangGraph pipeline (retrieve, answer, summarize)
??? app/                 # FastAPI routes (auth, issues, incidents, analytics, admin)
??? core/                # Vector store, incidents, notifications, correlation, summarizer
?   ??? vector_backends/ # Qdrant (default) + FAISS (fallback)
??? retrieval/           # Dense, BM25, RRF, rerank, recency
??? stream/              # Kafka producer + consumer
??? simulation/          # Alert generator
??? jobs/                # Background cleanup scheduler
??? frontend/            # React SPA
??? data/                # FAISS files only when VECTOR_BACKEND=faiss
??? scripts/             # migrate_faiss_to_qdrant.py
??? docker-compose.yaml  # Redpanda + Qdrant
??? config.py
??? requirements.txt
```

---

## API Endpoints

### Authentication
| Method | Path | Description |
|---|---|---|
| POST | `/register` | Create user + profile with team and role |

### Incidents & Ingestion
| Method | Path | Description |
|---|---|---|
| POST | `/log_issue` | Ingest incident (lifecycle + Kafka + summarize) |
| GET | `/incidents` | List incidents (filter by status, severity, team) |
| GET | `/incidents/{id}` | Detail + timeline + correlated incidents |
| PATCH | `/incidents/{id}/status` | Lifecycle state transition |
| PATCH | `/incidents/{id}/summary` | Update summary fields (SRE+) |
| GET | `/incidents/{id}/similar` | Similar historical incidents |
| GET | `/incidents/{id}/rca` | Generate RCA report |
| DELETE | `/issues/{id}` | Delete incident (owner or admin) |

### RAG & Intelligence
| Method | Path | Description |
|---|---|---|
| POST | `/ask` | Team-aware RAG Q&A (optional status/severity filters) |
| POST | `/summarize` | Summarize incidents matching a query |
| POST | `/recommend` | Resolution recommendation from similar incidents |
| GET | `/documents` | List indexed docs (auth required, team-scoped) |

### Notifications
| Method | Path | Description |
|---|---|---|
| GET | `/notifications` | Web dashboard notifications |
| POST | `/notifications/{id}/read` | Mark notification read |

### Simulation
| Method | Path | Description |
|---|---|---|
| POST | `/simulation/generate?count=N` | Bulk alert generator |
| POST | `/simulation/single` | Single random alert |

### Analytics
| Method | Path | Description |
|---|---|---|
| GET | `/analytics/dashboard` | Full dashboard (MTTR, severity, services) |
| GET | `/analytics/mttr` | Mean Time To Resolution |
| GET | `/analytics/severity` | Severity distribution |
| GET | `/analytics/services` | Top affected services |

### Admin
| Method | Path | Description |
|---|---|---|
| POST | `/admin/reset` | Reset all data (admin only) |
| POST | `/admin/cleanup` | Trigger cleanup job (admin only) |

---

## Incident Lifecycle

```json
{
  "incident_id": "a1b2c3d4",
  "status": "OPEN",
  "severity": "critical",
  "service": "payment-service",
  "created_at": "2026-06-18T10:00:00",
  "resolved_at": null,
  "summary": "...",
  "root_cause": "...",
  "impact": "...",
  "recommendation": "..."
}
```

**States:** OPEN ? INVESTIGATING ? MITIGATED ? RESOLVED ? CLOSED

**Example queries:**
- "Show open critical incidents"
- "What incidents were resolved this week?"
- "Have we seen database connection exhaustion before?"

---

## Time-Aware Retrieval

Final ranking score combines:

```text
Final Score = 0.5 � Semantic Similarity + 0.3 � BM25 + 0.2 � Recency Weight
```

**Default recency windows:**
| Severity | Window |
|---|---|
| Critical | 90 days |
| High | 60 days |
| Normal/Medium/Low | 30 days |

---

## RBAC Roles

| Role | Permissions |
|---|---|
| Analyst | Read incidents, ask questions, view analytics |
| Engineer | + Log issues, delete own issues |
| SRE | + Update summaries, transition status |
| Team Lead | + Access any team's data |
| Admin | + Reset system, trigger cleanup, delete any issue |

Set role in Supabase `profiles.role` or at registration.

---

## Environment Variables

### Backend (`rag/.env`)

```env
GROQ_API_KEY=your_groq_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_JWT_SECRET=your_jwt_secret

# Vector backend � Qdrant is the default
VECTOR_BACKEND=qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=incidents

# Embeddings (default: BGE-small)
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIM=384

# Notifications (optional)
SLACK_WEBHOOK_URL=
TEAMS_WEBHOOK_URL=
SMTP_HOST=
SMTP_USER=
SMTP_PASSWORD=

# Optional LangSmith
LANGCHAIN_TRACING_V2=true
LANGSMITH_PROJECT=incident-intelligence
LANGCHAIN_API_KEY=your_key
```

### Frontend (`frontend/.env`)

```env
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_anon_key
```

---

## How To Run

### 1. Install dependencies

```bash
cd rag
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt

cd frontend
npm install
```

### 2. Start infrastructure

```bash
cd rag
docker compose up -d           # Redpanda + Qdrant
```

### 3. Start services

```bash
# Terminal 1 � API (includes cleanup scheduler)
cd rag
uvicorn app.main:app --reload --port 8000

# Terminal 2 � Kafka consumer
cd rag
python -m stream.consumer

# Terminal 3 � Frontend
cd rag/frontend
npm run dev
```

Open **http://localhost:5173**

### 4. Quick demo flow

1. Sign up with a team (e.g. `devops`) and role (`engineer`)
2. Go to **Simulate** ? Generate 10 alerts
3. Go to **Incidents** ? View lifecycle, timeline, similar incidents
4. Go to **Ask AI** ? "What critical incidents are open?"
5. Go to **Analytics** ? View MTTR and severity distribution

---

## Qdrant Setup (Default)

The app now uses **Qdrant by default**. FAISS code remains as an optional fallback only.

### What you need

| Item | Purpose |
|---|---|
| `docker compose up -d` | Starts Qdrant on port **6333** + Redpanda on **9092** |
| `pip install qdrant-client` | Python client (in `requirements.txt`) |
| `VECTOR_BACKEND=qdrant` | Set in `.env` (already the default) |
| `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION` | Connection settings |

### What was removed from the active path

| FAISS artifact | Status |
|---|---|
| `data/faiss.index` | **Not used** when `VECTOR_BACKEND=qdrant` |
| `data/docs.json` | **Not used** � Qdrant stores payloads |
| `data/version.txt` | **Not used** � no disk reload needed |
| `core/persistence.py` | **Kept** � only for FAISS fallback |
| `core/vector_backends/faiss_backend.py` | **Kept** � set `VECTOR_BACKEND=faiss` to use |

### Why Qdrant is better here

- API and Kafka consumer share the **same remote index** (no `version.txt` reload)
- Native **metadata filtering** (`team_tag`, `status`, `severity`, `issue_id`)
- Persistent volume via Docker (`qdrant_data`)
- Scales beyond single-machine file storage

### Verify Qdrant is working

```bash
# 1. Check container
docker ps | findstr qdrant

# 2. Check API (admin token required)
curl http://localhost:6333/collections

# 3. After starting API � look for this log:
#    "Using Qdrant vector backend"

# 4. Admin endpoint
GET /admin/vector-status
# ? { "backend": "qdrant", "document_count": N }
```

### Migrate existing FAISS data (one-time)

If you have old data in `data/docs.json`:

```bash
cd rag
pip install qdrant-client
docker compose up -d qdrant
python -m scripts.migrate_faiss_to_qdrant
```

### FAISS fallback (optional, no Docker)

Only if you cannot run Qdrant:

```env
VECTOR_BACKEND=faiss
```

```bash
pip install faiss-cpu
```

FAISS stores data in `rag/data/` and uses `version.txt` for cross-process sync.

---

## Frontend Pages

| Route | Page |
|---|---|
| `/login` | Sign in |
| `/signup` | Account creation |
| `/ask` | RAG question answering |
| `/incidents` | Lifecycle management, timeline, RCA |
| `/simulation` | Preset scenarios + alert generator |
| `/analytics` | MTTR, severity, services, trends |
| `/backend` | Team-specific chat tabs |

---

## Simulation Strategy

Simulation demonstrates architecture without requiring PagerDuty, Datadog, or Splunk access.

The **Alert Generator** produces realistic incidents:
- CPU > 90%
- Memory leak detected
- API latency spike
- Database connection exhaustion
- Disk usage exceeded threshold

Flow: `Simulation Engine ? Kafka ? Consumer ? Indexing`

---

## Automatic Cleanup

A background scheduler runs daily (configurable via `CLEANUP_INTERVAL_HOURS`):

1. Archive resolved incidents older than `RETENTION_DAYS_RESOLVED` (default 365)
2. Purge archived vectors older than `RETENTION_DAYS_CLOSED` (default 180)
3. Compress analytics records

Manual trigger: `POST /admin/cleanup` (admin only)

---

## License

MIT. See `LICENSE`.
##Qdrant has a built-in web dashboard. Open this in your browser:

http://localhost:6333/dashboard