from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.chatbot.schemas import GRMetadataSchema

class DocumentFilterParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=10, ge=1, le=100, description="Items per page")
    search_query: Optional[str] = Field(default=None, description="Search in title or pdf_name")
    
    # Custom dynamic filters (pass exact filter column values)
    filters: Optional[Dict[str, Any]] = Field(
        default={}, 
        description="Dictionary of column-value filters, e.g., {'department': 'School Education', 'status': 'Active'}"
    )

class PaginatedDocumentsResponse(BaseModel):
    total_count: int
    page: int
    page_size: int
    total_pages: int
    documents: List[GRMetadataSchema]

class FilterOptionsResponse(BaseModel):
    filter_fields: List[str]
    options: Dict[str, List[str]]