from fastapi import FastAPI, Body, Depends, Query, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from core.vector_store import VectorStore
from agents.graph import build_graph
from app.issues import router as issue_router
from dotenv import load_dotenv
from langsmith import traceable
from langsmith.run_helpers import set_run_metadata
from app.auth import auth_middleware, get_current_user, UserContext, supabase

load_dotenv()   # MUST be first

import os
import uuid
print("LangSmith enabled:", os.getenv("LANGCHAIN_TRACING_V2"))
print("Project:", os.getenv("LANGSMITH_PROJECT"))

app = FastAPI()

# Attach Supabase auth middleware (extracts user from JWT when present)
app.middleware("http")(auth_middleware)

# CORS (for React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(issue_router)

class RegisterRequest(BaseModel):
    email: str
    password: str
    team: str

@app.post("/register")
def register_user(req: RegisterRequest):
    if not supabase:
        raise HTTPException(500, "Supabase not configured")

    # 1. Create User in Supabase Auth
    try:
        # admin.create_user auto-confirms email if configured, or sends email
        user_res = supabase.auth.admin.create_user({
            "email": req.email,
            "password": req.password,
            "email_confirm": True
        })
        user = user_res.user
    except Exception as e:
        # Check for specific error messages if possible, or just pass generic
        raise HTTPException(400, f"User creation failed: {str(e)}")

    # 2. Key Step: Create Profile (Bypassing RLS via Service Role Key)
    try:
        supabase.table("profiles").upsert({
            "id": user.id,
            "email": req.email,
            "team_name": req.team,
            "role": "user"
        }).execute()
    except Exception as e:
        # In a production app, we might want to delete the user here to rollback
        print(f"Profile creation failed: {e}")
        raise HTTPException(500, f"Profile creation failed: {str(e)}")
    
    return {"message": "User registered successfully", "user_id": user.id}


store = VectorStore()


@traceable(name="ask_request", run_type="chain")
def _handle_ask(query: str, request_id: str, team: str | None, user_context: dict | None = None):
    """One LangSmith trace per request (e.g. per refresh); all retrieve/answer spans nest under this run."""
    set_run_metadata(thread_id=request_id)
    graph = build_graph(store)
    # Pass team through the LangGraph state so retrieve/answer can be team-aware
    initial_state = {"query": query}
    if team:
        initial_state["team"] = team
    if user_context:
        initial_state["user_context"] = user_context
    return graph.invoke(initial_state)


@app.get("/documents")
def list_documents():
    return store.store.all()


@app.post("/ask")
def ask(
    query: str = Body(..., media_type="text/plain"),
    # Optional override to explicitly target a team (e.g. from dashboards)
    team_id: str | None = Query(default=None),
    user: UserContext = Depends(get_current_user),
):
    """
    Team-aware ask endpoint.

    - Authenticated via Supabase JWT (see `app/auth.py`)
    - Team is resolved from the user's profile, unless `team_id` query param overrides it
    """
    request_id = str(uuid.uuid4())[:8]
    team = team_id or user.team
    
    user_context = {
        "email": user.email,
        "role": user.role
    }
    
    return _handle_ask(query, request_id, team, user_context)

