# backend\app\chatbot\routes.py
import asyncio
import json
import math
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import os
import re

from app.database import get_metadata_db, get_db
from app.auth.services import get_current_user  
from app.auth.models import User, ChatSession, ChatMessage
from app.chatbot.models import GRMetadata
from app.chatbot.schemas import ChatRequest, ChatResponse, GRMetadataSchema, ChunkCitation
from app.chatbot.services import RAGService, embedding_model
from app.auth.schemas import FeedbackCreate
from app.auth.models import MessageFeedback

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])

BASE_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def save_chat_messages(
    auth_db: AsyncSession,
    session_id: int,
    user_query: str,
    answer: str,
    citations,
    metadata_records,
):
    metadata_lookup = {
        m.pdf_name: m
        for m in metadata_records
    }

    citations_for_db = json.dumps(
        [
            {
                "chunk_id": c["chunk_id"],
                "pdf_name": c["pdf_name"],

                "title": (
                    metadata_lookup[c["pdf_name"]].title
                    if c["pdf_name"] in metadata_lookup
                    else None
                ),

                "department": (
                    metadata_lookup[c["pdf_name"]].department
                    if c["pdf_name"] in metadata_lookup
                    else None
                ),

                "section": c.get("section", "General"),

                "page_number": c.get("page_number", 1),

                "text": c["text"],

                "relevance_score": c.get("score", 0.0),
            }
            for c in citations
        ],
        ensure_ascii=False,
    )

    auth_db.add_all(
        [
            ChatMessage(
                session_id=session_id,
                role="user",
                content=user_query,
            ),
            ChatMessage(
                session_id=session_id,
                role="assistant",
                content=answer,
                citations_json=citations_for_db,
            ),
        ]
    )

    await auth_db.commit()



@router.post("/query", response_model=ChatResponse)
async def process_chat_query(
    request: ChatRequest,
    meta_db: AsyncSession = Depends(get_metadata_db),
    auth_db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        chat_history_dicts = []
        
        if request.session_id:
            stmt = select(ChatSession).where(
                ChatSession.id == request.session_id, 
                ChatSession.user_id == current_user.id
            )
            result = await auth_db.execute(stmt)
            session = result.scalars().first()
            
            if not session:
                raise HTTPException(status_code=404, detail="Chat session not found")
                
            msg_stmt = select(ChatMessage).where(
                ChatMessage.session_id == session.id
            ).order_by(ChatMessage.created_at.asc())
            msg_result = await auth_db.execute(msg_stmt)
            previous_messages = msg_result.scalars().all()
            
            chat_history_dicts = [{"role": msg.role, "content": msg.content} for msg in previous_messages]
            
        else:
            session = ChatSession(
                user_id=current_user.id,
                title=request.query[:50] + "..." if len(request.query) > 50 else request.query
            )
            auth_db.add(session)
            await auth_db.commit()
            await auth_db.refresh(session)

        history_context = await RAGService.manage_chat_history(
            chat_history=chat_history_dicts,
            max_chars=3000
        )
        # ---------------------------------------------------------------------
        # RAG PIPELINE EXECUTION WITH DEBUGGING LOGS
        # ---------------------------------------------------------------------
        history_aware_query = await RAGService.rewrite_query_with_history(
            query=request.query,
            history_context=history_context
        )
        print("========== HISTORY ==========")
        print(history_context)
        print("=============================")
        print("\n========== HISTORY AWARE QUERY ==========")
        print(history_aware_query)
        print("=========================================\n")

        parsed_query = await RAGService.parse_and_rewrite_query(
            history_aware_query
        )

        
        print("\n========== PARSED QUERY ==========")
        print(parsed_query)
        print("==================================\n")
        semantic_query = parsed_query.get("semantic_query", request.query)

        query_embedding = (
            await asyncio.to_thread(
                embedding_model.encode, 
                [semantic_query], 
                normalize_embeddings=True
            )
        )[0].tolist()

        # STAGE 3: Document Funnel
        pdf_names = await RAGService.document_funnel_search(
            query_embedding=query_embedding,
            parsed=parsed_query,
            top_k=5
        )
        print(f"-> Documents: {pdf_names}")

        # STAGE 4: Targeted Chunks
        raw_chunks = await RAGService.targeted_chunk_search(
            query_embedding=query_embedding,
            pdf_names=pdf_names,
            fetch_k=request.top_chunks_k
        )
        print(f"-> Raw chunks: {len(raw_chunks)}")

        # STAGE 5: MMR
        diverse_chunks = RAGService.apply_mmr(
            query_embedding=query_embedding,
            chunks=raw_chunks,
            top_k=10,
            lambda_param=0.7 
        )
        print(f"-> MMR chunks: {len(diverse_chunks)}")

        # STAGE 6: Rerank
        reranked_chunks = await RAGService.rerank_and_filter(
            query=semantic_query,
            chunks=diverse_chunks,
            top_k=request.final_rerank_k
        )
        print(f"-> Reranked chunks: {len(reranked_chunks)}")
        
        confidence_score = 0.0
        if reranked_chunks:
            top_logit = reranked_chunks[0].get("score", 0.0)
            confidence_score = round((1 / (1 + math.exp(-top_logit))) * 100, 2)

        # STAGE 7: Neighbor Expansion
        final_chunks = await RAGService.fetch_neighboring_chunks(reranked_chunks)
        print(f"-> Final chunks: {len(final_chunks)}")

        referenced_pdfs = list(set([c["pdf_name"] for c in final_chunks]))
        metadata_records = []
        if referenced_pdfs:
            stmt = select(GRMetadata).where(GRMetadata.pdf_name.in_(referenced_pdfs))
            db_result = await meta_db.execute(stmt)
            metadata_records = [GRMetadataSchema.model_validate(record) for record in db_result.scalars().all()]

        history_context = await RAGService.manage_chat_history(
            chat_history=chat_history_dicts, 
            max_chars=3000
        )

        answer = await RAGService.synthesize_llm_response(
            query=request.query,
            citations=final_chunks,
            metadata_records=metadata_records,
            history_context=history_context,
            language=request.language
        )
        print(f"-> Final LLM Answer generated successfully.")

        # ---------------------------------------------------------------------
        # SAVE MESSAGES & RETURN
        # ---------------------------------------------------------------------
        # citations_for_db = json.dumps([
        #     {"chunk_id": c["chunk_id"], "pdf_name": c["pdf_name"], "page": c.get("page_number", 1)} 
        #     for c in final_chunks
        # ])

        # user_message = ChatMessage(session_id=session.id, role="user", content=request.query)
        # ai_message = ChatMessage(session_id=session.id, role="assistant", content=answer, citations_json=citations_for_db)
        
        # auth_db.add_all([user_message, ai_message])
        # await auth_db.commit()
        await save_chat_messages(
            auth_db=auth_db,
            session_id=session.id,
            user_query=request.query,
            answer=answer,
            citations=final_chunks,
            metadata_records=metadata_records,
        )

        formatted_citations = [
            ChunkCitation(
                chunk_id=c["chunk_id"],
                pdf_name=c["pdf_name"],
                page_number=c.get("page_number", 1),
                text=c["text"],
                relevance_score=c.get("score", 0.0)
            ) for c in final_chunks
        ]

        return ChatResponse(
            session_id=session.id,
            query=request.query,
            rewritten_query=semantic_query, 
            answer=answer,
            citations=formatted_citations,
            metadata_records=metadata_records,
            confidence_score=confidence_score
        )

    except Exception as e:
        print(f"[ERROR] RAG Pipeline Exception: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the request: {str(e)}"
        )


@router.get("/documents/{pdf_name}")
async def get_pdf_document(pdf_name: str):
    # Security check: Prevent directory traversal attacks
    if not re.match(r"^[a-zA-Z0-9_.-]+\.pdf$", pdf_name):
        raise HTTPException(status_code=400, detail="Invalid file name format.")

    # Construct path: backend/gr_files/filename.pdf
    file_path = os.path.join(BASE_BACKEND_DIR, "gr_files", pdf_name)

    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document not found.")

    # Return with pure inline disposition (do not pass filename=... here)
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline"
        }
    )

@router.get("/document/{pdf_name}/relations")
async def get_document_relations(
    pdf_name: str,
    meta_db: AsyncSession = Depends(get_metadata_db),
):
    return await RAGService.get_document_relations(
        pdf_name=pdf_name,
        meta_db=meta_db,
    )

# Add this below your existing routes in backend/app/chatbot/routes.py

@router.get("/sessions")
async def get_chat_sessions(
    auth_db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetches all chat sessions for the logged-in user to display in the sidebar."""
    stmt = select(ChatSession).where(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.created_at.desc())
    
    result = await auth_db.execute(stmt)
    sessions = result.scalars().all()
    
    return [
        {
            "id": s.id, 
            "title": s.title, 
            "created_at": s.created_at.isoformat()
        } for s in sessions
    ]

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: int,
    auth_db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetches all messages and citations for a specific chat session."""
    # 1. Verify the session belongs to the user
    stmt = select(ChatSession).where(
        ChatSession.id == session_id, 
        ChatSession.user_id == current_user.id
    )
    result = await auth_db.execute(stmt)
    session = result.scalars().first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")

    # 2. Fetch the messages
    msg_stmt = select(ChatMessage).where(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc())
    
    msg_result = await auth_db.execute(msg_stmt)
    messages = msg_result.scalars().all()

    formatted_messages = []
    for m in messages:
        citations = []
        if m.citations_json:
            try:
                citations = json.loads(m.citations_json)
            except json.JSONDecodeError:
                citations = []

        formatted_messages.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "citations": citations
        })

    return formatted_messages


@router.post("/feedback")
async def submit_message_feedback(
    feedback_data: FeedbackCreate,
    auth_db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Saves user feedback for a chatbot message or session to the database."""
    new_feedback = MessageFeedback(
        user_id=current_user.id,
        message_id=feedback_data.message_id,
        session_id=feedback_data.session_id,
        answered=feedback_data.answered,
        accuracy=feedback_data.accuracy,
        citations_relevant=feedback_data.citations_relevant,
        comments=feedback_data.comments
    )
    
    auth_db.add(new_feedback)
    await auth_db.commit()
    await auth_db.refresh(new_feedback)
    
    return {"status": "success", "message": "Feedback recorded successfully", "feedback_id": new_feedback.id}