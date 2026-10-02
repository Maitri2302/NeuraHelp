# NeuraHelp Architecture & Documentation

This document provides a comprehensive technical overview of the NeuraDesk (Python-RAG) architecture, component interactions, and data flow.

## 1. System Architecture Overview

NeuraHelp is structured as a decoupled client-server architecture:
- **Client**: Next.js single-page application (SPA) and Google Chrome Extension.
- **API Gateway**: FastAPI server handling REST requests and synchronous document processing.
- **AI/RAG Engine**: LangGraph and Groq-powered synthesis engine.
- **Storage Layer**: PostgreSQL for structured metadata and Qdrant for vector embeddings.

```mermaid
graph TD;
    Client[Next.js Frontend] --> |REST API| API[FastAPI Backend];
    ChromeExt[Chrome Extension] --> |REST API| API;
    API --> |Diskless Uploads & URL Scraping| Loader[Data Loader & WebBaseLoader];
    API --> |SQL| DB[(PostgreSQL metadata)];
    Loader --> |Text Embeddings| Qdrant[(Qdrant Vectors)];
    API --> |Query| LangGraph[LangGraph Agent];
    LangGraph --> |Semantic Search| Qdrant;
    LangGraph --> |Generation| Groq[Groq API LLM];
```

## 2. Component Deep-Dive

### 2.1 Frontend (Next.js & TailwindCSS)
The frontend is built using Next.js (app router) in a Single Page Application style using a central `page.tsx` that manages state between 4 tabs:
- **ChatTab**: Interacts with `/api/chat` using stateful sessions. Features an animated glassmorphic UI.
- **UploadTab**: Interacts with `/api/upload`. Supports drag-and-drop.
- **ManageTab**: Interacts with `/api/documents` (GET and DELETE) to view and remove indexed documents.
- **SearchTab**: Interacts with `/api/search` allowing users to query specific document subsets and receive AI-synthesized answers over raw contexts.

**Styling**: Utilizes standard TailwindCSS integrated with CSS variables for custom animations (`fade-in-up`, `blob`) and a custom `glass-panel` utility for frosted transparency.

### 2.2 Chrome Extension (Vanilla JS)
A Manifest V3 Chrome Extension is provided to allow users to instantly scrape and index web pages.
- **Popup UI**: Built with HTML/CSS matching the main app's dark-mode glassmorphic aesthetic.
- **Authentication**: Connects to the main app using the user's JWT token.
- **Scraping logic**: Grabs the active tab's URL and submits it to the backend's `/api/upload-url` endpoint for asynchronous server-side scraping.
- **In-Browser Chat**: Allows users to chat directly with the LLM about the current page.

### 2.3 Backend (FastAPI & Celery)
The backend `api.py` acts as the main controller. It uses standard Pydantic models for request/response validation.
- **CORS**: Configured to accept traffic from `http://localhost:3000` and `chrome-extension://*`.
- **Statelessness**: The backend maintains no disk state. All uploaded files are stored temporarily via Python's `NamedTemporaryFile` and deleted inside `finally` blocks after processing.
- **Synchronous Processing**: File parsing, web scraping (`WebBaseLoader`), and vector embedding are processed synchronously within the FastAPI request lifecycle to guarantee immediate availability in the knowledge base.

### 2.4 Data Ingestion Pipeline (`src/data_loader.py` & `src/embedding.py`)
When a file is uploaded or a URL is scraped:
1. **Extraction**: The file extension dictates the `langchain_community` loader (e.g., `PyMuPDFLoader`, `Docx2txtLoader`, `CSVLoader`). `PyMuPDFLoader` is explicitly used for PDF files to ensure robust text extraction compared to basic parsers. Excel files (`.xlsx`, `.xls`) are read using `pandas.ExcelFile` wrapped in a `with` context manager to prevent file-locking issues (`WinError 32`) on Windows. URLs are fetched directly from the backend using LangChain's `WebBaseLoader` (powered by `beautifulsoup4`).
2. **Chunking**: The extracted documents are fed into a `RecursiveCharacterTextSplitter`.
3. **Metadata Enrichment**: Each chunk is annotated with `source`, `page`, and custom metadata tracking its origin file.

### 2.5 Vector Database (`src/vectorstore.py`)
NeuraDesk uses **Qdrant** for vector storage.
- **Embeddings**: Employs `sentence-transformers/all-MiniLM-L6-v2` locally to map text chunks to 384-dimensional vectors.
- **Payload Management**: Qdrant stores the raw text and source metadata in the vector payload.
- **Search capabilities**: Uses `client.query_points` (Qdrant 1.18.0 API) for highly efficient cosine similarity lookups. Also supports precise `source` filtering to scope down searches to specific files or URLs.
- **Deletion**: When a document or URL is deleted via the API, the vector store executes a filter deletion (`delete_by_source`) to scrub all associated vector chunks immediately.

### 2.6 Relational Database (`src/db.py`)
**PostgreSQL** is used purely for lightweight metadata tracking.
- Maintains a `documents` table detailing `id`, `filename`, `document_type`, `size`, and `upload_date`.
- This ensures the UI has a fast, source-of-truth list of what is currently ingested without querying the heavier vector store.

### 2.7 LLM Orchestration (`src/search.py`)
Uses **LangGraph** to build a reliable conversational agent state machine.
- **State Definition**: Tracks `messages` and `context` across agent nodes.
- **Nodes**:
  - `retrieve`: Calls the vector store to fetch relevant chunks based on the user's latest message.
  - `generate`: Combines the retrieved context with the user's prompt and sends it to the Groq LLM API.
- **Edge Routing**: A straightforward `START -> retrieve -> generate -> END` pipeline.
- The default LLM is `llama-3.3-70b-versatile`, chosen for high-speed inference and reasoning accuracy.

## 3. Data Flow Lifecycles

### Document Upload Lifecycle
1. User drags `report.pdf` into Next.js UI (or clicks "Scrape" in Chrome Extension).
2. HTTP POST multipart/form-data to FastAPI `/api/upload` (or JSON to `/api/upload-url`).
3. `api.py` streams file into a temporary tempfile, and `data_loader.py` parses it. If URL: `WebBaseLoader` fetches the page content.
4. `db.py` creates or updates a record in Postgres.
5. `vectorstore.py` chunks the documents, embeds them via SentenceTransformers, and upserts them to Qdrant.
6. Tempfile is explicitly unlinked (deleted) from disk.
7. API responds with HTTP 200 OK to the client, and the frontend instantly refreshes the Knowledge Base.

### Chat & Query Lifecycle
1. User submits query "Summarize the report" in the UI.
2. HTTP POST to FastAPI `/api/chat`.
3. `api.py` invokes `RAGSearch.graph.invoke()`.
4. `retrieve` node queries Qdrant for the top 5 chunks matching the query embedding.
5. `generate` node feeds the query + the 5 chunks to Groq API using a specialized System Prompt.
6. Groq returns the synthesized string.
7. API responds with HTTP 200 containing `{ "answer": "..." }`.

## 4. Configuration Details
- **Ports**: 
  - FastAPI: `8000`
  - Next.js: `3000`
  - PostgreSQL: `5432` (Internal) / `5433` (External mapping)
  - Qdrant: `6333`
- **Environment Variables**: Managed via `.env` files in both the frontend and backend. Specifically, `GROQ_API_KEY` is required on the backend for LLM generation.
