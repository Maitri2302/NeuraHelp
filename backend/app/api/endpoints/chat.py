from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest, ChatResponse
from app.api.dependencies import get_current_user, get_rag_search

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    answer = get_rag_search().search_and_summarize(
        request.query, 
        session_id=request.session_id, 
        top_k=3,
        filename_filter=request.filename_filter,
        user_id=str(current_user["id"]),
        username=current_user["username"]
    )
    return ChatResponse(answer=answer)

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    generator = get_rag_search().asearch_stream(
        request.query, 
        session_id=request.session_id, 
        top_k=3,
        filename_filter=request.filename_filter,
        user_id=str(current_user["id"]),
        username=current_user["username"]
    )
    return StreamingResponse(generator, media_type="text/event-stream")

@router.get("/chat/sessions")
async def get_chat_sessions(current_user: dict = Depends(get_current_user)):
    sessions = get_rag_search().get_sessions(user_id=str(current_user["id"]))
    return {"sessions": sessions}

@router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str, current_user: dict = Depends(get_current_user)):
    history = get_rag_search().get_history(user_id=str(current_user["id"]), session_id=session_id)
    return {"history": history}

@router.delete("/chat/history/{session_id}")
async def delete_chat_history(session_id: str, current_user: dict = Depends(get_current_user)):
    success = get_rag_search().delete_session(user_id=str(current_user["id"]), session_id=session_id)
    if success:
        return {"status": "success", "message": "Session deleted"}
    return {"status": "error", "message": "Failed to delete session"}
