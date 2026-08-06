import os
import math
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct, or_
from app.chatbot.models import GRMetadata
from app.chatbot.services import BASE_BACKEND_DIR

# =====================================================================
# =====================================================================
# BACKEND/APP CHANGE SEPARATOR: CONFIGURABLE FILTER LIST
# =====================================================================
FILTERABLE_COLUMNS = [
    # "department",
    "status",
    "document_type",
]
# =====================================================================
# END OF BACKEND/APP CHANGE SEPARATOR
# =====================================================================

GR_FILES_DIR = os.path.join(BASE_BACKEND_DIR, "gr_files")

class DashboardService:

    @staticmethod
    def get_physical_pdf_files() -> set:
        """Helper to return set of actual pdf filenames inside gr_files directory."""
        if not os.path.exists(GR_FILES_DIR):
            return set()
        return {
            f for f in os.listdir(GR_FILES_DIR) 
            if f.lower().endswith('.pdf')
        }

    @staticmethod
    async def get_filter_options(db: AsyncSession) -> Dict[str, List[str]]:
        """
        Dynamically fetches unique non-null values for each configured column 
        in FILTERABLE_COLUMNS from the metadata database.
        """
        filter_options = {}

        for col_name in FILTERABLE_COLUMNS:
            if hasattr(GRMetadata, col_name):
                col_attr = getattr(GRMetadata, col_name)
                stmt = (
                    select(distinct(col_attr))
                    .where(col_attr.isnot(None), col_attr != "")
                    .order_by(col_attr.asc())
                )
                result = await db.execute(stmt)
                unique_vals = [row[0] for row in result.all() if row[0]]
                filter_options[col_name] = unique_vals
            else:
                filter_options[col_name] = []

        return filter_options

    @staticmethod
    async def get_paginated_documents(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        filters: Dict[str, Any] = None,
        search_query: str = None,
        sort_order: str = "newest",
        from_year: int = None,
        to_year: int = None,
        sync_with_disk: bool = True
    ) -> Tuple[List[GRMetadata], int]:
        """
        Fetches documents from GRMetadata applying dynamic filters, keyword search, 
        year range filtering, and disk-verification against gr_files.
        """
        filters = filters or {}
        conditions = []

        # 1. Apply configured column filters dynamically
        for col_name, value in filters.items():
            if value and col_name in FILTERABLE_COLUMNS and hasattr(GRMetadata, col_name):
                col_attr = getattr(GRMetadata, col_name)
                if isinstance(value, list):
                    conditions.append(col_attr.in_(value))
                else:
                    conditions.append(col_attr == value)

        # 2. Text Search Filter (Title or PDF Name)
        if search_query:
            term = f"%{search_query.strip()}%"
            conditions.append(
                or_(
                    GRMetadata.title.ilike(term),
                    GRMetadata.pdf_name.ilike(term)
                )
            )

        # =====================================================================
        # BACKEND/APP CHANGE SEPARATOR: YEAR RANGE FILTER (2015-2026)
        # =====================================================================
        if from_year or to_year:
            year_expr = func.substr(GRMetadata.pdf_name, 1, 4)
            if from_year:
                conditions.append(year_expr >= str(from_year))
            if to_year:
                conditions.append(year_expr <= str(to_year))
        # =====================================================================
        # END OF BACKEND/APP CHANGE SEPARATOR
        # =====================================================================

        # 3. Disk Sync Filter (Only include records where physical PDF exists in gr_files)
        if sync_with_disk:
            existing_pdfs = DashboardService.get_physical_pdf_files()
            if existing_pdfs:
                conditions.append(GRMetadata.pdf_name.in_(list(existing_pdfs)))
            else:
                # No files on disk
                return [], 0

        # Build Base Queries
        count_stmt = select(func.count(GRMetadata.pdf_name)) 
        data_stmt = select(GRMetadata)

        if conditions:
            count_stmt = count_stmt.where(*conditions)
            data_stmt = data_stmt.where(*conditions)

        # Execute Total Count Query
        total_res = await db.execute(count_stmt)
        total_count = total_res.scalar() or 0

        # Execute Paginated Query
        offset = (page - 1) * page_size
        
        # =====================================================================
        # BACKEND/APP CHANGE SEPARATOR: NEWEST FIRST / OLDEST FIRST SORTING
        # =====================================================================
        if sort_order == "oldest":
            data_stmt = data_stmt.order_by(
                GRMetadata.date.asc().nulls_last(), 
                GRMetadata.pdf_name.asc()
            )
        else:
            data_stmt = data_stmt.order_by(
                GRMetadata.date.desc().nulls_last(), 
                GRMetadata.pdf_name.desc()
            )
        # =====================================================================
        # END OF BACKEND/APP CHANGE SEPARATOR
        # =====================================================================

        data_stmt = data_stmt.offset(offset).limit(page_size)
        
        result = await db.execute(data_stmt)
        documents = result.scalars().all()

        return documents, total_count