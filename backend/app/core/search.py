import os
from typing import Annotated
from typing_extensions import TypedDict
from dotenv import load_dotenv

from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from .vectorstore import QdrantVectorStore

load_dotenv()

class State(TypedDict):
    messages: Annotated[list, add_messages]
    context: str
    username: str

class RAGSearch:
    def __init__(self, collection_name: str = "documents", embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2", llm_model: str = "llama-3.3-70b-versatile"):
        self.vectorstore = QdrantVectorStore(collection_name, embedding_model)
        
        # We rely on the unified search ingestion API to add documents incrementally
        # No initial directory loading is performed.
            
        from app.core.config import settings
        groq_api_key = settings.GROQ_API_KEY
        if not groq_api_key or groq_api_key.strip() == "" or groq_api_key == "your_groq_api_key_here":
            raise ValueError(
                "\n[ERROR] GROQ_API_KEY is not configured. Please set your actual Groq API key in the '.env' file in the project root."
            )
        self.llm = ChatGroq(groq_api_key=groq_api_key, model_name=llm_model)
        
        self.db_url = settings.DATABASE_URL or "postgresql://python_rag_user:rag_password@127.0.0.1:5435/rag_memory"
        
        # PostgresSaver needs a connection pool (synchronous for PostgresSaver)
        self.pool = ConnectionPool(
            conninfo=self.db_url,
            max_size=20,
            kwargs={"autocommit": True, "prepare_threshold": None}
        )
        
        # Setup Checkpointer
        self.checkpointer = PostgresSaver(self.pool)
        self.checkpointer.setup()

        # Build Graph
        workflow = StateGraph(State)
        
        async def call_model(state: State):
            context = state.get("context", "")
            username = state.get("username", "User")
            system_prompt = f"You are a helpful AI assistant. You are speaking with {username}. Use the following context to answer their question:\n\n{context}\n\nIf the answer isn't in the context, just say you don't know. IMPORTANT: You MUST cite your sources in your answer using the filename provided in the context, e.g., 'according to [filename.pdf]...' or simply appending [filename.pdf] to the end of sentences."
            
            # Combine system prompt with existing messages
            messages_for_llm = [{"role": "system", "content": system_prompt}] + state["messages"]
            response = await self.llm.ainvoke(messages_for_llm)
            return {"messages": [response]}
            
        workflow.add_node("agent", call_model)
        workflow.add_edge(START, "agent")
        workflow.add_edge("agent", END)
        
        self.workflow = workflow
        self.graph = workflow.compile(checkpointer=self.checkpointer)
        print(f"[INFO] Groq LLM initialized with LangGraph Postgres Checkpointer: {llm_model}")

    def search_and_summarize(self, query: str, user_id: str, username: str, session_id: str = "default", top_k: int = 5, filename_filter: str = None) -> str:
        from app.core.cache import semantic_cache
        
        # 1. Check Semantic Cache
        cached_answer = semantic_cache.check(query, user_id)
        if cached_answer:
            return cached_answer
            
        try:
            results = self.vectorstore.query(query, user_id=user_id, top_k=top_k, filter_source=filename_filter)
            texts = [f"Source: {r['metadata'].get('source', 'Unknown')}\n{r['metadata'].get('text', '')}" for r in results if r["metadata"]]
            context = "\n\n---\n\n".join(texts)
        except Exception as e:
            print(f"[ERROR] Vectorstore search failed: {e}")
            context = ""
            
        if not context:
            context = "No relevant documents found."
            
        try:
            config = {"configurable": {"thread_id": f"{user_id}_{session_id}"}}
            input_message = HumanMessage(content=query)
            
            # Run the LangGraph
            state = self.graph.invoke({"messages": [input_message], "context": context, "username": username}, config)
            
            # The last message in the state is the AI's response
            answer = state["messages"][-1].content
            
            # 2. Store in Semantic Cache
            if "No relevant documents found" not in context:
                semantic_cache.store(query, answer, user_id)
                
            return answer
        except Exception as e:
            print(f"[ERROR] LangGraph failed: {e}")
            return "Sorry, I encountered an error processing your request."

    async def asearch_stream(self, query: str, user_id: str, username: str, session_id: str = "default", top_k: int = 5, filename_filter: str = None):
        import json
            
        try:
            results = self.vectorstore.query(query, user_id=user_id, top_k=top_k, filter_source=filename_filter)
            texts = [f"Source: {r['metadata'].get('source', 'Unknown')}\n{r['metadata'].get('text', '')}" for r in results if r["metadata"]]
            context = "\n\n---\n\n".join(texts)
        except Exception as e:
            print(f"[ERROR] Vectorstore search failed: {e}")
            context = ""
            
        if not context:
            context = "No relevant documents found."
            
        try:
            config = {"configurable": {"thread_id": f"{user_id}_{session_id}"}}
            input_message = HumanMessage(content=query)
            
            # Lazily initialize async checkpointer and graph
            if getattr(self, "async_graph", None) is None:
                from psycopg_pool import AsyncConnectionPool
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                self.async_pool = AsyncConnectionPool(
                    conninfo=self.db_url,
                    max_size=20,
                    kwargs={"autocommit": True, "prepare_threshold": None}
                )
                self.async_checkpointer = AsyncPostgresSaver(self.async_pool)
                await self.async_checkpointer.setup()
                self.async_graph = self.workflow.compile(checkpointer=self.async_checkpointer)
            
            full_answer = ""
            async for event in self.async_graph.astream_events({"messages": [input_message], "context": context, "username": username}, config, version="v2"):
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        full_answer += content
                        yield f"data: {json.dumps({'content': content})}\n\n"
            
            yield "data: [DONE]\n\n"
                
        except Exception as e:
            import traceback
            print(f"[ERROR] LangGraph streaming failed: {repr(e)}")
            traceback.print_exc()
            yield f"data: {json.dumps({'error': 'Sorry, I encountered an error processing your request.'})}\n\n"
            yield "data: [DONE]\n\n"

    def get_sessions(self, user_id: str):
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE %s", (f"{user_id}_%",))
                    rows = cursor.fetchall()
                    
                    sessions = []
                    for row in rows:
                        thread_id = row[0]
                        session_id = thread_id.replace(f"{user_id}_", "", 1)
                        title = "New Chat"
                        
                        try:
                            config = {"configurable": {"thread_id": thread_id}}
                            state = self.graph.get_state(config)
                            if state and state.values and "messages" in state.values:
                                messages = state.values["messages"]
                                for msg in messages:
                                    if getattr(msg, "type", "") == "human":
                                        content = getattr(msg, "content", "")
                                        if content:
                                            title = content[:25].strip() + ("..." if len(content) > 25 else "")
                                        break
                        except Exception as e:
                            print(f"[ERROR] Failed to get state for {thread_id}: {e}")
                            
                        sessions.append({"id": session_id, "title": title})
                    return sessions
        except Exception as e:
            print(f"[ERROR] Failed to fetch sessions: {e}")
            return []

    def get_history(self, user_id: str, session_id: str):
        config = {"configurable": {"thread_id": f"{user_id}_{session_id}"}}
        try:
            state = self.graph.get_state(config)
            if not state or not state.values:
                return []
            
            messages = state.values.get("messages", [])
            history = []
            for msg in messages:
                role = "user" if getattr(msg, "type", "") == "human" else "ai"
                # Exclude system messages or others if necessary, but LangGraph mostly tracks human/ai in chat
                if getattr(msg, "type", "") in ["human", "ai"]:
                    history.append({"role": role, "content": msg.content})
            return history
        except Exception as e:
            print(f"[ERROR] Failed to get history: {e}")
            return []

    def delete_session(self, user_id: str, session_id: str):
        try:
            thread_id = f"{user_id}_{session_id}"
            with self.pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM checkpoints WHERE thread_id = %s", (thread_id,))
                    cursor.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (thread_id,))
                    cursor.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (thread_id,))
                conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to delete session: {e}")
            return False
