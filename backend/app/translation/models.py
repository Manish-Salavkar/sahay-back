# =====================================================================
# BACKEND/APP CHANGE SEPARATOR: TRANSLATION DATABASE MODEL
# =====================================================================
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime
from app.database import Base


class DocumentTranslation(Base):
    """
    SQLAlchemy model for document_translations table in maharashtra_ai.db.
    Stores translated titles, translation editor contents, and translation workflow status.
    """
    __tablename__ = "document_translations"

    pdf_name = Column(String, primary_key=True, index=True)
    translated_title = Column(Text, nullable=True)
    translated_content = Column(Text, nullable=True)
    translation_status = Column(String, nullable=False, default="Translation Pending")
    review_note = Column(Text, nullable=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String, nullable=True)
    reviewer_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
# =====================================================================
# END OF BACKEND/APP CHANGE SEPARATOR
# =====================================================================
