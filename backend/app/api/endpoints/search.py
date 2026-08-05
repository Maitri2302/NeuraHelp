import uuid
from fastapi import APIRouter, Depends
from psycopg2.extras import RealDictCursor

from app.models.schemas import SearchRequest
from app.api.dependencies import get_current_user, get_rag_search
from app.db.database import get_db_connection

router = APIRouter()

@router.post("/search")
async def unified_search(request: SearchRequest, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    vector_results = get_rag_search().vectorstore.query(
        request.query, 
        top_k=request.top_k, 
        filter_source=request.filename_filter,
        user_id=user_id
    )
    
    if not vector_results:
        return {"results": []}
        
    filenames = list(set([res["metadata"].get("source") for res in vector_results if res.get("metadata") and res["metadata"].get("source")]))
    
    db_metadata = {}
    if filenames:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = "SELECT filename, size, uploaded_at FROM documents WHERE user_id = %s AND filename IN %s"
            cursor.execute(query, (user_id, tuple(filenames),))
            records = cursor.fetchall()
            for r in records:
                db_metadata[r["filename"]] = {
                    "size": r["size"],
                    "uploaded_at": str(r["uploaded_at"])
                }
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[ERROR] DB Select failed during search: {e}")

    final_results = []
    for res in vector_results:
        source = res["metadata"].get("source", "")
        item = {
            "id": res["id"],
            "score": res["score"],
            "text": res["metadata"].get("text", ""),
            "filename": source
        }
        if source in db_metadata:
            item.update(db_metadata[source])
        final_results.append(item)
        
    texts = [res["text"] for res in final_results if res.get("text")]
    context = "\n\n".join(texts)
    
    from app.core.cache import semantic_cache
    cached_answer = semantic_cache.check(request.query, user_id)
    if cached_answer:
        answer = cached_answer
    else:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            
            system_prompt = f"You are an AI assistant. The user's name is {current_user['username']}. Answer the user's question using only the provided context. If the context does not contain the answer, say you don't know.\n\nContext:\n{context}"
            messages_for_llm = [SystemMessage(content=system_prompt), HumanMessage(content=request.query)]
            
            response = await get_rag_search().llm.ainvoke(messages_for_llm)
            answer = response.content
            
            if final_results:
                semantic_cache.store(request.query, answer, user_id)
        except Exception as e:
            import traceback
            print(f"[ERROR] LLM synthesis failed in search: {e}")
            traceback.print_exc()
            answer = "Sorry, I could not synthesize an answer from the documents at this time."
            
    return {"results": final_results, "answer": answer}
