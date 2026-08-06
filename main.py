# backend/app/main.py

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.auth import models as auth_models
from app.auth import routes as auth_routes
from app.chatbot.routes import router as chatbot_router
from app.dashboard.routes import router as dashboard_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    lifespan=lifespan
)

# Allow all CORS (Development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", # Vite default
        "http://localhost:3000", # React standard
        "http://127.0.0.1:5173",
        "http://localhost:5500"  # Live Server
        "http://10.70.243.129:5173"    
        ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Routers
app.include_router(auth_routes.router)
app.include_router(chatbot_router)
app.include_router(dashboard_router)