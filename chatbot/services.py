# backend\app\chatbot\services.py
import os
import json
import asyncio
import re
import numpy as np
from typing import List, Dict, Any, Optional
import requests
import chromadb
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer, CrossEncoder

from app.chatbot.schemas import GRMetadataSchema
from app.config import GOOGLE_API_KEY
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chatbot.models import GRMetadata
# ----------------------------
# CONFIG & MODELS
# ----------------------------
# LLM_MODEL = "gemini-3.5-flash-lite"
# LLM_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL}:generateContent"

# LLM_MODEL = "gemma-4-26B-A4B-it-QAT-Q4_0"
# LLM_URL = "http://100.117.161.96:8080/v1/chat/completions"

LLM_MODEL = "gemma4:26b"
LLM_URL = "https://ollama.manishsalavkar.me/api/chat"

print("[STARTUP] Loading Embedding & Reranker models...")
embedding_model = SentenceTransformer("BAAI/bge-m3")
reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

BASE_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.environ.get(
    "VECTOR_DB_PATH",
    os.path.join(BASE_BACKEND_DIR, "maharashtra_gr_db_v2_backup", "chroma_db")
)

client = chromadb.PersistentClient(path=DB_PATH)

try:
    doc_collection = client.get_collection(name="gr_documents")
    chunk_collection = client.get_collection(name="gr_chunks")
except Exception as e:
    raise RuntimeError(
        "Required ChromaDB collections ('gr_documents' and/or 'gr_chunks') "
        "do not exist. Please build or restore the vector database first."
    ) from e

STATIC_SYNONYMS = {
    "scholarship": "scholarship शिष्यवृत्ती",
    "reservation": "reservation आरक्षण",
    "fee reimbursement": "fee reimbursement शुल्क परतावा",
    "transfer": "transfer बदली",
    "promotion": "promotion पदोन्नती"
}

class RAGService:

    #gemini
    # @staticmethod
    # def _sync_call_llm(system_prompt: str, user_prompt: str, temperature: float = 0):
    #     payload = {
    #         "contents": [{"parts": [{"text": f"System:\n{system_prompt}\n\nUser:\n{user_prompt}"}]}],
    #         "generationConfig": {"temperature": temperature}
    #     }
    #     headers = {"Content-Type": "application/json", "x-goog-api-key": GOOGLE_API_KEY}
    #     response = requests.post(LLM_URL, headers=headers, json=payload, timeout=120)
    #     response.raise_for_status()
    #     return response.json()["candidates"][0]["content"]["parts"][0]["text"]


    #tanmay local llm
    @staticmethod
    def _sync_call_llm(
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0,
    ):
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        response = requests.post(
            LLM_URL,
            json=payload,
            timeout=300,
        )

        response.raise_for_status()

        data = response.json()

        return data["message"]["content"]

    @staticmethod
    async def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0):
        return await asyncio.to_thread(RAGService._sync_call_llm, system_prompt, user_prompt, temperature)

    @staticmethod
    async def manage_chat_history(chat_history: List[dict], max_chars: int = 3000) -> str:
        if not chat_history:
            return ""
            
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        if len(history_text) <= max_chars:
            return history_text
            
        summary_prompt = "Summarize the key context and facts of this conversation strictly in 3-4 sentences."
        summary = await RAGService.call_llm(summary_prompt, history_text)
        recent_turns = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-2:]])
        return f"[Context Summary]: {summary}\n\n[Recent Chat]:\n{recent_turns}"

    @staticmethod
    async def rewrite_query_with_history(
        query: str,
        history_context: str,
    ) -> str:
        """
        Rewrites follow-up questions into standalone questions
        using previous conversation context.
        """

        if not history_context.strip():
            return query

        prompt = f"""
You are a conversational query rewriting assistant.

Your task is to rewrite ONLY the latest user question into a complete,
standalone search query using the previous conversation.

Rules:

1. Preserve the exact topic being discussed.
2. Preserve the objective or purpose of the discussion.
3. Preserve all proper nouns, organization names, committee names,
   scheme names, department names, and GR numbers.
4. Do NOT generalize the topic.
5. Do NOT replace a specific topic with generic phrases like
   "information", "details", "Government Resolution",
   "available documents", or "related information".
6. If the latest message is already self-contained,
   return it unchanged.
7. Do NOT answer the question.
8. Return ONLY the rewritten query.

    Conversation History:

    {history_context}

    Latest User Question:

    {query}
    """

        rewritten = await RAGService.call_llm(
            system_prompt="Rewrite follow-up questions.",
            user_prompt=prompt,
            temperature=0
        )

        return rewritten.strip()

    @staticmethod
    async def parse_and_rewrite_query(query: str):
        query_lower = query.lower().strip()
        
        is_simple_query = len(query_lower.split()) <= 3
        if is_simple_query and query_lower in STATIC_SYNONYMS:
            return {
                "semantic_query": STATIC_SYNONYMS[query_lower],
                "department": None, "status": None, "latest": False, 
                "document_type": None, "academic_year": None
            }

        prompt = """
        You are a parser for Maharashtra Government Resolutions.
        Translate terms: (e.g., Scholarship -> शिष्यवृत्ती).
        Return ONLY valid JSON.
        Schema: {
            "semantic_query": "translated/expanded query",
            "department": "Department Name or null",
            "status": "Active or null",
            "document_type": "GR/Letter/null",
            "latest": true/false,
            "academic_year": "YYYY-YY or null",
            "financial_year": "YYYY-YY or null"
        }
        """
        response = await RAGService.call_llm(prompt, query)
        try:
            clean_json = re.sub(r'```json|```', '', response).strip()
            return json.loads(clean_json)
        except Exception:
            return {"semantic_query": query} 

    @staticmethod
    async def document_funnel_search(query_embedding: List[float], parsed: dict, top_k: int = 5) -> List[str]:
        raw_where = {
            k: v for k, v in parsed.items()
            if v and k in [
                "department",
                "status",
                # "document_type",
                "academic_year",
                "financial_year"
            ]
        }

        where_clause = None
        if len(raw_where) == 1:
            where_clause = raw_where
        elif len(raw_where) > 1:
            where_clause = {"$and": [{k: v} for k, v in raw_where.items()]}

        # ==========================
        # DEBUG PRINTS
        # ==========================
        print("\n========== DOCUMENT FUNNEL ==========")
        print("Parsed Query:")
        print(parsed)

        print("\nRaw Where:")
        print(raw_where)

        print("\nWhere Clause:")
        print(where_clause)

        print("\nEmbedding length:", len(query_embedding))
        print("=====================================\n")

        def _sync_query():
            return doc_collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                # where=where_clause if where_clause else None
            )

        results = await asyncio.to_thread(_sync_query)

        # ==========================
        # DEBUG PRINT
        # ==========================
        print("\n========== CHROMA RESULT ==========")
        print(results)
        print("===================================\n")

        return results["ids"][0] if results and results.get("ids") else []

    @staticmethod
    async def targeted_chunk_search(query_embedding: List[float], pdf_names: List[str], fetch_k: int = 50):
        if not pdf_names: return []

        def _sync_chunk_query():
            return chunk_collection.query(
                query_embeddings=[query_embedding],
                n_results=fetch_k,
                where={"pdf_name": {"$in": pdf_names}},
                include=["documents", "metadatas", "embeddings"] 
            )

        results = await asyncio.to_thread(_sync_chunk_query)
        
        chunks = []
        if results and results.get("ids"):
            for i in range(len(results["ids"][0])):
                meta = results["metadatas"][0][i]
                chunks.append({
                    "chunk_id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "embedding": results["embeddings"][0][i],
                    "pdf_name": meta.get("pdf_name", ""),
                    "page_number": meta.get("page_number", 1),
                    # FIX: Match indexing script metadata exactly
                    "chunk_index": meta.get("chunk_index", 0), 
                    "prev_chunk": meta.get("prev_chunk", "none"),
                    "next_chunk": meta.get("next_chunk", "none")
                })
        return chunks

    @staticmethod
    async def fetch_neighboring_chunks(selected_chunks: List[Dict]) -> List[Dict]:
        if not selected_chunks: return []
        
        neighbor_ids = []
        # FIX: Utilize existing metadata values for neighbors
        for c in selected_chunks:
            if c.get("prev_chunk") and c.get("prev_chunk") != "none":
                neighbor_ids.append(c["prev_chunk"])
            if c.get("next_chunk") and c.get("next_chunk") != "none":
                neighbor_ids.append(c["next_chunk"])
                
        # Deduplicate IDs
        neighbor_ids = list(set(neighbor_ids))
        
        if not neighbor_ids:
            return selected_chunks
            
        def _sync_fetch_neighbors():
            return chunk_collection.get(ids=neighbor_ids, include=["documents"])
            
        neighbors = await asyncio.to_thread(_sync_fetch_neighbors)
        neighbor_map = dict(zip(neighbors["ids"], neighbors["documents"])) if neighbors and neighbors.get("ids") else {}
        
        for c in selected_chunks:
            prev_id = c.get("prev_chunk", "none")
            next_id = c.get("next_chunk", "none")
            
            prev_text = neighbor_map.get(prev_id, "")
            next_text = neighbor_map.get(next_id, "")
            
            c["text"] = f"{prev_text}\n{c['text']}\n{next_text}".strip()
            
        return selected_chunks

    @staticmethod
    def apply_mmr(query_embedding: List[float], chunks: List[Dict], top_k: int = 10, lambda_param: float = 0.7):
        if not chunks: return []
        if len(chunks) <= top_k: return chunks

        q_emb = np.array([query_embedding])
        c_embs = np.array([c["embedding"] for c in chunks])
        
        query_sims = cosine_similarity(q_emb, c_embs)[0]
        selected_indices, unselected_indices = [], list(range(len(chunks)))
        
        first_idx = int(np.argmax(query_sims))
        selected_indices.append(first_idx)
        unselected_indices.remove(first_idx)
        
        while len(selected_indices) < top_k and unselected_indices:
            selected_embs = np.array([c_embs[i] for i in selected_indices])
            unselected_embs = np.array([c_embs[i] for i in unselected_indices])
            
            sim_to_selected = cosine_similarity(unselected_embs, selected_embs)
            max_sim_to_selected = np.max(sim_to_selected, axis=1)
            
            mmr_scores = (lambda_param * query_sims[unselected_indices]) - ((1 - lambda_param) * max_sim_to_selected)
            
            best_idx = unselected_indices[np.argmax(mmr_scores)]
            selected_indices.append(best_idx)
            unselected_indices.remove(best_idx)
            
        return [chunks[i] for i in selected_indices]

    @staticmethod
    async def rerank_and_filter(query: str, chunks: List[Dict], top_k: int = 3, max_per_pdf: int = 2):
        if not chunks: return []

        def _sync_rerank():
            pairs = [[query, c["text"]] for c in chunks]
            scores = reranker_model.predict(pairs)
            for idx, score in enumerate(scores):
                chunks[idx]["score"] = float(score)
            return sorted(chunks, key=lambda x: x["score"], reverse=True)

        ranked = await asyncio.to_thread(_sync_rerank)

        top_score = ranked[0]["score"]
        dynamic_threshold = min(0.0, top_score * 0.8) if top_score > 0 else top_score - 2.0

        final_citations = []
        pdf_counts = {}
        
        for c in ranked:
            if c["score"] < dynamic_threshold:
                continue
                
            pdf = c["pdf_name"]
            if pdf_counts.get(pdf, 0) >= max_per_pdf:
                continue
                
            pdf_counts[pdf] = pdf_counts.get(pdf, 0) + 1
            final_citations.append(c)
            
            if len(final_citations) >= top_k:
                break

        return final_citations

    @staticmethod
    async def synthesize_llm_response(query: str, citations: List[Dict], metadata_records: List[GRMetadataSchema], history_context: str, language: str,) -> str:
        metadata_str = "\n".join([f"- {m.pdf_name} | {m.title} | Dept: {m.department} | Date: {m.date}" for m in metadata_records])
        chunk_str = "\n".join([f"[Source: {c['pdf_name']}, Page: {c['page_number']}]\n{c['text']}\n" for c in citations])
        language_instruction = {
            "en": f"""
                Respond ONLY in English.

                Do not use Marathi except when quoting
                official document names,
                GR numbers,
                Acts,
                Schemes,
                or department names.

                Translate all explanations into English.
            """,
            "mr": f"""
                Respond ONLY in Marathi.

                Do not use English for explanations.

                Keep official names,
                GR numbers,
                Acts,
                department names,
                and scheme names unchanged whenever translating them would change their legal meaning. 
                """
        }.get(language, "Respond ONLY in English.")
        system_prompt = f"""You are a precise Maharashtra Government Resolution AI Assistant.

1. RELEVANT GR METADATA:
{metadata_str}

2. RETRIEVED TEXT CHUNKS (Verified):
{chunk_str}

3. CONVERSATION HISTORY:
{history_context}

INSTRUCTIONS:
- Answer ONLY using the supplied context above.
- Language Requirement: {language_instruction}  
- Do NOT hallucinate. If the answer is missing, state it clearly.
- Do NOT use phrases like "Based on the context...".
- Cite sources naturally (e.g., [PDF_Name.pdf, Page X]).
- Provide a concise executive summary by default (80-150 words).
"""
        return await RAGService.call_llm(system_prompt, query)


    @staticmethod
    async def get_document_relations(
        pdf_name: str,
        meta_db: AsyncSession,
    ):
        """
        Demo implementation.

        Later this hardcoded mapping will be replaced by
        automatic relationship detection.
        """

        DEMO_RELATIONS = {
            "202402291744117508.pdf": [
                {
                    "pdf_name": "202310311516240808.pdf",
                    "relation": "Infrastructure Development"
                },
                {
                    "pdf_name": "202310311524187608.pdf",
                    "relation": "Equipment Procurement"
                },
                {
                    "pdf_name": "202401291505054008.pdf",
                    "relation": "Fund Allocation"
                }
            ]
        }

        # No hardcoded relations
        if pdf_name not in DEMO_RELATIONS:
            return {
                "current_pdf": pdf_name,
                "related_documents": []
            }

        related_mapping = DEMO_RELATIONS[pdf_name]

        pdf_names = [x["pdf_name"] for x in related_mapping]

        stmt = (
            select(GRMetadata)
            .where(GRMetadata.pdf_name.in_(pdf_names))
        )

        result = await meta_db.execute(stmt)
        docs = result.scalars().all()

        metadata_lookup = {
            doc.pdf_name: doc
            for doc in docs
        }

        related_documents = []

        for item in related_mapping:

            doc = metadata_lookup.get(item["pdf_name"])

            if not doc:
                continue

            related_documents.append(
                {
                    "relation": item["relation"],
                    "pdf_name": doc.pdf_name,
                    "title": doc.title,
                    "department": doc.department,
                    "gr_number": doc.gr_number,
                    "date": doc.date,
                    "document_type": doc.document_type,
                    "status": doc.status,
                }
            )

        return {
            "current_pdf": pdf_name,
            "related_documents": related_documents
        }