from sqlalchemy import Column, String, Integer, Text
from app.database import MetadataBase


class GRMetadata(MetadataBase):
    """
    SQLAlchemy model for gr_metadata table in metadata.db.
    Maps all 36 extracted metadata fields.
    """
    __tablename__ = "gr_metadata"

    pdf_name = Column(String, primary_key=True, index=True)
    gr_number = Column(String, nullable=True, index=True)
    date = Column(String, nullable=True)
    title = Column(Text, nullable=True)
    department = Column(String, nullable=True, index=True)
    department_type = Column(String, nullable=True)
    issuing_authority = Column(String, nullable=True)
    issuing_office = Column(String, nullable=True)
    document_type = Column(String, nullable=True)
    document_series = Column(String, nullable=True)
    business_type = Column(String, nullable=True)
    revision_type = Column(String, nullable=True)
    language = Column(String, nullable=True)
    number_of_pages = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    topics = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)
    referenced_gr_numbers = Column(Text, nullable=True)
    legal_references = Column(Text, nullable=True)
    related_acts_or_schemes = Column(Text, nullable=True)
    scheme_names = Column(Text, nullable=True)
    mentioned_departments = Column(Text, nullable=True)
    mentioned_organizations = Column(Text, nullable=True)
    mentioned_locations = Column(Text, nullable=True)
    target_entities = Column(Text, nullable=True)
    effective_date = Column(String, nullable=True)
    expiry_date = Column(String, nullable=True)
    academic_year = Column(String, nullable=True)
    financial_year = Column(String, nullable=True)
    amendment_or_supersedes = Column(Text, nullable=True)
    superseded_by = Column(Text, nullable=True)
    administrative_level = Column(String, nullable=True)
    geographic_scope = Column(String, nullable=True)
    financial_implication = Column(String, nullable=True)
    action_verbs = Column(String, nullable=True)
    status = Column(String, nullable=True)