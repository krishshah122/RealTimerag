from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware

from core.vector_store import VectorStore
from agents.graph import build_graph
from app.issues import router as issue_router

app = FastAPI()

# CORS (for React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(issue_router)
store = VectorStore()
@app.get("/documents")
def list_documents():
    return store.store.all()

@app.post("/ask")
def ask(query: str = Body(..., media_type="text/plain")):
    graph = build_graph(store)
    return graph.invoke({"query": query})

