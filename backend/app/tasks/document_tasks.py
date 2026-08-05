import os
import uuid
from app.core.celery_app import celery_app
from app.core.data_loader import load_single_document
from app.db.database import get_db_connection
from app.core.search import RAGSearch
from langchain_community.document_loaders import WebBaseLoader
from langchain_groq import ChatGroq
from app.core.config import settings

def generate_summary(documents) -> str:
    if not documents:
        return ""
    try:
        text = "\n\n".join([doc.page_content for doc in documents])
        llm = ChatGroq(groq_api_key=settings.GROQ_API_KEY, model_name="llama-3.3-70b-versatile")
        prompt = f"Please provide a short, concise 2-3 sentence summary of the following document:\n\n{text[:15000]}"
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        print(f"[ERROR] Summarization failed: {e}")
        return ""

def process_document_task(temp_file_path: str, filename: str, user_id: str, file_size: int):
    try:
        print(f"[CELERY] Starting to process document: {filename} for user: {user_id}")
        
        # Load and parse the document
        documents = load_single_document(temp_file_path, filename)
        
        summary = ""
        if documents:
            # We initialize a new RAGSearch instance so it handles its own Qdrant connection pool in this worker
            rag = RAGSearch()
            rag.vectorstore.add_documents(documents, filename, user_id)
            summary = generate_summary(documents)
            
        # Update PostgreSQL
        conn = get_db_connection()
        cursor = conn.cursor()
        doc_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO documents (id, user_id, filename, file_path, size, summary) 
            VALUES (%s, %s, %s, %s, %s, %s) 
            ON CONFLICT (user_id, filename) DO UPDATE SET size = EXCLUDED.size, summary = EXCLUDED.summary, uploaded_at = CURRENT_TIMESTAMP
            """,
            (doc_id, user_id, filename, "diskless", file_size, summary)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"[CELERY] Successfully processed and indexed: {filename}")
        
    except Exception as e:
        print(f"[CELERY ERROR] Upload processing failed for {filename}: {e}")
        
    finally:
        # Cleanup the temporary file regardless of success or failure
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
    return {"message": "success", "filename": filename}

def process_url_task(url: str, user_id: str):
    try:
        print(f"[CELERY] Starting to process URL: {url} for user: {user_id}")
        
        # Load and parse the URL
        loader = WebBaseLoader(url)
        documents = loader.load()
        
        summary = ""
        if documents:
            # Add source metadata just in case
            for doc in documents:
                doc.metadata["source"] = url
                
            rag = RAGSearch()
            rag.vectorstore.add_documents(documents, url, user_id)
            summary = generate_summary(documents)
            
        # Update PostgreSQL
        conn = get_db_connection()
        cursor = conn.cursor()
        doc_id = str(uuid.uuid4())
        # Estimate size as length of content
        file_size = sum(len(doc.page_content) for doc in documents) if documents else 0
        
        cursor.execute(
            """
            INSERT INTO documents (id, user_id, filename, file_path, size, summary) 
            VALUES (%s, %s, %s, %s, %s, %s) 
            ON CONFLICT (user_id, filename) DO UPDATE SET size = EXCLUDED.size, summary = EXCLUDED.summary, uploaded_at = CURRENT_TIMESTAMP
            """,
            (doc_id, user_id, url, "url", file_size, summary)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"[CELERY] Successfully processed and indexed URL: {url}")
        
    except Exception as e:
        print(f"[CELERY ERROR] URL processing failed for {url}: {e}")
        
    return {"message": "success", "filename": url}
