# backend/app/main.py
import sys
if not hasattr(sys, "get_int_max_str_digits"):
    sys.get_int_max_str_digits = lambda: 4300
if not hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits = lambda maxdigits: None

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.auth import models as auth_models
from app.auth import routes as auth_routes
from app.chatbot.routes import router as chatbot_router
from app.dashboard.routes import router as dashboard_router


# =====================================================================
# BACKEND/APP CHANGE SEPARATOR: INITIAL SEED ADMIN EXECUTION
# =====================================================================
from app.database import SessionLocal
from app.auth.services import seed_initial_admin_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with SessionLocal() as session:
        await seed_initial_admin_service(session)
    yield
# =====================================================================
# END OF BACKEND/APP CHANGE SEPARATOR
# =====================================================================


app = FastAPI(
    lifespan=lifespan
)

# Allow all CORS (Development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Routers
app.include_router(auth_routes.router)
app.include_router(chatbot_router)
app.include_router(dashboard_router)

# =====================================================================
# BACKEND/APP CHANGE SEPARATOR: TRANSLATION ROUTER INCLUSION
# =====================================================================
from app.translation.routes import router as translation_router
app.include_router(translation_router)
# =====================================================================
# END OF BACKEND/APP CHANGE SEPARATOR
# =====================================================================