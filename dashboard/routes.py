import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_metadata_db
from app.auth.services import get_current_user
from app.auth.models import User
from app.chatbot.schemas import GRMetadataSchema

from app.dashboard.schemas import (
    DocumentFilterParams,
    PaginatedDocumentsResponse,
    FilterOptionsResponse
)
from app.dashboard.services import DashboardService, FILTERABLE_COLUMNS
import traceback


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/filters", response_model=FilterOptionsResponse)
async def get_dashboard_filters(
    meta_db: AsyncSession = Depends(get_metadata_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns available list of filter fields and their distinct values from DB.
    """
    try:
        options = await DashboardService.get_filter_options(meta_db)
        return FilterOptionsResponse(
            filter_fields=FILTERABLE_COLUMNS,
            options=options
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch filter options: {str(e)}"
        )


@router.post("/documents", response_model=PaginatedDocumentsResponse)
async def get_dashboard_documents(
    params: DocumentFilterParams,
    meta_db: AsyncSession = Depends(get_metadata_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches paginated GR document records from metadata.db 
    with dynamic filter capabilities.
    """
    try:
        documents, total_count = await DashboardService.get_paginated_documents(
            db=meta_db,
            page=params.page,
            page_size=params.page_size,
            filters=params.filters,
            search_query=params.search_query,
            sync_with_disk=False  
        )

        total_pages = math.ceil(total_count / params.page_size) if total_count > 0 else 0

        # --- THE FIX: Sanitize the data ---
        # Convert SQLAlchemy objects to dicts and replace empty strings with None
        safe_docs = []
        for doc in documents:
            doc_dict = {}
            # Loop through all columns in the database model
            for column in doc.__table__.columns:
                val = getattr(doc, column.name)
                # If the value is an empty string, force it to None to prevent Pydantic parsing crashes
                if val == "":
                    val = None
                doc_dict[column.name] = val
            safe_docs.append(doc_dict)
        # ----------------------------------

        return {
            "total_count": total_count,
            "page": params.page,
            "page_size": params.page_size,
            "total_pages": total_pages,
            "documents": safe_docs # Pass the sanitized dictionaries here
        }

    except Exception as e:
        print("[ERROR] Dashboard Documents Failure:")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching dashboard documents: {str(e)}"
        )