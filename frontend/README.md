# Ask your PDFs — frontend

React + Vite + Tailwind CSS v4 single-page UI for the Simple RAG API (see the
project PRD, section 8).

## Setup

```bash
npm install
npm run dev
```

Then open http://localhost:5173.

The API base URL is read from `.env` (`VITE_API_URL`, default
`http://127.0.0.1:8000`). Start the FastAPI backend first (`uvicorn app:app
--reload` from the project root).
