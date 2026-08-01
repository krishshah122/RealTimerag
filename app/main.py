from fastapi import FastAPI, Body, Depends, Query, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.vector_store import VectorStore
from agents.graph import build_graph
from app.issues import router as issue_router
from app.analytics import router as analytics_router
from app.notifications import router as notifications_router
from app.admin import router as admin_router
from core.analytics import AnalyticsManager
from dotenv import load_dotenv
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from app.auth import auth_middleware, get_current_user, UserContext, supabase
from app.rbac import can_access_team
from core.summarizer import recommend_resolution
from core.correlation import find_similar_incidents
from jobs.scheduler import start_scheduler_in_thread
import time
import os
import uuid

load_dotenv()

print("LangSmith enabled:", os.getenv("LANGCHAIN_TRACING_V2"))
print("Project:", os.getenv("LANGSMITH_PROJECT"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    from config import VECTOR_BACKEND, QDRANT_HOST, QDRANT_PORT

    if VECTOR_BACKEND == "qdrant":
        try:
            from qdrant_client import QdrantClient
            client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            client.get_collections()
            print(f"Qdrant connected at {QDRANT_HOST}:{QDRANT_PORT}")
        except Exception as e:
            print(f"WARNING: Qdrant not reachable at {QDRANT_HOST}:{QDRANT_PORT} — {e}")
            print("Start with: docker compose up -d qdrant")

    start_scheduler_in_thread()
    yield


app = FastAPI(
    title="Real-Time Incident Intelligence Platform",
    version="2.0.0",
    lifespan=lifespan,
)

app.middleware("http")(auth_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(issue_router)
app.include_router(analytics_router)
app.include_router(notifications_router)
app.include_router(admin_router)


class RegisterRequest(BaseModel):
    email: str
    password: str
    team: str
    role: str = "analyst"


@app.post("/register")
async def register_user(req: RegisterRequest):
    if not supabase:
        raise HTTPException(500, "Supabase not configured")

    import asyncio
    try:
        user_res = await asyncio.to_thread(
            lambda: supabase.auth.admin.create_user({
                "email": req.email,
                "password": req.password,
                "email_confirm": True,
            })
        )
        user = user_res.user
    except Exception as e:
        raise HTTPException(400, f"User creation failed: {str(e)}")

    try:
        await asyncio.to_thread(
            lambda: supabase.table("profiles").upsert({
                "id": user.id,
                "email": req.email,
                "team_name": req.team,
                "role": req.role,
            }).execute()
        )
    except Exception as e:
        raise HTTPException(500, f"Profile creation failed: {str(e)}")

    return {"message": "User registered successfully", "user_id": user.id}


store = VectorStore()


@traceable(name="ask_request", run_type="chain")
async def _handle_ask(
    query: str,
    request_id: str,
    team: str | None,
    user_context: dict | None = None,
    mode: str = "ask",
    status_filter: str | None = None,
    severity_filter: str | None = None,
):
    # set_run_metadata was removed in newer langsmith versions; update
    # the current run tree's metadata instead when available.
    run_tree = get_current_run_tree()
    if run_tree:
        try:
            run_tree.add_metadata({"thread_id": request_id})
        except Exception as e:
            print(f"Failed to set LangSmith run metadata: {e}")
    graph = build_graph(store, mode=mode)
    initial_state: dict = {"query": query}
    if team:
        initial_state["team"] = team
    if user_context:
        initial_state["user_context"] = user_context
    if status_filter:
        initial_state["status_filter"] = status_filter
    if severity_filter:
        initial_state["severity_filter"] = severity_filter
    return await graph.ainvoke(initial_state)


@app.get("/documents")
async def list_documents(user: UserContext = Depends(get_current_user)):
    """List indexed documents (authenticated, team-scoped for non-admins)."""
    vs = VectorStore()
    docs = vs.store.docs
    if user.role != "admin" and user.team:
        docs = {
            k: v for k, v in docs.items()
            if v.get("metadata", {}).get("team_tag") == user.team
        }
    return docs


@app.post("/ask")
async def ask(
    query: str = Body(..., media_type="text/plain"),
    team_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    user: UserContext = Depends(get_current_user),
):
    team = team_id or user.team
    if not can_access_team(user, team):
        raise HTTPException(403, "You do not have access to this team's data")

    request_id = str(uuid.uuid4())[:8]
    user_context = {"email": user.email, "role": user.role}

    start_time = time.time()
    response = await _handle_ask(
        query, request_id, team, user_context,
        status_filter=status, severity_filter=severity,
    )
    response_time_ms = (time.time() - start_time) * 1000

    response_text = str(response.get("answer", "") if isinstance(response, dict) else response)
    accuracy = min(len(response_text) / 500, 1.0) * 0.9 + 0.1

    try:
        AnalyticsManager.track_query(request_id, query, team, response_time_ms, accuracy)
    except Exception as e:
        print(f"Analytics tracking failed: {e}")

    return response


@app.post("/summarize")
async def summarize(
    query: str = Body(..., media_type="text/plain"),
    team_id: str | None = Query(default=None),
    user: UserContext = Depends(get_current_user),
):
    """Summarize recent incidents matching a query."""
    team = team_id or user.team
    if not can_access_team(user, team):
        raise HTTPException(403, "Access denied")

    request_id = str(uuid.uuid4())[:8]
    response = await _handle_ask(
        query, request_id, team,
        user_context={"email": user.email, "role": user.role},
        mode="summarize",
    )
    return response


@app.post("/recommend")
async def recommend(
    query: str = Body(..., media_type="text/plain"),
    team_id: str | None = Query(default=None),
    user: UserContext = Depends(get_current_user),
):
    """Suggest resolution based on similar historical incidents."""
    team = team_id or user.team
    if not can_access_team(user, team):
        raise HTTPException(403, "Access denied")

    vs = VectorStore()
    similar = find_similar_incidents(query, vs, team=team, k=5)
    recommendation = await recommend_resolution(similar, query)
    return {"similar_incidents": similar, "recommendation": recommendation}
