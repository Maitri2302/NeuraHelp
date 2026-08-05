# NeuraDesk (Python-RAG)

NeuraDesk is a modern, high-performance Retrieval-Augmented Generation (RAG) platform. It allows users to upload custom documents and chat with a Large Language Model (LLM) that has exact knowledge of those documents.

Built with a **Next.js** frontend and a **FastAPI** backend, the system utilizes **Qdrant** for vector search, **PostgreSQL** for metadata tracking, and **LangGraph** for AI orchestration.

---

## 🚀 Features

- **Dynamic Premium UI**: A highly engaging, glassmorphic Next.js interface with micro-animations.
- **Diskless Ingestion**: Uploaded documents are parsed entirely in memory/temp-space and never saved to disk.
- **Multi-Format Support**: Ingests PDF (via PyMuPDF for robust extraction), Text, CSV, Excel (with safe file lock handling), Word, and JSON files seamlessly.
- **Web Scraping Chrome Extension**: Easily upload and index any webpage directly from your browser. The backend utilizes LangChain's WebBaseLoader and a Celery worker to asynchronously index the web content.
- **Agentic RAG Engine**: Utilizes LangGraph to power an advanced conversational and search pipeline, ensuring accurate answers with context citations.
- **Secure Multi-Tenancy**: Persistent Postgres storage and session-based authentication prevents data cross-contamination between different users.
- **Hybrid Search & Management**: You can query the entire knowledge base, or filter by specific uploaded documents (or URLs).
- **Local Embeddings & High-Speed LLMs**: Generates semantic embeddings locally using `sentence-transformers` and queries via the lightning-fast Groq API (`llama-3.3-70b-versatile`).

---

## 🛠️ Tech Stack

### Frontend
- **Framework**: Next.js 15 (React 19)
- **Styling**: Tailwind CSS v4, custom CSS Keyframes, Glassmorphism
- **Language**: TypeScript

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **AI/LLM**: LangChain, LangGraph, Groq API
- **Embeddings**: `sentence-transformers` (`all-MiniLM-L6-v2`)
- **Metadata Database**: PostgreSQL (via `asyncpg`)
- **Vector Database**: Qdrant (Dockerized)

### Browser Extension
- **Platform**: Google Chrome (Manifest V3)
- **Technologies**: Vanilla HTML/CSS/JavaScript

---

## ⚙️ Quickstart Setup

### 1. Prerequisites
- Docker & Docker Compose (for PostgreSQL, Redis, and Qdrant)
- Node.js (for Next.js frontend)
- Python 3.10+ and `uv` package manager (for FastAPI backend)

### 2. Infrastructure Setup
Start the local databases (Postgres, Redis, and Qdrant) using Docker Compose:
```bash
docker-compose up -d
```

### 3. Backend Setup
1. Navigate to the `backend` directory.
2. Create a `.env` file based on `.env.example` (ensure `GROQ_API_KEY`, Postgres, Redis, and Qdrant variables are set).
3. Install dependencies:
```bash
cd backend
uv pip install -r requirements.txt
```
4. Run the FastAPI server:
```bash
uv run python -m uvicorn app.main:app --reload
```
*The backend will be available at http://127.0.0.1:8000*

### 4. Frontend Setup
1. Navigate to the `frontend` directory.
2. Install dependencies:
```bash
cd frontend
npm install
```
3. Run the development server:
```bash
npm run dev
```
*The UI will be available at http://localhost:3000*

### 5. Chrome Extension Setup
1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (top right corner).
3. Click **Load unpacked** and select the `chrome-extension` directory in this repository.
4. Open the extension, enter your NeuraDesk login details, and seamlessly scrape and query web pages!

---

## 📖 Further Reading
For a deep dive into the architecture, component interaction, and design decisions, please read the [DOCUMENTATION.md](./DOCUMENTATION.md) file.
