# =====================================================================
# BACKEND/APP CHANGE SEPARATOR: TRANSLATION PYDANTIC SCHEMAS
# =====================================================================
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class SaveTranslationInput(BaseModel):
    translated_title: Optional[str] = None
    translated_content: Optional[str] = None
    translation_status: str = "Under Review"
    review_note: Optional[str] = None


class SaveReviewInput(BaseModel):
    action: str  # "APPROVE" or "REWORK"
    review_note: Optional[str] = None


class DocumentTranslationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pdf_name: str
    translated_title: Optional[str] = None
    translated_content: Optional[str] = None
    translation_status: str = "Translation Pending"
    review_note: Optional[str] = None
    translator_id: Optional[int] = None
    translator_name: Optional[str] = None
    reviewer_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TranslationDocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pdf_name: str
    gr_number: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    date: Optional[str] = None
    number_of_pages: Optional[int] = None
    translation_status: str = "Translation Pending"
    translated_title: Optional[str] = None
    translated_content: Optional[str] = None
    review_note: Optional[str] = None
    updated_at: Optional[datetime] = None


class TranslationPaginatedResponse(BaseModel):
    items: list[TranslationDocumentListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    pending_count: int
    under_review_count: int
    rework_count: int
    approved_count: int
# =====================================================================
# END OF BACKEND/APP CHANGE SEPARATOR
# =====================================================================
