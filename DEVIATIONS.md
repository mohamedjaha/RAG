# DEVIATIONS.md — deviations between the delivered code and the RAG notebook

## 1. Purpose

This file records **every place the delivered application differs from `docs/notebook.ipynb`** (the source of truth for all RAG logic) and why. Each entry is assigned one of the fixed categories:

- **(a) PRD requirement** — the difference is required or explicitly resolved by `docs/PRD – Simple RAG API (FastAPI).md`.
- **(b) bug fix** — the notebook contains a defect that blocks the app; fixed minimally and logged here (AGENTS.md §3 rule 6).
- **(c) import change** — only the import path changed (e.g. a moved/deprecated LangChain module); behavior is identical (AGENTS.md §3 rule 5).
- **(d) allowed extension** — one of the nine extensions listed in AGENTS.md §5, which exist because the PRD requires something the notebook has no equivalent for.
- **(e) owner-directed decision** — the project owner chose a change that departs from the notebook even though a notebook-faithful alternative existed and was working. Added 2026-10-17 for D-01 (see "New deviation D-01: models replaced by Jina AI APIs").

An empty difference list would mean "zero deviations", but this file must exist regardless. Sections 2 and 4 are populated up front from AGENTS.md §6 and from the notebook reading pass (milestone M1); section 6 starts empty and is appended to by milestones M2/M3/M4 as code is written.

**Note on document paths:** AGENTS.md refers to `notebook/notebook.ipynb` and `PRD_Simple_RAG_API.md`; the actual files in this repository are `docs/notebook.ipynb` and `docs/PRD – Simple RAG API (FastAPI).md` (en-dash in the filename). Same documents, different paths — no behavioral impact.

---

## 2. Conflicts from AGENTS section 6

All eight known conflicts, reproduced from AGENTS.md §6 (first three columns use its own wording). Resolution rules apply exactly as written there.

| # | What the notebook does | What the PRD says | What we do | Category | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | The `Retriever` class implements the full hybrid pipeline (MMR + BM25 + RRF + cross-encoder). But the final `RAG_Generation` chain actually uses `RAG_Retrieval.get_retriever()`, which is **plain MMR only**, `k=8`. | The pipeline must be hybrid. | Wire the app to `Retriever.invoke()` (it is notebook code and matches the PRD). Do not use the plain-MMR path. | (a) PRD requirement | Not started |
| 2 | Prompt has three rules: say exactly `"I don't know."` if the context is insufficient; "if you have any information that can help say it"; "try to use all context". | "Strict rules: use only the context, do not invent facts." | Use the notebook prompt **verbatim**. Do not add the PRD's extra rules. Ask the owner if stricter wording is wanted. | (a) PRD requirement | Not started |
| 3 | MMR is called with `k=20` and **no `fetch_k`** (the library default applies). | `fetch_k=40`. | Follow the notebook: do not pass `fetch_k`. | (a) PRD requirement | Not started |
| 4 | `Embedding.get_Models()` returns `self.chat_Models`, an attribute that does not exist (bug). | Not mentioned. | Do not copy the bug. Return `self.chat_llm` or drop the method, and log it. | (b) bug fix | Not started |
| 5 | `Embedding.__init__` rebuilds the Chroma index from all files every time it is created, which duplicates chunks when re-run on a persistent directory. | Indexing at upload time; no duplicates. | Covered by allowed extensions 2 and 4. | (b) bug fix (handled by (d) allowed extensions 2 & 4) | Not started |
| 6 | `context` is the raw list of `Document` objects passed into the prompt. | Not specified. | Keep the same behavior for the LLM input unless it breaks. Build the `sources` list separately from the same documents. | (d) allowed extension (sources only; LLM input unchanged) | Not started |
| 7 | `Retriever` has `k=5` while `RAG_Generation` has `k=8`. | Default `k=5`. | Use `k=5` as the default (matches `Retriever`). The API's optional `k` overrides it. | (a) PRD requirement | Not started |
| 8 | Packages installed: langchain, langchain-community, langchain-groq, pypdf, fastembed, chromadb, langchain-chroma. `rank_bm25` and `sentence-transformers` are imported but not installed in the notebook (Kaggle preinstalls them). | `requirements.txt` includes them. | Keep them in `requirements.txt`. | (a) PRD requirement (requirements.txt) | Not started |

**Caveat recorded at conflict #1:** the notebook's recorded test scores (Suite 1 `7/8`, Suite 2 `8/11`, Suite 3 `22/28`, cells 20–22 outputs) were produced through the **plain-MMR `k=8` path**, not the hybrid `Retriever`. They are therefore a reference point, not a strict baseline: the hybrid app is allowed to score differently, and a lower score should first trigger a check against AGENTS.md §4 and this file (AGENTS.md §8).

---

## 3. Environment / setup differences

Differences between the notebook's Kaggle runtime and the delivered local app. All are covered by AGENTS.md §5 (allowed extensions) or §9 (forbidden carry-overs).

| # | Notebook | Delivered app | Category |
| --- | --- | --- | --- |
| 1 | `GROQ_API_KEY` obtained via `kaggle_secrets.UserSecretsClient` and written into `os.environ` (cell 5); hard-coded `/kaggle/input/datasets/mohamedjahha/...` paths (cells 7, 9, 17). | Read `GROQ_API_KEY` from `os.environ` (refuse to start without it); local paths only. Kaggle secrets client and `/kaggle/input/...` paths are never imported or hard-coded (AGENTS.md §5 item 1, §9). | (a) PRD requirement / (d) allowed extension |
| 2 | Indexing happens inside `Embedding.__init__` over a hard-coded `file_links` list at notebook start-up. | Indexing happens at upload time, one PDF at a time via `POST /upload`; re-uploading a file with the same name deletes its old chunks before adding new ones (no duplicates) (AGENTS.md §5 items 2 & 4; PRD FR-1, FR-3). | (d) allowed extension (also resolves conflict #5) |
| 3 | BM25 built from the in-memory `documents`/`chunks` list held by the notebook session (cell 14). | BM25 corpus rebuilt from the chunks stored in Chroma, because the app does not hold them in memory (AGENTS.md §5 item 6). | (d) allowed extension |
| 4 | No `sources` concept anywhere; the chain returns only the answer string (cell 16). | `/ask` returns `file`, 1-based `page` and a 200-character `snippet` built from the same reranked chunks sent to the LLM (`PyPDFLoader` pages are 0-based, converted for display) (AGENTS.md §5 item 7; PRD §7). | (d) allowed extension |
| 5 | No FastAPI, no CORS, no HTTP endpoints, no UI; interaction is via notebook cells and `print()`. | Three endpoints (`POST /upload`, `GET /files`, `POST /ask`), `CORSMiddleware` for `http://localhost:5173`, PRD error codes (400/404), and the whole React + Tailwind single-page UI (palette `#293132` / `#CD5D67` / `#D6D5C9`, Josefin Sans) exist only in the PRD (AGENTS.md §5 item 9; PRD §5, §7, §8). | (a) PRD requirement / (d) allowed extension |
| 6 | `.env` does not exist in the notebook. | The repository `.env` contains `GROQ_API_KEY` whose value is wrapped in **literal double quotes** (verified during M1: value starts and ends with `"`). Any env loader we write must strip surrounding quotes, or Groq returns HTTP 401. **Config-handling note — record and handle at startup.** | (d) allowed extension (config handling) |
| 7 | Test PDFs referenced from Kaggle paths (`/kaggle/input/datasets/mohamedjahha/pdf-test/lekl101.pdf`, `.../test22/IBMSIQDeploymentConfigGuide76021.pdf`). | Test PDFs live in `PDF/`: `lekl101.pdf` (a clean copy of `lekl101 (1).pdf`) and `IBMSIQDeploymentConfigGuide76021.pdf`. The notebook's hard-coded Kaggle file paths are not used. | (d) allowed extension |
| 8 | Notebook pip cell (cell 1) installs: langchain, langchain-community, langchain-groq, pypdf, fastembed, chromadb, langchain-chroma. `rank_bm25`, `sentence-transformers` and `langchain_text_splitters` are imported without being installed by the notebook (Kaggle preinstalls them; `langchain_text_splitters` arrives transitively with `langchain`). | `requirements.txt` (= PRD Appendix A) lists 13 packages: the 7 above plus fastapi, uvicorn[standard], python-multipart, langchain-text-splitters, rank_bm25, sentence-transformers. | (a) PRD requirement (conflict #8) |
| 9 | Persistence is the literal `persist_directory="./chroma_db"` (cell 11). | Same directory, configurable via PRD §10 (`CHROMA_DIR=chroma_db`, `UPLOAD_DIR=uploads`, `CORS_ORIGINS`); the persistent Chroma directory is reused across restarts (AGENTS.md §5 item 8; PRD FR-8). | (d) allowed extension |
| 10 | PRD §10 mentions `BAAI/bge-small-en-v1.5 as a lighter alternative` embedding model. | **Not adopted.** `thenlper/gte-large` stays (AGENTS.md §3 rule 3, §9); the PRD remark is only a suggestion and does not override the notebook. **Superseded 2026-10-17 by D-01:** the embedding model is now `jina-embeddings-v5-text-small` per the project owner's decision (see "New deviation D-01" below). The BGE suggestion itself is still not adopted — the delivered model is Jina, not BGE. | no deviation (explicitly rejected) — embedding-model row superseded by D-01 |
| 11 | The notebook needs only one secret, `GROQ_API_KEY` (cell 5); no other API secret exists anywhere in the notebook. | **New required secret `JINA_API_KEY`**, read from `os.environ` / `.env` (with the same quote-stripping handling as `GROQ_API_KEY`, §3 item 6); the app **refuses to start** if it is missing. Required for both the Jina embeddings and rerank endpoints (D-01). | (e) owner-directed decision (D-01) |
| 12 | N/A — the Kaggle runtime is unaffected; this is a defect of the local machine, not of the notebook. | **Broken Windows User-level environment variable `SSL_CERT_FILE`**: it points at a non-existent path, `C:\Users\ASUS\Desktop\Stage_ete\src\AiService\.venv\Lib\site-packages\certifi\cacert.pem` (a deleted project's venv). `httpx` (used by `huggingface_hub`) calls `ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])` and raises `FileNotFoundError: [Errno 2]`, breaking any local model download — this is the root cause behind D-01. Worth fixing on the machine regardless of D-01, since it breaks any other httpx-based tool; a valid CA bundle exists at `C:\Users\ASUS\miniconda3\Lib\site-packages\certifi\cacert.pem`. | environment issue (not a code deviation; recorded under D-01 "Why") |

---

## 4. Notebook bug log

Bugs and defects found while reading the notebook (M1). Per AGENTS.md §3 rule 6, none of these may be copied silently; each has an explicit disposition.

| # | Location | Defect | Disposition |
| --- | --- | --- | --- |
| B1 | Cell 11, `Embedding.get_Models()` | Returns `self.chat_Models`, an attribute that does not exist (the real attribute is `self.chat_llm`). Calling it raises `AttributeError`. | **Do not copy.** Return `self.chat_llm` or drop the method entirely; logged here (AGENTS.md §6 conflict #4). |
| B2 | Cell 11, `Embedding.__init__` | Rebuilds the Chroma index from all files every time an `Embedding` is instantiated (`Chroma.from_documents` on `./chroma_db`), duplicating chunks on re-run against the persistent directory. | **Superseded by allowed extensions 2 and 4** (upload-time indexing + replace-on-re-upload). Indexing is no longer tied to `__init__` of a global object (AGENTS.md §6 conflict #5). |
| B3 | Cell 16, `RAG_Generation.__init__` | Creates a **second** `Models()` instance with default parameters, separate from the one inside `Embedding` — the notebook therefore instantiates two `ChatGroq` and two `FastEmbedEmbeddings` objects. Functionally the chain works (it uses `self.models.chat_llm`), but it is wasteful duplication. *(Found during M1; not listed in AGENTS.md §6.)* | Minimal adaptation: the app keeps a **single shared `Models` instance** and reuses it in both `Embedding` and `RAG_Generation`. Class names and behavior unchanged; logged here. |
| B4 | Cell 12 | `query = "What is the importance of the title 'I Sell My Dreams ?"` is defined but never used by any later cell (dead code). | Skip — not ported; no behavioral impact. |
| B5 | Cells 20–22 (test suites) | The suites call `rag.response(q)`, i.e. the **plain-MMR `k=8`** path superseded by conflict #1 — so the recorded scores (`7/8`, `8/11`, `22/28`) do not measure the hybrid `Retriever` that the app wires up. Also, each suite duplicates `norm()`/`IDK` verbatim and sleeps 15 s **before** every question (including the first), not strictly "between" questions. | Port the helpers, questions and status logic exactly as written (AGENTS.md §8); keep `time.sleep(15)` per question (configurable delay is allowed). Treat the recorded scores as reference only (see the caveat under §2 above). |

---

## 5. Import changes

Notebook import paths versus what the delivered code will import. Dependency installation has now completed (versions recorded in §5.1 below), so the former "TBD after install" rows are resolved: **all ten notebook import paths were verified working unchanged**. Only import paths may change; behavior may not (AGENTS.md §3 rule 5). Note that D-01 (Jina AI APIs) replaces two notebook components, so two verified import rows are marked "no longer used by the delivered code" below.

| Notebook import | Delivered import | Reason |
| --- | --- | --- |
| `from kaggle_secrets import UserSecretsClient` (cell 5) | **Removed** — `os.environ["GROQ_API_KEY"]` | Kaggle-only module; forbidden carry-over (AGENTS.md §9). Category (d). |
| `from langchain_community.document_loaders import PyPDFLoader` (cell 2) | **Unchanged — verified OK** (langchain-community 0.4.2, pypdf 6.21.1) | Import path works as-is; no change needed. |
| `from langchain_community.embeddings import FastEmbedEmbeddings` (cell 5) | **Import unchanged — verified OK, but no longer used by the delivered code** (langchain-community 0.4.2) | Still imports fine, but D-01 replaces embeddings with a custom Jina API class, so the delivered code will not instantiate `FastEmbedEmbeddings`. `fastembed` remains in requirements.txt anyway (conflict #8). Category (c) import verified + (e) superseded by D-01. |
| `from langchain_groq import ChatGroq` (cell 5) | **Unchanged — verified OK** (langchain-groq 1.1.3) | Import path works as-is; no change needed. |
| `from langchain_text_splitters import RecursiveCharacterTextSplitter` (cell 9) | **Unchanged — verified OK** (langchain-text-splitters 1.1.3) | Package installed explicitly via requirements.txt (not by the notebook's pip cell); import path works as-is. |
| `from langchain_chroma import Chroma` (cell 11) | **Unchanged — verified OK** (langchain-chroma 1.1.0) | Import path works as-is; no change needed. |
| `from langchain_community.retrievers import BM25Retriever` (cell 14) | **Unchanged — verified OK** (langchain-community 0.4.2 with rank_bm25 0.2.2) | Import path works as-is; langchain-community is sunset (see §5.1) but the class still imports and functions. |
| `from sentence_transformers import CrossEncoder` (cell 14) | **Import unchanged — verified OK, but no longer used by the delivered code** (sentence-transformers 6.1.0, torch 2.14.1+cpu) | Still imports fine, but D-01 replaces the local cross-encoder with the Jina rerank API, so the delivered code will not instantiate `CrossEncoder`. `sentence-transformers` remains in requirements.txt anyway (conflict #8). Category (c) import verified + (e) superseded by D-01. |
| `from langchain_core.prompts import ChatPromptTemplate` (cell 16) | **Unchanged — verified OK** (langchain-core 1.6.12) | Import path works as-is; no change needed. |
| `from langchain_core.output_parsers import StrOutputParser` (cell 16) | **Unchanged — verified OK** (langchain-core 1.6.12) | Import path works as-is; no change needed. |
| `from langchain_core.runnables import RunnablePassthrough` (cell 16) | **Unchanged — verified OK** (langchain-core 1.6.12) | Import path works as-is; no change needed. |
| `import os` / `import re, time, unicodedata` (cells 2, 5, 20–22) | Unchanged | Standard library; no change. |
| _(no notebook equivalent)_ | **New:** thin custom class subclassing `langchain_core.embeddings.Embeddings`, implementing `embed_documents()` and `embed_query()` via raw HTTP `POST https://api.jina.ai/v1/embeddings` | Required by D-01: no maintained LangChain integration for the Jina endpoints exists (dead `langchain_community.embeddings.JinaEmbeddings`, unofficial `langchain-jina` 0.0.1.dev0, unrelated `jinaai` SDK — see D-01.2). Category (e). |

### 5.1 Installed versions (verified 2026-10-17)

| Package | Installed version |
| --- | --- |
| Python | 3.13.11 |
| langchain | 1.4.6 |
| langchain-community | 0.4.2 (sunset — emits DeprecationWarning; shim over langchain-classic) |
| langchain-chroma | 1.1.0 |
| langchain-groq | 1.1.3 |
| langchain-text-splitters | 1.1.3 |
| langchain-core | 1.6.12 |
| pypdf | 6.21.1 |
| fastembed | 0.9.0 (stays in requirements.txt per conflict #8; **no longer used by the delivered app** after D-01) |
| chromadb | 1.5.9 |
| rank_bm25 | 0.2.2 |
| sentence-transformers | 6.1.0 (stays in requirements.txt per conflict #8; **no longer used by the delivered app** after D-01) |
| torch | 2.14.1+cpu |

All ten notebook import paths (PyPDFLoader, FastEmbedEmbeddings, BM25Retriever, Chroma, ChatGroq, RecursiveCharacterTextSplitter, ChatPromptTemplate, StrOutputParser, RunnablePassthrough, CrossEncoder) were verified to import **unchanged** in this environment. Note that `fastembed` and `sentence-transformers` remain in `requirements.txt` even though the delivered app will no longer use them — they stay per AGENTS.md conflict #8 / allowed-extension rules.

---

## 6. Deviations found while reading (open section)

The table below started **empty**: milestone M1 read the notebook, PRD and AGENTS.md and found nothing beyond the eight known conflicts (§2) and the bug log (§4). On 2026-10-17 the first entry was appended: **D-01**, the owner-directed replacement of the local embedding model and reranker with Jina AI APIs (full detail in the dedicated "New deviation D-01" section below). Milestones M2 (backend), M3 (evaluation) and M4 (frontend) append any further deviations here as they are discovered while writing code.

| # | Location in notebook | What differs | Reason | Category | Status |
| --- | --- | --- | --- | --- | --- |
| D-01 | Cells 5 & 14 (`Models.__init__` embedding model + `Retriever.__init__` cross-encoder) | Embedding model and reranker replaced by hosted Jina AI APIs (`jina-embeddings-v5-text-small`, `jina-reranker-v3.5`), requiring a new `JINA_API_KEY` secret. | Owner-directed decision taken after local model downloads failed on this machine (broken `SSL_CERT_FILE`; a one-line fix was available and verified — full details in the dedicated D-01 section below). | (e) owner-directed decision | Implemented — verified in code |

Full detail (summary table, root cause, technical contract, expected impact) is in the dedicated section below.

---

## New deviation D-01: models replaced by Jina AI APIs

> **Owner-directed architecture decision, 2026-10-17. Category (e) owner-directed decision. Status: Implemented — verified in code (M4, 2026-10-17)** — the code described here now exists in `app.py`; this section is the implementation reference for milestones M2/M3.

This deviation replaces two notebook components — the local embedding model and the local reranker — with hosted Jina AI APIs. It is **not** a bug fix: a one-line local fix was available and verified to work, and the project owner still chose the API route (see "Why" below). It is recorded here with full transparency and is not presented as anything else.

### D-01.1 Summary table

| Aspect | Notebook (source of truth) | Delivered | Deviation ID/category |
| --- | --- | --- | --- |
| Embedding model | `thenlper/gte-large` via `FastEmbedEmbeddings(model_name="thenlper/gte-large")` (cell 5) — local, 1024-dim | `jina-embeddings-v5-text-small` (Jina hosted API; 1024 default dimensions) | D-01 / (e) owner-directed |
| Embedding serving method | Local model downloaded and run in-process by `fastembed` | Raw HTTP `POST https://api.jina.ai/v1/embeddings`, authenticated with `JINA_API_KEY`; thin custom class subclassing `langchain_core.embeddings.Embeddings` with `embed_documents()` and `embed_query()` (no maintained LangChain integration exists — see D-01.2) | D-01 / (e) owner-directed |
| Reranker model | `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")` (cell 14) — local | `jina-reranker-v3.5` (Jina hosted API) | D-01 / (e) owner-directed |
| Reranker call shape | `CrossEncoder.predict([(query, doc.page_content), ...])` — pairs of (query, doc) | Raw HTTP `POST https://api.jina.ai/v1/rerank` takes **one** `query` string plus a `documents` array of strings — it does NOT accept `(query, doc)` pairs like `CrossEncoder.predict` does | D-01 / (e) owner-directed |
| Required secrets | The notebook needs only `GROQ_API_KEY` (from Kaggle secrets) | Now also requires **`JINA_API_KEY`**, read from `os.environ` / `.env`; the app refuses to start if it is missing | D-01 / (e) owner-directed (also §3 item 11) |

### D-01.2 Why

Local model downloads fail on this machine. Root cause (diagnosed and verified 2026-10-17): the Windows **User-level** environment variable `SSL_CERT_FILE` points at a non-existent path, `C:\Users\ASUS\Desktop\Stage_ete\src\AiService\.venv\Lib\site-packages\certifi\cacert.pem` — a CA bundle belonging to a deleted project's virtualenv. `httpx` (used by `huggingface_hub`) does `ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])` and raises `FileNotFoundError: [Errno 2]` on any download. Verified: removing the variable in-process makes HuggingFace downloads work again (`config.json` downloaded fine). A valid CA bundle exists on the machine at `C:\Users\ASUS\miniconda3\Lib\site-packages\certifi\cacert.pem`.

**A one-line fix was available** (point `SSL_CERT_FILE` at the valid miniconda certifi bundle, or delete the User-level variable) **and the fix was verified to work — the project owner nevertheless decided to switch both models to hosted Jina AI APIs authenticated with a `JINA_API_KEY`.** This is recorded with full transparency as an owner-directed deviation: the local route was working and was abandoned by choice, not by necessity.

Related integration facts (also verified): no maintained LangChain integration exists for the Jina endpoints. `langchain_community.embeddings.JinaEmbeddings` is effectively dead (langchain-community is sunset, embedding modules were removed in LangChain v1, and the class only supports v2-era payloads with no `task`/`dimensions`), and PyPI `langchain-jina` is an unofficial single `0.0.1.dev0` release pinned to langchain-core<0.4. There is also no official Python SDK for these endpoints (PyPI `jinaai` is an unrelated, last-released-2024 SDK for different products — do not install). Raw HTTP is therefore the correct approach.

### D-01.3 Technical contract

All facts below were verified 2026-10-17 against Jina's official OpenAPI spec at `https://docs.jina.ai/openapi.json` (spec version 2026.10.13.1624). This subsection is the implementation reference for M2/M3.

**Embeddings — `POST https://api.jina.ai/v1/embeddings`**

- Headers: `Authorization: Bearer <JINA_API_KEY>`, `Content-Type: application/json`, `Accept: application/json`.
- Request body: required `model` and `input`. Optional: `task` (use `retrieval.passage` at index time, `retrieval.query` at query time; the enum default is `text-matching`), `dimensions` (1–1024), `normalized`, `truncate`, `embedding_type`.
- Model chosen: `jina-embeddings-v5-text-small` — 1024 default dimensions (matches gte-large's 1024, so the Chroma collection dimension is unchanged), 32,768-token context, Matryoshka-truncatable.
- Response shape: `{model, object, usage:{total_tokens, prompt_tokens}, data:[{object, index, embedding}]}`. Results MUST be mapped by `data[i]["index"]`, not by array position.
- Batching: no server-side per-request item limit; Jina advises batching 32–256 inputs per request. We will batch 64–128.
- `normalized`: its default conflicts between official sources (OpenAPI says default true for v5, the docs meta-prompt says false) → we set it explicitly.

**Rerank — `POST https://api.jina.ai/v1/rerank`**

- Same auth headers (`Authorization: Bearer <JINA_API_KEY>`, `Content-Type: application/json`, `Accept: application/json`).
- Request: `query` (string), `model`, `documents` (array of strings), optional `top_n`, optional `return_documents` (default true), optional `max_doc_length`. NOTE: it takes ONE query plus a document list — it does NOT accept `[(query, doc), ...]` pairs like `CrossEncoder.predict` does.
- Model chosen: `jina-reranker-v3.5` (current flagship, 131k context, 63.20 nDCG@10 BEIR). NOTE: `jina-reranker-v2-turbo` is NOT in the current OpenAPI model enum — do not use it.
- Response shape: `{model, object, usage:{total_tokens}, results:[{index, relevance_score, document?}]}`, where `results` is already sorted by `relevance_score` DESCENDING and `index` is the position in the original input `documents` array.

**Error codes and retry policy**

| HTTP | Codes | Action |
| --- | --- | --- |
| 401 | `AUTH_INVALID_API_KEY` / `AUTH_MISSING_API_KEY` | Bad key — do not retry |
| 403 | `AUTHZ_INSUFFICIENT_BALANCE` / `AUTHZ_RESOURCE_LIMIT_EXCEEDED` | Free tokens exhausted — do not retry |
| 429 | `RATE_REQUEST_LIMIT_EXCEEDED` / `RATE_TOKEN_LIMIT_EXCEEDED` | Retry with exponential backoff |
| 400 | `INPUT_TOKEN_LIMIT_EXCEEDED` / `INPUT_MODEL_NOT_FOUND` | Client error — do not retry |
| 500 / 503 / 504 | (transient) | Retry |

**Rate limits (conflicting official sources)**

Rate limits DISAGREE between official sources: the OpenAPI spec says free tier = 500 RPM · 1M TPM, while Jina marketing pages say free tier = 100 RPM · 100K TPM. Design for the conservative **100 RPM / 100K TPM**.

### D-01.4 Expected impact

Stated honestly, without softening:

- **Retrieval results change.** Both the embedding model and the reranker differ from the notebook's, so retrieved chunks, rerank order, and final answers will differ from anything the notebook produced. This is inherent to the decision, not a side effect.
- **The notebook's recorded suite scores are NOT a baseline this build can be scored against strictly.** The recorded scores (Suite 1 `7/8`, Suite 2 `8/11`, Suite 3 `22/28`) were produced with the **local** models (`thenlper/gte-large` + `cross-encoder/ms-marco-MiniLM-L-6-v2`) on the **plain-MMR `k=8` path** (§2 caveat, bug B5). The delivered build is hybrid (per conflict #1) **and** uses different models (this deviation) — two axes of difference from the conditions that produced those scores.
- **Any evaluation result must be reported as-is**, never tuned to match the notebook's numbers (AGENTS.md §8). A `HALLUCINATED` status is a failure to report, not to hide. If scores are worse than the notebook's, first re-check §4 and this file for deviations, then report honestly.

**Status: Implemented — verified in code (M4, 2026-10-17)** — `app.py` now contains the Jina `Embeddings` subclass, the rerank call and the `JINA_API_KEY` startup check; the independent fidelity review confirmed all D-01.3 contract points (URL, model IDs, `task` values, `normalized`/`truncate`, index-mapped responses, batch 64, one-query-plus-documents rerank, Bearer auth, 401/403/429/400/5xx handling). Runtime behaviour is still pending M5.

---

## Appendix A — Notebook → app.py mapping

Mapping of every notebook class, function and test artifact to its target in the delivered application, per AGENTS.md §2. Class names and method names are kept so the notebook and `app.py` can be compared side by side (AGENTS.md §3 rule 1).

### A.1 Classes and functions

| Notebook class / function | Notebook cell | Responsibility | Target in the app (file + name) | Notes |
| --- | --- | --- | --- | --- |
| `Models` | 5 | Builds `ChatGroq` (chat) and `FastEmbedEmbeddings` (embeddings) from model-name defaults. | `app.py` → `Models` | Same defaults (`openai/gpt-oss-20b`, `thenlper/gte-large`). `GROQ_API_KEY` comes from `os.environ` instead of Kaggle secrets (§3 item 1). A single shared instance (bug B3). |
| `File_Loader` | 7 | Filters links by extension (`ALLOWED_FILES = ["pdf"]`) and loads allowed PDFs with `PyPDFLoader`. | `app.py` → `File_Loader` | Reused at upload time for the one saved file per request (allowed extension 2). Class/method names unchanged. |
| `Chunker` | 9 | Wraps `File_Loader` + `RecursiveCharacterTextSplitter`; `split()` returns chunks. | `app.py` → `Chunker` | Constructor defaults are `chunk_size=1000, chunk_overlap=150`, but the app always reaches it through `Embedding`, which passes `800/150` — exactly the notebook's behavior. |
| `Embedding` | 11 | Creates `Models`, chunks the files, builds the persistent Chroma store via `Chroma.from_documents`. | `app.py` → `Embedding` | Indexing is triggered per upload instead of per `__init__` over all files (allowed extensions 2 & 4, conflict #5). `get_Models()` bug B1 not copied. `get_db()` / `get_chunks()` kept. |
| `Retriever` | 14 | Full hybrid pipeline: MMR semantic search + BM25 keyword search + RRF fusion (`_rrf`, `_document_key`) + cross-encoder rerank, returning top-`k` docs from `invoke()`. | `app.py` → `Retriever` (with `invoke`, `_rrf`, `_document_key`) | **This is the retriever wired to `POST /ask`** (conflict #1, AGENTS.md §10). Optional `files` filter is added to both branches (allowed extension 5) without touching the rest of the logic. |
| `RAG_Retrieval` | 16 | Owns the `Embedding`; `get_retriever(k=5)` returns a **plain MMR** retriever. | `app.py` → `RAG_Retrieval` | Kept for side-by-side comparison per fidelity rule 1, but its plain-MMR path is **not** used by `/ask` (conflict #1). |
| `RAG_Generation` | 16 | Prompt template + LCEL chain `{"context": retriever, "query": RunnablePassthrough()} \| prompt \| chat_llm \| StrOutputParser()`; `response(query)` returns the answer text. | `app.py` → `RAG_Generation` (with `response`) | Template used **verbatim** (conflict #2). Context is the hybrid docs from `Retriever.invoke()` fed to the same prompt/LLM/parser chain; `k` default is `5` (conflict #7), overridable by the API's `k`. The LLM input stays the raw list of `Document` objects (conflict #6); `sources` are built separately from the same docs (allowed extension 7). |
| `template` (prompt) | 16 | The generation prompt: IDK rule + "if you have any information that can help say it" + "try to use all context", then `Context: {context}` / `Question: {query}` / `Answer:`. | `app.py` → `RAG_Generation` template argument | Verbatim, character for character, including the trailing spaces on two rule lines and the blank lines (AGENTS.md §3 rule 2). PRD's stricter wording is **not** added (conflict #2). |
| `norm()` | 20, 21, 22 (identical copies) | Normalizes answers: NFKD lowercase, strip combining marks, dashes→space, strip apostrophes/markdown, NBSP→space, collapse whitespace. | `tests/test_notebook_suites.py` → `norm` | Copied exactly; all three cells contain the same function. |
| `IDK` | 20, 21, 22 (identical copies) | `["i dont know", "not in", "no information", "not mentioned", "cannot", "not provided"]` — phrases that mark an "I don't know" style answer. | `tests/test_notebook_suites.py` → `IDK` | Copied verbatim. |
| `tests` (Suite 1) | 20 | 8 answerable questions about the story "I Sell My Dreams" with expected keywords; loop with `time.sleep(15)`, statuses `PASS` / `MISS (idk)` / `WRONG` / `HALLUCINATED` / `EMPTY`, final `Score: x/y`. | `tests/test_notebook_suites.py` → Suite 1 | Questions and keywords copied as-is (AGENTS.md §8). Served through `POST /upload` (lekl101.pdf) + `POST /ask`. Notebook recorded score: **7/8** (via the plain-MMR path — see §2 caveat). |
| `tests` (Suite 2) | 21 | Same story: 7 answerable + 4 unanswerable questions (11 total), same helper logic. | `tests/test_notebook_suites.py` → Suite 2 | Copied as-is. Unanswerable questions must yield an IDK-style answer, else `HALLUCINATED`. Notebook recorded score: **8/11**. |
| `tests` (Suite 3) | 22 | IBM StoredIQ deployment guide: 25 answerable + 3 unanswerable questions (28 total), same helper logic. | `tests/test_notebook_suites.py` → Suite 3 | Copied as-is; uses `PDF/IBMSIQDeploymentConfigGuide76021.pdf`. Notebook recorded score: **22/28**. |

### A.2 Exact values to copy verbatim

Every value below was verified against the notebook during M1; the notebook wins if any other document disagrees (AGENTS.md §1, §3 rule 2, §4).

| Component | Exact value | Notebook cell |
| --- | --- | --- |
| Chat model | `ChatGroq(model="openai/gpt-oss-20b", temperature=0.2, max_tokens=4000)` — i.e. model `openai/gpt-oss-20b` | 5 (`Models.__init__`) |
| Temperature | `0.2` | 5 |
| Max tokens | `4000` | 5 |
| Embedding model | `FastEmbedEmbeddings(model_name="thenlper/gte-large")` — i.e. `thenlper/gte-large` | 5 (defaults reused by `Embedding`, cell 11) — **superseded 2026-10-17 by D-01**: the delivered embedding model is `jina-embeddings-v5-text-small` (owner-directed decision) |
| Allowed files | `ALLOWED_FILES = ["pdf"]`, loaded with `PyPDFLoader` | 7 (`File_Loader`) |
| Chunk size | `chunk_size=800` (the `Chunker` default of 1000 is overridden by `Embedding`) | 11 (`Embedding.__init__`; `Chunker` default at 9) |
| Chunk overlap | `chunk_overlap=150` | 11 (`Embedding.__init__`; `Chunker` default at 9) |
| Vector store | `Chroma.from_documents(documents=..., embedding=..., persist_directory="./chroma_db")` | 11 |
| Semantic search | `as_retriever(search_type="mmr", search_kwargs={"k": 20})` — `k=20`, **no `fetch_k`** | 14 (`Retriever.__init__`, `candidate_k=20`) |
| Keyword search | `BM25Retriever.from_documents(documents)` with `self.bm25_retriever.k = 20` | 14 (`bm25_k=20`) |
| Fusion | RRF: `scores[key] = scores.get(key, 0) + (1 / (self.rrf_k + rank))`, `rrf_k = 60`, ranks start at 1 via `enumerate(..., start=1)`, dedup key = `(doc.page_content, str(sorted(doc.metadata.items())))` | 14 (`_rrf`, `_document_key`) |
| Reranker | `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")`, scores `(query, doc.page_content)` pairs, sorted by score descending | 14 (`Retriever.__init__`, `invoke`) — **superseded 2026-10-17 by D-01**: the delivered reranker is `jina-reranker-v3.5` via the Jina rerank API (owner-directed decision) |
| Final chunks | `k=5` (default of `Retriever`; `RAG_Generation`'s `k=8` is superseded — conflict #7) | 14 (`k=5`); 16 (`k=8`, not used) |
| Prompt template | Verbatim `template` in `RAG_Generation`: "You are an AI assistant that answers questions using the provided context." + Rules (`"I don't know."` rule, "if you have any information that can help say it ", "try to use all context to answer " — note trailing spaces) + `Context:\n{context}` + `Question:\n{query}` + `Answer:` | 16 (`RAG_Generation.__init__`) |
| Chain | `{"context": retriever, "query": RunnablePassthrough()} \| self.prompt \| self.models.chat_llm \| StrOutputParser()` | 16 (`RAG_Generation.__init__`) |
| Test delay | `time.sleep(15)` per question (Groq rate limits) | 20, 21, 22 |
