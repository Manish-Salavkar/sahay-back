from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    query: str
    session_id: Optional[int] = None
    language: Literal["en", "mr"] = "en"
    top_docs_k: int = 5
    top_chunks_k: int = 50
    final_rerank_k: int = 3


class ChunkCitation(BaseModel):
    chunk_id: str
    pdf_name: str
    section: Optional[str] = "General"
    page_number: Optional[int] = 1
    text: str
    relevance_score: float


class GRMetadataSchema(BaseModel):
    pdf_name: str
    gr_number: Optional[str] = None
    date: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    department_type: Optional[str] = None
    issuing_authority: Optional[str] = None
    issuing_office: Optional[str] = None
    document_type: Optional[str] = None
    document_series: Optional[str] = None
    business_type: Optional[str] = None
    revision_type: Optional[str] = None
    language: Optional[str] = None
    # number_of_pages: Optional[int] = None
    number_of_pages: Any = None
    summary: Optional[str] = None
    topics: Optional[str] = None
    keywords: Optional[str] = None
    referenced_gr_numbers: Optional[str] = None
    legal_references: Optional[str] = None
    related_acts_or_schemes: Optional[str] = None
    scheme_names: Optional[str] = None
    mentioned_departments: Optional[str] = None
    mentioned_organizations: Optional[str] = None
    mentioned_locations: Optional[str] = None
    target_entities: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    academic_year: Optional[str] = None
    financial_year: Optional[str] = None
    amendment_or_supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    administrative_level: Optional[str] = None
    geographic_scope: Optional[str] = None
    financial_implication: Optional[str] = None
    action_verbs: Optional[str] = None
    status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    session_id: int
    query: str
    rewritten_query: str
    answer: str
    citations: List[ChunkCitation]
    metadata_records: List[GRMetadataSchema]
    confidence_score: float