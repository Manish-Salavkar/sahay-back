# backend\app\database.py
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL, METADATA_DATABASE_URL

# ==============================================================================
# 1. AUTH & APP STATE DATABASE (maharashtra_ai.db)
# ==============================================================================
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    """Base class for Auth and User-related models (maharashtra_ai.db)"""
    pass


async def get_db():
    """Dependency for Auth & User operations"""
    async with SessionLocal() as session:
        yield session


# ==============================================================================
# 2. GR METADATA DATABASE (metadata.db)
# ==============================================================================
metadata_engine = create_async_engine(
    METADATA_DATABASE_URL,
    echo=False,
)

MetadataSessionLocal = async_sessionmaker(
    bind=metadata_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class MetadataBase(DeclarativeBase):
    """Base class for Document & GR Metadata models (metadata.db)"""
    pass


async def get_metadata_db():
    """Dependency for RAG & GR Metadata lookup operations"""
    async with MetadataSessionLocal() as session:
        yield session


# ==============================================================================
# INITIALIZATION
# ==============================================================================
async def init_db():
    """
    Creates tables for Auth models in maharashtra_ai.db.
    Assumes metadata.db is already created and populated by the ingestion pipeline.
    """
    # Only create tables for the Auth/App DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # We explicitly omit MetadataBase.metadata.create_all to ensure we are 
    # strictly connecting to the pre-existing metadata database.