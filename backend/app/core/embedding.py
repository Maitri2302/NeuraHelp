from typing import List, Any
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from fastembed import TextEmbedding
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
import numpy as np
from .data_loader import load_all_documents

class EmbeddingPipeline:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", chunk_size: int = 1000, chunk_overlap: int = 200, use_semantic: bool = True):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model = TextEmbedding(model_name=model_name)
        self.lc_model = FastEmbedEmbeddings(model_name=model_name)
        self.use_semantic = use_semantic
        print(f"[INFO] Loaded embedding model: {model_name}")

    def chunk_documents(self, documents: List[Any]) -> List[Any]:
        if self.use_semantic:
            splitter = SemanticChunker(self.lc_model, breakpoint_threshold_type="percentile")
            print("[INFO] Using SemanticChunker.")
        else:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
            print("[INFO] Using RecursiveCharacterTextSplitter.")
        
        chunks = splitter.split_documents(documents)
        print(f"[INFO] Split {len(documents)} documents into {len(chunks)} chunks.")
        return chunks

    def embed_chunks(self, chunks: List[Any]) -> np.ndarray:
        texts = [chunk.page_content for chunk in chunks]
        print(f"[INFO] Generating embeddings for {len(texts)} chunks...")
        embeddings = list(self.model.embed(texts))
        emb_array = np.vstack(embeddings)
        print(f"[INFO] Embeddings shape: {emb_array.shape}")
        return emb_array

