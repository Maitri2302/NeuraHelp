import uuid
import numpy as np
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from app.core.config import settings

class QdrantSemanticCache:
    """
    A semantic cache using Qdrant to store and retrieve queries and their answers.
    This avoids heavy hits to the LLM when users ask similar questions.
    """
    def __init__(self, collection_name: str = "semantic_cache", embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2", threshold: float = 0.90):
        qdrant_url = settings.QDRANT_URL or "http://localhost:6333"
        qdrant_api_key = settings.QDRANT_API_KEY
        self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.model = TextEmbedding(model_name=embedding_model)
        self.threshold = threshold
        
        # Get dimensions
        dummy_emb = list(self.model.embed(["dummy"]))[0]
        self.dim = len(dummy_emb)
        
        # Ensure collection exists
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(size=self.dim, distance=qmodels.Distance.COSINE),
            )
            
            # Create payload index for user isolation
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="user_id",
                field_schema=qmodels.PayloadSchemaType.KEYWORD
            )
            print(f"[INFO] Created Qdrant collection '{collection_name}' for Semantic Cache.")

    def check(self, query: str, user_id: str) -> str:
        """Check if a semantically similar query exists in the cache."""
        try:
            query_emb = list(self.model.embed([query]))[0]
            
            must_conditions = [
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchValue(value=user_id)
                )
            ]
            query_filter = qmodels.Filter(must=must_conditions)
            
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_emb.tolist(),
                query_filter=query_filter,
                limit=1
            ).points
            
            if results and results[0].score >= self.threshold:
                print(f"[INFO] Cache HIT for query: '{query}' (score: {results[0].score:.4f})")
                return results[0].payload.get("answer")
                
            print(f"[INFO] Cache MISS for query: '{query}'")
            return None
        except Exception as e:
            print(f"[ERROR] Cache check failed: {e}")
            return None
            
    def store(self, query: str, answer: str, user_id: str):
        """Store the query and answer in the cache."""
        try:
            query_emb = list(self.model.embed([query]))[0]
            
            point = qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector=query_emb.tolist(),
                payload={
                    "query": query,
                    "answer": answer,
                    "user_id": user_id
                }
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            print(f"[INFO] Stored query in Semantic Cache.")
        except Exception as e:
            print(f"[ERROR] Cache store failed: {e}")

# Global instance
semantic_cache = QdrantSemanticCache()
