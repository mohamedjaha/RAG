# PRD – Simple RAG App (FastAPI + React)

*Product Requirements Document · Version 1.1 · October 17, 2026*

## 1. Overview

This project is a minimal full-stack application. A REST API, built with **FastAPI**, lets a user upload PDF files and ask questions about them. Answers are produced with a Retrieval-Augmented Generation (RAG) pipeline. A very simple **React + Tailwind CSS** user interface sits on top of the API so the whole thing can be demonstrated without Swagger. The goal is **not** to ship a production system, but to **demonstrate RAG skills** in the simplest possible codebase: one Python file, three endpoints, a clear hybrid retrieval pipeline, and a small single-page front end.

The pipeline is taken directly from the source notebook ("RAG notebook"), which uses LangChain, ChromaDB, FastEmbed, BM25, a cross-encoder reranker and a Groq-hosted LLM.

## 2. Goals and Non-Goals

### Goals

- Expose the notebook's RAG pipeline as a simple FastAPI service.
- Show the key RAG techniques: chunking, embeddings, vector search (MMR), keyword search (BM25), Reciprocal Rank Fusion (RRF), cross-encoder reranking, and grounded generation.
- Provide a very simple, clean web interface (React + Tailwind CSS) to upload PDFs, pick files and ask questions.
- Apply a consistent visual identity: a three-color palette and the Josefin Sans font.
- Keep the code small, readable and easy to run locally.
- Return the sources (file, page, snippet) with every answer so results can be verified.

### Non-Goals

- No user accounts, authentication or multi-tenancy.
- No complex front end: no routing, no global state library, no component library, no dark/light theme switch. The UI is one page.
- The built-in Swagger UI at `/docs` remains available for developers but is no longer the main interface.
- No support for `.txt` or `.docx` files (the notebook only loads PDFs).
- No normal (non-RAG) chat mode or conversation memory (the UI shows the current answer only, not a chat history).
- No streaming responses, background jobs or horizontal scaling.

## 3. Target Users

- A developer or student who wants to showcase RAG skills (portfolio, demo, interview).
- Anyone who wants a small, working example to extend later.
- A non-technical viewer who should be able to try the demo through a web page.

## 4. User Stories

1. As a user, I can upload a PDF so that its content becomes searchable.
2. As a user, I can list the PDFs that are already indexed.
3. As a user, I can ask a question and receive an answer based only on my documents.
4. As a user, I can limit a question to one or more specific PDFs.
5. As a user, I can see which file and page each answer came from.
6. As a user, I get "I don't know." when the documents do not contain the answer.
7. As a user, I can do all of the above from a web page, without using any tool other than my browser.
8. As a user, I see clear loading and error messages so I know what the app is doing.

## 5. Functional Requirements

### 5.1 Backend (API)

| ID | Requirement |
| --- | --- |
| FR-1 | `POST /upload` accepts one PDF file, saves it, loads it with PyPDF, splits it into chunks and stores the chunks with embeddings in Chroma. |
| FR-2 | Non-PDF uploads are rejected with HTTP 400. PDFs without extractable text are rejected with HTTP 400. |
| FR-3 | Re-uploading a file with the same name replaces its previous chunks (no duplicates). |
| FR-4 | `GET /files` returns the sorted list of indexed PDF names. |
| FR-5 | `POST /ask` accepts a question, an optional list of files and an optional `k`, and returns an answer plus a list of sources. |
| FR-6 | If `files` contains an unknown name, `/ask` returns HTTP 404. If nothing is indexed, `/ask` returns HTTP 404. |
| FR-7 | The LLM must answer only from the retrieved context and reply exactly "I don't know." when the context is insufficient. |
| FR-8 | The vector index persists on disk (`chroma_db/`) across restarts. |
| FR-9 | The API enables CORS (`CORSMiddleware`) for the front-end origin (`http://localhost:5173` by default) so the React app can call it from the browser. |

### 5.2 Frontend (UI)

| ID | Requirement |
| --- | --- |
| FR-10 | The UI is a single-page React app (built with Vite) styled only with Tailwind CSS utility classes. |
| FR-11 | **Upload:** the user can pick a PDF (button or drag and drop) and send it to `POST /upload`. On success the file list refreshes and a success message shows the file name, pages and chunks. |
| FR-12 | **File list:** on load, and after every upload, the UI calls `GET /files` and shows the indexed PDFs as selectable items (checkboxes or chips). |
| FR-13 | **File filter:** selected files are sent in the `files` field of `POST /ask`. If none is selected, the UI searches all PDFs (the field is omitted). |
| FR-14 | **Ask:** the user types a question in a text field and submits it with a button or the Enter key. The submit button is disabled while the field is empty or a request is running. |
| FR-15 | **Answer:** the answer is displayed in a card. Below it, the sources are listed as small cards showing file name, page number and the snippet. |
| FR-16 | **Optional `k`:** a small numeric input (default 5, range 1–10) lets the user change the number of chunks used. |
| FR-17 | **States:** the UI shows a loading indicator during upload and during questions (answers can take several seconds), and shows a readable error message when the API returns 400 or 404 or cannot be reached. |
| FR-18 | **Empty state:** when no PDF is indexed, the UI shows a short hint ("Upload a PDF to get started") and disables the ask form. |
| FR-19 | The API base URL is read from the `VITE_API_URL` environment variable (default `http://127.0.0.1:8000`). |
| FR-20 | The layout is responsive and usable on both desktop and mobile widths. |

## 6. RAG Pipeline

### 6.1 Ingestion (on upload)

1. **Load** – `PyPDFLoader` reads the PDF page by page.
2. **Chunk** – `RecursiveCharacterTextSplitter` with `chunk_size=800` and `chunk_overlap=150`.
3. **Metadata** – each chunk's `source` is set to the clean file name.
4. **Embed and store** – FastEmbed (`thenlper/gte-large`) embeddings stored in a persistent Chroma collection.

### 6.2 Retrieval (on question)

1. **Semantic search** – Chroma MMR search (`k=20`, `fetch_k=40`), optionally filtered by `source`.
2. **Keyword search** – BM25 over the stored chunks (`k=20`), with the same file filter.
3. **Fusion** – Reciprocal Rank Fusion with `rrf_k=60` merges both ranked lists.
4. **Rerank** – cross-encoder `cross-encoder/ms-marco-MiniLM-L-6-v2` scores each candidate against the question.
5. **Select** – the top `k` chunks (default 5) become the context.

### 6.3 Generation

- Prompt template with strict rules: use only the context, do not invent facts, answer "I don't know." if unsure.
- LLM: Groq `openai/gpt-oss-20b`, `temperature=0.2`, `max_tokens=4000`.
- Output parsed to plain text.

```text
PDF -> chunks -> embeddings -> Chroma

question -> MMR (semantic) --+
                             +-> RRF -> cross-encoder rerank -> top-k -> LLM -> answer + sources
question -> BM25 (keyword) --+
```

## 7. API Specification

### POST /upload

- **Input:** multipart form, field `file` (PDF).
- **Success (200):** `{ "file": "doc.pdf", "pages": 12, "chunks": 48 }`
- **Errors:** 400 (not a PDF, or no text found).

### GET /files

- **Success (200):** `["doc1.pdf", "doc2.pdf"]`

### POST /ask

- **Input (JSON):**

```json
{
  "question": "What is the importance of the title 'I Sell My Dreams'?",
  "files": ["lekl101.pdf"],
  "k": 5
}
```

`files` is optional (default: search all PDFs). `k` is optional (default 5).

- **Success (200):**

```json
{
  "answer": "...",
  "sources": [
    { "file": "lekl101.pdf", "page": 3, "snippet": "first 200 characters of the chunk" }
  ]
}
```

- **Errors:** 404 (unknown file, or nothing indexed yet).

Interactive documentation is available at `/docs` (Swagger UI).

## 8. User Interface Specification

### 8.1 Design principles

- **Simple:** one page, one column of content on mobile, two columns on desktop.
- **Calm and readable:** generous spacing, rounded corners, no decorative clutter.
- **Consistent:** only the three palette colors (and their opacity variants) are used.

### 8.2 Color palette

| Name | Hex | Tailwind token | Usage |
| --- | --- | --- | --- |
| Ink | `#293132` | `ink` | Header, sidebar/panels, main text color, text on accent buttons. |
| Rose | `#CD5D67` | `rose` | Primary buttons, focus rings, active/selected states, links, error accents. |
| Sand | `#D6D5C9` | `sand` | Page background, cards on dark panels, text on Ink backgrounds. |

Guidelines:

- Page background is **Sand**; body text is **Ink**.
- Dark areas (header, upload panel) use **Ink** with **Sand** text.
- Primary buttons use a **Rose** background with **Ink** text (this keeps the text readable); hover state uses `rose/90`.
- Cards are white-ish by mixing Sand with opacity (for example `bg-sand/60` on Ink, or `bg-white/40` on Sand) and a thin `border-ink/20` border.
- Disabled elements use 40–50% opacity.
- Errors use a Rose-bordered box (`border-rose`) with Ink text. No extra red or green colors are introduced; success messages use Ink text on a Sand card with a Rose left border.

### 8.3 Typography

- Font family: **Josefin Sans** (Google Fonts), loaded in `index.html`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Josefin+Sans:wght@300;400;600;700&display=swap" rel="stylesheet" />
```

- Applied globally as the default sans-serif font, with `sans-serif` as the fallback.
- Weights: 700 for the app title, 600 for section titles and buttons, 400 for body text, 300 for secondary text (snippets, hints).
- Base size 16 px; the answer text uses a slightly larger size (`text-lg`) for readability.

### 8.4 Tailwind configuration

The palette and font are declared once as theme tokens (Tailwind CSS v4 syntax, in `src/index.css`):

```css
@import "tailwindcss";

@theme {
  --color-ink: #293132;
  --color-rose: #CD5D67;
  --color-sand: #D6D5C9;
  --font-sans: "Josefin Sans", sans-serif;
}

body {
  @apply bg-sand text-ink font-sans;
}
```

This makes classes such as `bg-ink`, `text-sand`, `border-rose` and `font-sans` available everywhere in the app.

### 8.5 Layout

```text
+------------------------------------------------------------+
|  HEADER (Ink)  "Ask your PDFs"                             |
+------------------------+-----------------------------------+
|  LEFT PANEL (Ink)      |  MAIN AREA (Sand)                 |
|                        |                                   |
|  [ Upload PDF ]        |  Question: [______________] [Ask] |
|  drag & drop zone      |  k: [5]                           |
|                        |                                   |
|  Indexed files         |  ANSWER card                      |
|  [x] doc1.pdf          |                                   |
|  [ ] doc2.pdf          |  SOURCES                          |
|                        |  [file · p.3 · snippet...]        |
+------------------------+-----------------------------------+
```

On mobile widths the left panel stacks above the main area.

### 8.6 Components

The app stays small. A single `App.jsx` file is acceptable; splitting into the components below is optional.

| Component | Responsibility |
| --- | --- |
| `Header` | App title and short tagline. |
| `UploadPanel` | File picker / drag and drop, upload button, upload status message. |
| `FileList` | Fetches and displays indexed files with checkboxes for filtering. |
| `AskForm` | Question input, `k` input, submit button. |
| `AnswerCard` | Displays the answer text, or "I don't know." as returned by the API. |
| `SourceCard` | Displays one source: file name, page and snippet. |
| `Message` | Shared loading / error / success box. |

### 8.7 Behavior and states

| Situation | UI behavior |
| --- | --- |
| App loads | Calls `GET /files`; shows the list or the empty-state hint. |
| Upload in progress | Upload button disabled, "Indexing…" message with a simple spinner. |
| Upload succeeds | Success message ("doc.pdf · 12 pages · 48 chunks"), file list refreshed. |
| Upload fails (400) | Error box with the API's `detail` message. |
| Question in progress | Ask button disabled, "Thinking…" message with a spinner, previous answer cleared. |
| Answer received | Answer card and source cards displayed. |
| Ask fails (404) | Error box with the API's `detail` message (unknown file or nothing indexed). |
| API unreachable | Error box: "Cannot reach the server. Is the API running?" |

### 8.8 Accessibility basics

- All inputs have visible labels or `aria-label`s.
- Buttons are real `<button>` elements and keyboard focusable, with a visible Rose focus ring.
- Text/background pairs follow the palette guidelines above (Ink on Sand, Sand on Ink, Ink on Rose).

## 9. Technical Stack

| Layer | Technology |
| --- | --- |
| API | FastAPI + Uvicorn |
| Orchestration | LangChain |
| PDF loading | PyPDF |
| Embeddings | FastEmbed, model `thenlper/gte-large` |
| Vector store | ChromaDB (persistent) |
| Keyword search | BM25 (`rank_bm25`) |
| Reranker | sentence-transformers CrossEncoder |
| LLM | Groq, `openai/gpt-oss-20b` |
| Front end | React (built with Vite) |
| Styling | Tailwind CSS |
| Font | Josefin Sans (Google Fonts) |
| HTTP client (UI) | Browser `fetch` (no extra library) |

## 10. Configuration

| Setting | Value | Notes |
| --- | --- | --- |
| `GROQ_API_KEY` | environment variable | Required. The app refuses to start without it. |
| `UPLOAD_DIR` | `uploads` | Where PDFs are saved. |
| `CHROMA_DIR` | `chroma_db` | Where the vector index is persisted. |
| `EMBEDDING_MODEL` | `thenlper/gte-large` | About 1.2 GB; use `BAAI/bge-small-en-v1.5` for a lighter demo. |
| `CHAT_MODEL` | `openai/gpt-oss-20b` | Groq-hosted model. |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Loaded once at startup. |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed front-end origin(s) for the API. |
| `VITE_API_URL` | `http://127.0.0.1:8000` | Backend URL used by the React app (set in `frontend/.env`). |

## 11. Project Structure

```text
rag-app/
├── app.py                  # FastAPI backend (single file)
├── requirements.txt
├── uploads/                # saved PDFs (created at runtime)
├── chroma_db/              # vector index (created at runtime)
└── frontend/
    ├── index.html          # loads Josefin Sans
    ├── package.json
    ├── vite.config.js
    ├── .env                # VITE_API_URL
    └── src/
        ├── main.jsx
        ├── index.css       # Tailwind import + palette/font tokens
        └── App.jsx         # the whole UI (or split into small components)
```

## 12. Non-Functional Requirements

- **Simplicity:** the backend is a single file of roughly 180 lines (including the CORS setup); the front end is a single page with a handful of small components (about 200–250 lines in total).
- **Performance:** models are loaded once at startup, not per request. Endpoints are synchronous so FastAPI runs them in a thread pool.
- **Reliability:** the index persists on disk; re-uploads do not create duplicates.
- **Transparency:** every answer lists its sources, in the API response and in the UI.
- **Usability:** every action gives visible feedback (loading, success or error).
- **Compatibility:** the UI works in current versions of Chrome, Firefox, Safari and Edge, on desktop and mobile.
- **Security (demo level):** only `.pdf` uploads are accepted and file names are sanitized with `os.path.basename`. CORS is limited to the configured front-end origin. There is no authentication.

## 13. Changes From the Notebook

- Indexing happens at upload time, not on every start-up.
- Re-uploading a file replaces its old chunks.
- Kaggle secrets are replaced by the `GROQ_API_KEY` environment variable.
- The interactive console chat loop and the normal chat mode are removed; the console is replaced by a React web interface.
- The `.txt` and `.docx` paths are removed (the notebook loader only processed PDFs).

## 14. Risks and Limitations

- The first start is slow because the embedding and reranker models are downloaded.
- BM25 is rebuilt from the stored chunks on every question. This is fine for a demo but will not scale to large corpora.
- Answers are not streamed, so the UI can look idle for several seconds; the loading indicator is therefore required.
- The Rose color has limited contrast on the Sand background, so it is used for buttons, borders and accents, not for small body text.
- Front end and back end run as two separate processes in development; a wrong `VITE_API_URL` or `CORS_ORIGINS` value will make every request fail.
- No authentication, rate limiting or per-user data isolation.
- Scanned PDFs without a text layer cannot be indexed (no OCR).
- Answer quality depends on the LLM and on the retrieved chunks.

## 15. Success Criteria

- A PDF can be uploaded from the web page and appears in the file list.
- A question about the PDF returns a correct, grounded answer with sources, displayed in the UI.
- A question unrelated to the PDF returns "I don't know."
- Selecting specific files in the UI changes which sources are returned.
- Errors (non-PDF upload, unknown file, API down) are shown as readable messages, not as a blank page.
- The UI uses only the palette `#293132`, `#CD5D67`, `#D6D5C9` and the Josefin Sans font.
- The UI is usable on a phone-sized screen.
- The whole project can be set up and run in under five minutes (excluding model download).

## 16. Setup and Run

### Backend

```bash
pip install -r requirements.txt
export GROQ_API_KEY="your_key"      # Windows: set GROQ_API_KEY=your_key
uvicorn app:app --reload
```

API docs: http://127.0.0.1:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173.

The front end is created with:

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install tailwindcss @tailwindcss/vite
```

and the Tailwind plugin is enabled in `vite.config.js`:

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
});
```

## 17. Future Improvements

- Support `.txt` and `.docx` files.
- Add a normal chat mode with conversation history (and a chat-style UI).
- Cache the BM25 index and rebuild it only after uploads.
- Streaming answers in the UI.
- Delete-file button in the file list.
- Authentication and per-user collections.
- OCR for scanned PDFs.
- Serve the built React app directly from FastAPI to run everything with a single command.

## Appendix A – requirements.txt

```text
fastapi
uvicorn[standard]
python-multipart
langchain
langchain-community
langchain-chroma
langchain-groq
langchain-text-splitters
pypdf
fastembed
chromadb
rank_bm25
sentence-transformers
```

## Appendix B – Frontend dependencies (package.json, main entries)

```text
react
react-dom
vite
@vitejs/plugin-react
tailwindcss
@tailwindcss/vite
```