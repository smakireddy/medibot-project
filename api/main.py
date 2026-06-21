from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import auth, chat, collections, health
from core.vector_store import ensure_collection


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup — ensures Qdrant collection + access_roles index exist
    ensure_collection()
    yield
    # shutdown — nothing to clean up


app = FastAPI(
    title="MediBot API",
    description="Hybrid RAG with RBAC for MediAssist Health Network",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(collections.router)
app.include_router(health.router)
