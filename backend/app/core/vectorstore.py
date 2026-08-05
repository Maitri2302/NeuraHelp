import numpy as np
import uuid
from typing import List, Any
from fastembed import TextEmbedding, SparseTextEmbedding
from qdrant_client import QdrantClient
from flashrank import Ranker, RerankRequest
from qdrant_client.http import models as qmodels
from .embedding import EmbeddingPipeline
from .data_loader import load_all_documents

class QdrantVectorStore:
    def __init__(self, collection_name: str = "documents_hybrid", embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2", chunk_size: int = 1000, chunk_overlap: int = 200):
        from app.core.config import settings
        qdrant_url = settings.QDRANT_URL or "http://localhost:6333"
        qdrant_api_key = settings.QDRANT_API_KEY
        self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.model = TextEmbedding(model_name=embedding_model)
        self.sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")
        try:
            self.ranker = Ranker(model_name="ms-marco-MiniLM-L-6-v2")
            self.use_reranker = True
        except Exception as e:
            print(f"[WARNING] FlashRank failed to initialize: {e}")
            self.use_reranker = False
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # We assume embedding model produces 384 dimensions for all-MiniLM-L6-v2
        dummy_emb = list(self.model.embed(["dummy"]))[0]
        self.dim = len(dummy_emb)
        
        # Ensure collection exists
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": qmodels.VectorParams(size=self.dim, distance=qmodels.Distance.COSINE)
                },
                sparse_vectors_config={
                    "sparse": qmodels.SparseVectorParams()
                }
            )
            
        # Ensure payload indexes exist for filtering
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="user_id",
                field_schema=qmodels.PayloadSchemaType.KEYWORD
            )
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="source",
                field_schema=qmodels.PayloadSchemaType.KEYWORD
            )
        except Exception:
            pass
        print(f"[INFO] Loaded Qdrant collection '{collection_name}' with embedding model: {embedding_model}")

    def add_documents(self, documents: List[Any], source_filename: str, user_id: str):
        if not documents:
            print(f"[WARNING] No documents to add for {source_filename}.")
            return
            
        print(f"[INFO] Adding {len(documents)} document pages/chunks for {source_filename} to vector store for user {user_id}...")
        
        emb_pipe = EmbeddingPipeline(model_name=self.embedding_model, chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
        chunks = emb_pipe.chunk_documents(documents)
        if not chunks:
            print(f"[WARNING] No chunks created for {source_filename}.")
            return
            
        embeddings = emb_pipe.embed_chunks(chunks)
        metadatas = [{"text": chunk.page_content, "source": source_filename, "user_id": user_id} for chunk in chunks]
        texts = [chunk.page_content for chunk in chunks]
        
        # Generate sparse embeddings
        sparse_embeddings = list(self.sparse_model.embed(texts))
        
        points = []
        for i, (emb, sparse_emb, meta) in enumerate(zip(embeddings, sparse_embeddings, metadatas)):
            points.append(qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector={
                    "dense": emb.tolist(),
                    "sparse": qmodels.SparseVector(
                        indices=sparse_emb.indices.tolist(),
                        values=sparse_emb.values.tolist()
                    )
                },
                payload=meta
            ))
            
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        print(f"[INFO] Upserted {len(points)} vectors to Qdrant collection '{self.collection_name}' for {source_filename}.")

    def search(self, query_text: str, user_id: str, top_k: int = 5, filter_source: str = None):
        try:
            must_conditions = [
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchValue(value=user_id)
                )
            ]
            if filter_source:
                must_conditions.append(
                    qmodels.FieldCondition(
                        key="source",
                        match=qmodels.MatchValue(value=filter_source)
                    )
                )
            
            query_filter = qmodels.Filter(must=must_conditions)
            
            dense_query = list(self.model.embed([query_text]))[0].tolist()
            sparse_query = list(self.sparse_model.embed([query_text]))[0]
            
            results = self.client.query_points(
                collection_name=self.collection_name,
                prefetch=[
                    qmodels.Prefetch(
                        query=dense_query,
                        using="dense",
                        limit=20,
                        filter=query_filter
                    ),
                    qmodels.Prefetch(
                        query=qmodels.SparseVector(
                            indices=sparse_query.indices.tolist(),
                            values=sparse_query.values.tolist()
                        ),
                        using="sparse",
                        limit=20,
                        filter=query_filter
                    )
                ],
                query=qmodels.FusionQuery(fusion=qmodels.Fusion.RRF),
                limit=top_k
            ).points
            return results
        except Exception as e:
            print(f"[ERROR] Qdrant search failed: {e}")
            return []

    def query(self, query_text: str, user_id: str, top_k: int = 5, filter_source: str = None):
        print(f"[INFO] Querying vector store for: '{query_text}'" + (f" (filtered by {filter_source})" if filter_source else ""))
        
        fetch_k = max(20, top_k * 3) if self.use_reranker else top_k
        vector_results = self.search(query_text, user_id=user_id, top_k=fetch_k, filter_source=filter_source)
        
        combined_results = []
        for res in vector_results:
            combined_results.append({
                "id": res.id,
                "score": res.score,
                "metadata": res.payload
            })
            
        if not combined_results or not self.use_reranker:
            return combined_results[:top_k]
            
        try:
            passages = [
                {
                    "id": str(i),
                    "text": r["metadata"].get("text", ""),
                    "meta": r["metadata"]
                }
                for i, r in enumerate(combined_results)
            ]
            
            rerankrequest = RerankRequest(query=query_text, passages=passages)
            reranked_results = self.ranker.rerank(rerankrequest)
            
            final_results = []
            for r in reranked_results[:top_k]:
                idx = int(r["id"])
                final_results.append({
                    "id": combined_results[idx]["id"],
                    "score": r["score"],
                    "metadata": r["meta"]
                })
            print(f"[INFO] Reranked {len(combined_results)} results down to {len(final_results)}.")
            return final_results
        except Exception as e:
            print(f"[ERROR] Reranking failed: {e}")
            return combined_results[:top_k]

    def delete_by_source(self, source_filename: str, user_id: str):
        print(f"[INFO] Deleting vectors for source: {source_filename} by user {user_id}")
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="source",
                                match=qmodels.MatchValue(value=source_filename)
                            ),
                            qmodels.FieldCondition(
                                key="user_id",
                                match=qmodels.MatchValue(value=user_id)
                            )
                        ]
                    )
                )
            )
        except Exception as e:
            print(f"[ERROR] Failed to delete vectors for {source_filename}: {e}")

