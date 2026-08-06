# =====================================================================
# BACKEND/APP CHANGE SEPARATOR: TRANSLATION BUSINESS SERVICES
# =====================================================================
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.chatbot.models import GRMetadata
from app.translation.models import DocumentTranslation
import math
from app.translation.schemas import (
    SaveTranslationInput,
    DocumentTranslationOut,
    TranslationDocumentListItem,
    TranslationPaginatedResponse,
)

from app.auth.models import User


def safe_int_conversion(val):
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


from sqlalchemy import text


async def ensure_translation_table_schema(db: AsyncSession):
    try:
        await db.execute(text("ALTER TABLE document_translations ADD COLUMN review_note TEXT;"))
        await db.commit()
    except Exception:
        await db.rollback()

    try:
        await db.execute(text("ALTER TABLE document_translations ADD COLUMN reviewer_name VARCHAR;"))
        await db.commit()
    except Exception:
        await db.rollback()


async def get_translation_documents_service(
    meta_db: AsyncSession,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    status_filter: str | None = None,
) -> TranslationPaginatedResponse:
    """
    Fetches GR metadata documents with translation statuses, applying search, status filtering, and pagination.
    """
    await ensure_translation_table_schema(db)

    # 1. Fetch GR Metadata from metadata.db
    gr_result = await meta_db.execute(select(GRMetadata).order_by(GRMetadata.pdf_name.asc()))
    gr_docs = gr_result.scalars().all()

    # 2. Fetch existing translations from maharashtra_ai.db
    trans_result = await db.execute(select(DocumentTranslation))
    translations = {t.pdf_name: t for t in trans_result.scalars().all()}

    # 3. Combine GR metadata with translation status and count totals
    all_items = []
    pending_count = 0
    under_review_count = 0
    rework_count = 0
    approved_count = 0

    for doc in gr_docs:
        trans = translations.get(doc.pdf_name)
        status_val = trans.translation_status if trans else "Translation Pending"
        if status_val == "Under Review":
            under_review_count += 1
        elif status_val == "Needs Rework" or status_val == "Rework":
            rework_count += 1
        elif status_val == "Approved":
            approved_count += 1
        else:
            pending_count += 1

        trans_title = trans.translated_title if trans else None
        trans_content = trans.translated_content if trans else None
        rev_note = trans.review_note if trans else None
        updated_val = trans.updated_at if trans else None

        item = TranslationDocumentListItem(
            pdf_name=doc.pdf_name,
            gr_number=doc.gr_number,
            title=doc.title,
            department=doc.department,
            date=doc.date,
            number_of_pages=safe_int_conversion(doc.number_of_pages),
            translation_status=status_val,
            translated_title=trans_title,
            translated_content=trans_content,
            review_note=rev_note,
            updated_at=updated_val,
        )
        all_items.append(item)

    # 4. Filter by search query
    filtered = all_items
    if search:
        s_lower = search.lower()
        filtered = [
            i for i in filtered
            if (i.title and s_lower in i.title.lower()) or
               (i.pdf_name and s_lower in i.pdf_name.lower()) or
               (i.department and s_lower in i.department.lower()) or
               (i.translated_title and s_lower in i.translated_title.lower())
        ]

    # 5. Filter by translation status
    if status_filter and status_filter.upper() != "ALL":
        filtered = [i for i in filtered if i.translation_status == status_filter]

    total = len(filtered)
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    current_page = max(1, min(page, total_pages))

    start_idx = (current_page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_items = filtered[start_idx:end_idx]

    return TranslationPaginatedResponse(
        items=paginated_items,
        total=total,
        page=current_page,
        page_size=page_size,
        total_pages=total_pages,
        pending_count=pending_count,
        under_review_count=under_review_count,
        rework_count=rework_count,
        approved_count=approved_count,
    )


async def get_single_translation_service(
    meta_db: AsyncSession,
    db: AsyncSession,
    pdf_name: str,
) -> dict:
    """
    Fetches details of a single document along with its translation status and draft.
    """
    await ensure_translation_table_schema(db)

    gr_doc = (
        await meta_db.execute(
            select(GRMetadata).where(GRMetadata.pdf_name == pdf_name)
        )
    ).scalar_one_or_none()

    if not gr_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    trans = (
        await db.execute(
            select(DocumentTranslation).where(DocumentTranslation.pdf_name == pdf_name)
        )
    ).scalar_one_or_none()

    return {
        "pdf_name": gr_doc.pdf_name,
        "gr_number": gr_doc.gr_number,
        "title": gr_doc.title,
        "department": gr_doc.department,
        "date": gr_doc.date,
        "summary": gr_doc.summary,
        "translation_status": trans.translation_status if trans else "Translation Pending",
        "translated_title": trans.translated_title if trans else "",
        "translated_content": trans.translated_content if trans else "",
        "review_note": trans.review_note if trans else "",
        "translator_name": trans.translator_name if trans else None,
        "reviewer_name": trans.reviewer_name if trans else None,
        "updated_at": trans.updated_at if trans else None,
    }


async def save_translation_service(
    db: AsyncSession,
    pdf_name: str,
    payload: SaveTranslationInput,
    current_user: User,
) -> DocumentTranslationOut:
    """
    Saves or updates translation draft and updates status to 'Under Review'.
    """
    # Safely pre-extract user primitive values before executing DB queries
    translator_id = getattr(current_user, "id", None)
    translator_name = getattr(current_user, "full_name", None) or getattr(current_user, "employee_id", "Translator")

    await ensure_translation_table_schema(db)

    trans = (
        await db.execute(
            select(DocumentTranslation).where(DocumentTranslation.pdf_name == pdf_name)
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if not trans:
        trans = DocumentTranslation(
            pdf_name=pdf_name,
            translated_title=payload.translated_title,
            translated_content=payload.translated_content,
            translation_status=payload.translation_status or "Under Review",
            review_note=payload.review_note,
            translator_id=translator_id,
            translator_name=translator_name,
            created_at=now,
            updated_at=now,
        )
        db.add(trans)
    else:
        if payload.translated_title is not None:
            trans.translated_title = payload.translated_title
        if payload.translated_content is not None:
            trans.translated_content = payload.translated_content
        trans.translation_status = payload.translation_status or "Under Review"
        if payload.review_note is not None:
            trans.review_note = payload.review_note
        trans.translator_id = translator_id
        trans.translator_name = translator_name
        trans.updated_at = now

    await db.flush()
    await db.refresh(trans)

    return DocumentTranslationOut.model_validate(trans)


async def save_review_service(
    db: AsyncSession,
    pdf_name: str,
    action: str,
    review_note: str | None,
    current_user: User,
) -> DocumentTranslationOut:
    """
    Saves review status ('Approved' or 'Needs Rework') along with optional reviewer note.
    """
    # Safely pre-extract reviewer name before executing DB queries
    reviewer_name = getattr(current_user, "full_name", None) or getattr(current_user, "employee_id", "Reviewer")

    await ensure_translation_table_schema(db)

    trans = (
        await db.execute(
            select(DocumentTranslation).where(DocumentTranslation.pdf_name == pdf_name)
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    new_status = "Approved" if action.upper() == "APPROVE" else "Needs Rework"

    if not trans:
        trans = DocumentTranslation(
            pdf_name=pdf_name,
            translation_status=new_status,
            review_note=review_note,
            reviewer_name=reviewer_name,
            created_at=now,
            updated_at=now,
        )
        db.add(trans)
    else:
        trans.translation_status = new_status
        trans.review_note = review_note
        trans.reviewer_name = reviewer_name
        trans.updated_at = now

    await db.flush()
    await db.refresh(trans)

    return DocumentTranslationOut.model_validate(trans)
# =====================================================================
# END OF BACKEND/APP CHANGE SEPARATOR
# =====================================================================
