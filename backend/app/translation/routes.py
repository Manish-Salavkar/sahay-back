# =====================================================================
# BACKEND/APP CHANGE SEPARATOR: TRANSLATION API ROUTES
# =====================================================================
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_metadata_db
from app.auth.services import get_current_user
from app.auth.models import User
from app.translation.schemas import (
    SaveTranslationInput,
    SaveReviewInput,
    DocumentTranslationOut,
    TranslationDocumentListItem,
    TranslationPaginatedResponse,
)
from app.translation.services import (
    get_translation_documents_service,
    get_single_translation_service,
    save_translation_service,
    save_review_service,
)


router = APIRouter(prefix="/translation", tags=["Translation Workspace"])


@router.get("/documents", response_model=TranslationPaginatedResponse)
async def list_translation_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    meta_db: AsyncSession = Depends(get_metadata_db),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns paginated list of documents with their current translation status.
    """
    return await get_translation_documents_service(
        meta_db=meta_db,
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status_filter,
    )


@router.get("/documents/{pdf_name:path}")
async def get_document_translation_detail(
    pdf_name: str,
    meta_db: AsyncSession = Depends(get_metadata_db),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetches single document details and translation draft.
    """
    return await get_single_translation_service(meta_db, db, pdf_name)


@router.post("/documents/{pdf_name:path}/save", response_model=DocumentTranslationOut)
async def save_document_translation(
    pdf_name: str,
    payload: SaveTranslationInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Saves translated content and sets translation status to 'Under Review'.
    """
    res = await save_translation_service(db, pdf_name, payload, current_user)
    await db.commit()
    return res


@router.post("/documents/{pdf_name:path}/review", response_model=DocumentTranslationOut)
async def save_document_review(
    pdf_name: str,
    payload: SaveReviewInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Saves review feedback ('Approved' or 'Needs Rework') with optional review note.
    """
    res = await save_review_service(
        db=db,
        pdf_name=pdf_name,
        action=payload.action,
        review_note=payload.review_note,
        current_user=current_user,
    )
    await db.commit()
    return res
# =====================================================================
# END OF BACKEND/APP CHANGE SEPARATOR
# =====================================================================
