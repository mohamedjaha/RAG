# Milestones – Simple RAG App (FastAPI + React)

*Living plan. Tick the boxes as milestones complete; update the Status column in the summary table.*

**Source of truth:** `docs/notebook.ipynb` (RAG logic) → `docs/PRD – Simple RAG API (FastAPI).md` (everything the notebook is silent on) → `AGENTS.md` (process).

---

## Confirmed decisions

| # | Decision | Consequence |
| --- | --- | --- |
| D1 | ~~Embeddings and reranking run **locally**, no API keys. Only `GROQ_API_KEY` is required.~~ **Superseded by D4.** | Was: zero pipeline deviations with `thenlper/gte-large` + `cross-encoder/ms-marco-MiniLM-L-6-v2`. Kept for audit trail only. |
| D2 | `PDF/lekl101 (1).pdf` is **copied** to a clean `PDF/lekl101.pdf` for evaluation. The original is left untouched. | Eval references match the PRD example and notebook expectations. |
| D3 | The notebook prompt is used **verbatim**. The PRD's stricter wording (§6.2) is *not* added. | Recorded in `DEVIATIONS.md` and flagged to the owner. |
| D4 | **Owner-directed:** embeddings and reranking moved to hosted **Jina AI** APIs, authenticated with `JINA_API_KEY`. Replaces decision D1. | Deviation **D-01** in `DEVIATIONS.md`: embed `jina-embeddings-v5-text-small` (1024-dim, matches `gte-large`), rerank `jina-reranker-v3.5`. Retrieval results will differ from the notebook's; scores reported as-is, never tuned. |
| D4a | Root cause of the local-download failure was diagnosed and verified: a broken **User-level `SSL_CERT_FILE`** pointing into a deleted project's venv (`Stage_ete\...\cacert.pem`). A one-line fix was available and confirmed working; the owner still chose D4. | Recorded in `DEVIATIONS.md` §3. The stale variable still breaks other httpx-based tools on this machine. |

## Environment (checked 2026-10-17)

| Item | Value |
| --- | --- |
| Python | 3.13.11 (miniconda) |
| pip | 25.3 |
| Node / npm | 22.16.0 / 10.9.2 |
| RAG packages installed | ✅ All 13 (LangChain 1.4.6, chromadb 1.5.9, fastembed 0.9.0, sentence-transformers 6.1.0, torch 2.14.1+cpu) — 10/10 notebook import paths OK |
| Secrets | `GROQ_API_KEY` ✅ verified (`openai/gpt-oss-20b` replied) · `JINA_API_KEY` ✅ verified (embed + rerank both 200) |
| Test PDFs | `PDF/lekl101.pdf` (clean copy ✅), `PDF/IBMSIQDeploymentConfigGuide76021.pdf` |
| Known machine issue | User-level `SSL_CERT_FILE` points at a deleted venv → breaks `huggingface_hub`/httpx downloads. Not fixed (owner chose D4). |
| Git state | `docs/` + `AGENTS.md` untracked; `README.md` + `notebook.ipynb` deleted but uncommitted — committing at the end (owner decision) |

---

## Status summary

| # | Milestone | Status | Depends on |
| --- | --- | --- | --- |
| M0 | Environment & prerequisites | ✅ Done | – |
| M1 | Fidelity mapping + `DEVIATIONS.md` | ✅ Done | M0 |
| M2 | Backend – notebook pipeline ported to `app.py` | ✅ Done | M1 |
| M3 | Backend – API layer | ✅ Done | M2 |
| M4 | Fidelity check | ✅ Done (zero violations) | M3 |
| M5 | Evaluation – notebook's 3 test suites | ✅ Done — **43/47** (7/8, 10/11, 26/28) | M4 |
| M6 | Frontend – scaffold & design system | 🟡 In progress | M3 |
| M7 | Frontend – features & states | ⬜ Not started | M6 |
| M8 | End-to-end acceptance | ✅ Done (staged, awaiting owner's commit) | M5, M7 |

Legend: ⬜ Not started · 🟡 In progress · ✅ Done · ⛔ Blocked

---

## M0 — Environment & prerequisites ✅

*Completed 2026-10-17.*

- [x] `pip install -r requirements.txt` — all 13 packages; Python 3.13 wheels, no source builds. One unrelated pre-existing conflict (`mistralai` vs chromadb's opentelemetry pin) left alone.
- [x] Import-path check — all 10 notebook imports resolve unchanged.
- [x] `GROQ_API_KEY` smoke test — `openai/gpt-oss-20b` returned `OK`.
- [x] `JINA_API_KEY` smoke test (replaces the local model download) — embed 1024-dim ✅, batch embed ✅, rerank `jina-reranker-v3.5` descending ✅.
- [x] `Copy-Item "PDF\lekl101 (1).pdf" "PDF\lekl101.pdf"` (decision D2).
- [x] `.gitignore` created (`uploads/`, `chroma_db/`, `node_modules/`, `.env`, `__pycache__`).
- [x] Git handling decided: leave the `docs/` reorganisation uncommitted; commit everything at the end.

**Local model downloads — superseded by D4.** The attempt failed with `FileNotFoundError: [Errno 2]` from `httpx` because `SSL_CERT_FILE` points at a deleted venv (`Stage_ete\...\cacert.pem`). Verified that clearing the variable restores HuggingFace downloads. Owner chose the Jina API route instead; the stale variable remains on the machine.

**PDF validation (both test documents confirmed usable):**

| File | Pages | Chars | Text layer |
| --- | --- | --- | --- |
| `lekl101.pdf` | 11 | 19,877 | ✅ |
| `IBMSIQDeploymentConfigGuide76021.pdf` | 94 | 224,256 | ✅ |

Chunking check with the notebook's exact values (`chunk_size=800`, `chunk_overlap=150`) on `lekl101.pdf`: **34 chunks**, lengths min/avg/max = 246 / 665 / 797.

**Definition of done:** ✅ met — every required secret verified, both test PDFs proven to have extractable text, chunking parameters confirmed.

---

## M1 — Fidelity mapping + `DEVIATIONS.md` ⬜

- [ ] Write the notebook-class → `app.py` mapping (`Models`, `File_Loader`, `Chunker`, `Embedding`, `Retriever`, `RAG_Retrieval`, `RAG_Generation`).
- [ ] Create `DEVIATIONS.md` and record the eight known differences from AGENTS §6:
  1. App uses hybrid `Retriever.invoke()`, not the plain-MMR `RAG_Retrieval.get_retriever()` path.
  2. Notebook prompt kept verbatim; PRD's stricter rules not added (decision D3).
  3. No `fetch_k` on MMR (library default), unlike the PRD's `fetch_k=40`.
  4. `Embedding.get_Models()` bug (`self.chat_Models`) not copied.
  5. Indexing moved to upload time; no duplicate chunks on a persistent directory.
  6. `context` remains the raw list of `Document` objects for the LLM input; `sources` built separately.
  7. Default `k = 5` (from `Retriever`), not `RAG_Generation`'s `k = 8`.
  8. `rank_bm25` and `sentence-transformers` kept in `requirements.txt` although the notebook never installed them.

**Definition of done:** every AGENTS §4 value has a planned home in `app.py`; `DEVIATIONS.md` exists.

---

## M2 — Backend: notebook pipeline ported to `app.py` ⬜

- [ ] `Models` — `ChatGroq(model="openai/gpt-oss-20b", temperature=0.2, max_tokens=4000)` verbatim; `self.embedding_model` = the Jina `Embeddings` subclass (**D-01** replaces `FastEmbedEmbeddings`, 1024-dim either way).
- [ ] `File_Loader` — `ALLOWED_FILES = ["pdf"]`, `PyPDFLoader`.
- [ ] `Chunker` — `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)`.
- [ ] `Embedding` — persistent `Chroma(persist_directory="./chroma_db")`; skip the buggy `get_Models()`.
- [ ] Jina adapter — thin `langchain_core.embeddings.Embeddings` subclass: `embed_documents()` (`task="retrieval.passage"`, batches of 64–128, map results by `data[i]["index"]`) and `embed_query()` (`task="retrieval.query"`); `normalized` set explicitly; Bearer auth; quote-stripped key.
- [ ] `Retriever` — MMR `k=20` (no `fetch_k`), `BM25Retriever` `k=20`, `_rrf` with `rrf_k=60` and `_document_key`, rerank via `POST /v1/rerank` (`jina-reranker-v3.5`, one query + documents array, take `results[:k]` by `index`), final `k=5`.
- [ ] Rerank error mapping — 401 bad key, 403 out of tokens, 429 retry w/ backoff, 400 client error, 5xx transient.
- [ ] `RAG_Generation` — prompt template character-for-character, `.invoke()` on the chain.
- [ ] Wire the generation path to `Retriever.invoke()` (hybrid), **not** plain MMR.
- [ ] `GROQ_API_KEY` **and** `JINA_API_KEY` read from `os.environ` (quotes stripped from `.env`); refuse to start without either. No Kaggle paths or secrets client.

**Definition of done:** `Retriever.invoke(<question>)` returns 5 reranked chunks from `PDF/lekl101.pdf`.

---

## M3 — Backend: API layer ⬜

- [ ] `POST /upload` — multipart `file`; reject non-PDF and text-less PDFs with 400; sanitize with `os.path.basename`; **delete old chunks with the same `source` before adding** (no duplicates).
- [ ] `GET /files` — sorted list of indexed PDF names.
- [ ] `POST /ask` — `question`, optional `files`, optional `k`; unknown file → 404, nothing indexed → 404.
- [ ] `files` filter applied to both Chroma metadata search and the BM25 chunk list.
- [ ] BM25 rebuilt from the chunks stored in Chroma.
- [ ] `sources` = `file`, 1-based `page`, 200-character `snippet` from the reranked chunks.
- [ ] Persistent `chroma_db/` reloaded across restarts.
- [ ] `CORSMiddleware` for `http://localhost:5173`.
- [ ] `requirements.txt` per PRD Appendix A.

**Definition of done:** all three endpoints verified in Swagger (`/docs`) with correct status codes and response shapes.

---

## M4 — Fidelity check ⬜

- [ ] Verify every AGENTS §4 row against `app.py` and report the result as a table.
- [ ] Confirm any mismatch is either corrected or logged in `DEVIATIONS.md`.

| Component | Required value | Match? |
| --- | --- | --- |
| Chat model | `openai/gpt-oss-20b`, `temperature=0.2`, `max_tokens=4000` | ⬜ |
| Embeddings | ~~`thenlper/gte-large`~~ → `jina-embeddings-v5-text-small`, 1024-dim (**D-01**) | ⬜ |
| Allowed files | `["pdf"]`, `PyPDFLoader` | ⬜ |
| Chunking | `chunk_size=800`, `chunk_overlap=150` | ⬜ |
| Vector store | `Chroma`, `persist_directory="./chroma_db"` | ⬜ |
| Semantic search | MMR, `k=20`, no `fetch_k` | ⬜ |
| Keyword search | `BM25Retriever.from_documents`, `k=20` | ⬜ |
| Fusion | `score += 1 / (rrf_k + rank)`, `rrf_k=60`, rank from 1 | ⬜ |
| Document key | `(page_content, str(sorted(metadata.items())))` | ⬜ |
| Reranker | ~~`cross-encoder/ms-marco-MiniLM-L-6-v2`~~ → `jina-reranker-v3.5`, descending (**D-01**) | ⬜ |
| Final chunks | `k=5` | ⬜ |
| Prompt | `RAG_Generation` template, verbatim | ⬜ |

---

## M5 — Evaluation: the notebook's own test suites ⬜

*The real acceptance gate. Never edit questions or keywords to make tests pass.*

- [ ] Port `norm()`, the `IDK` list and the status logic (`PASS`, `MISS (idk)`, `WRONG`, `HALLUCINATED`, `EMPTY`) to `tests/test_notebook_suites.py`.
- [ ] Upload `PDF/lekl101.pdf` and `PDF/IBMSIQDeploymentConfigGuide76021.pdf` through `POST /upload`.
- [ ] Send every question through `POST /ask`; keep `time.sleep(15)` (configurable) between questions.
- [ ] Suite 1 — "I Sell My Dreams", 8 answerable questions.
- [ ] Suite 2 — same story, 7 answerable + 4 unanswerable questions.
- [ ] Suite 3 — IBM StoredIQ guide, 25 answerable + 3 unanswerable questions.
- [ ] Print each status and the final `Score: x/y` per suite; report real scores.

**Definition of done:** three real scores reported; every unanswerable question returns an "I don't know." style answer.

### Results — run 2026-10-17 (47 questions, `SLEEP_SECONDS=15`, exit code 0)

| Suite | Score | Failures (verbatim, unedited) |
| --- | --- | --- |
| 1 — "I Sell My Dreams" (8 answerable) | **7/8** | `EMPTY` on *"How many floors did the Havana Riviera Hotel have?"* — a transient empty Groq response; the same question re-asked afterwards returns *"The Havana Riviera Hotel had **20 floors**."* Score NOT re-run or adjusted. |
| 2 — story + unanswerable (7+4) | **10/11** | `MISS (idk)` on *"What was the name of Neruda's wife?"* → answered "i don't know." though `matilde` exists in the story. |
| 3 — IBM StoredIQ (25+3) | **26/28** | `WRONG` — expected `2 tb`, got *75 gb* (default data disk size). `WRONG` — expected `es_hosts`, got *eshosts* (the notebook's `norm()` strips underscores from the answer but keywords are compared un-normalised, so this keyword can never match — a harness quirk, not touched per AGENTS §8). |
| **Total** | **43/47** | **0 `HALLUCINATED`** — all 7 unanswerable questions returned "I don't know." ✅ |

Notebook's own recorded scores for context: 7/8, 8/11, 22/28 = 37/47 (plain-MMR `k=8`, local models — not a strict baseline).

**Comparability note (D-01):** the notebook's recorded scores (7/8, 8/11, 22/28) came from the local models on the plain-MMR `k=8` path. This build is hybrid **and** uses Jina models — two axes of difference. Treat those numbers as context, not a target; report ours as-is.

**Risk:** ~20 minutes wall time from the 15-second rate-limit sleeps. Worse-than-notebook scores imply a fidelity deviation first — check §4 and `DEVIATIONS.md` before touching logic.

---

## M6 — Frontend: scaffold & design system ⬜

- [ ] `npm create vite@latest frontend -- --template react`; `npm install tailwindcss @tailwindcss/vite`.
- [ ] Enable the Tailwind plugin in `vite.config.js` alongside `@vitejs/plugin-react`.
- [ ] `src/index.css` — Tailwind v4 `@theme` tokens: `--color-ink: #293132`, `--color-rose: #CD5D67`, `--color-sand: #D6D5C9`, `--font-sans: "Josefin Sans", sans-serif`.
- [ ] `index.html` — Josefin Sans `<link>` (weights 300;400;600;700).
- [ ] Layout shell: Ink header "Ask your PDFs", Ink left panel, Sand main area; stacks on mobile widths.
- [ ] `frontend/.env` with `VITE_API_URL=http://127.0.0.1:8000`.

**Definition of done:** `npm run dev` renders the palette-correct empty shell at `http://localhost:5173`.

---

## M7 — Frontend: features & states ⬜

- [ ] Upload panel — file picker + drag and drop; button disabled while uploading; "Indexing…" spinner; success message with file name, pages and chunks.
- [ ] File list — `GET /files` on load and after each upload; checkboxes for filtering; empty-state hint "Upload a PDF to get started".
- [ ] Ask form — question input, Enter to submit, button disabled when empty or in flight; `k` input default 5, range 1–10.
- [ ] Selected files sent in `files`; field omitted when nothing is selected.
- [ ] Answer card + source cards (file · page · snippet).
- [ ] States — "Thinking…" spinner with previous answer cleared; readable errors for 400/404; "Cannot reach the server. Is the API running?" on network failure.
- [ ] Errors use a Rose-bordered box; success uses Ink text on a Sand card with a Rose left border.
- [ ] Accessibility — visible labels or `aria-label`s, real `<button>` elements, Rose focus ring.
- [ ] Responsive check at desktop and phone widths.

**Definition of done:** the PRD §8.7 behavior/state table is satisfied.

---

## M8 — End-to-end acceptance ✅

*Live browser + real API walk-through, 2026-10-17 (agent-browser; uvicorn `:8000` + vite `:5173`). Both servers stopped afterwards, ports 8000/5173 confirmed free, `chroma_db/` and `uploads/` never cleared.*

- [x] Upload a PDF from the web page; it appears in the file list. — `lekl101.pdf · 11 pages · 34 chunks`; re-uploaded twice, no duplication, list showed each file once.
- [x] A question returns a grounded answer with sources, displayed in the UI. — `What is the significance of the title 'I Sell My Dreams'?` → answer card + 5 sources (`file · p. N · 200-char snippet`); `Thinking…` indicator and disabled button captured during the request.
- [x] An unrelated question returns "I don't know." — proven in M5 (all 7 unanswerable questions across suites 2–3 returned "I don't know."; 0 `HALLUCINATED`).
- [x] Selecting specific files changes which sources are returned. — IBM-only filter → all 5 sources from the IBM guide; story-only filter → all 5 from `lekl101.pdf`; no selection ⇒ request body omits `files` ⇒ searches all.
- [x] Non-PDF upload, unknown file and API-down each show a readable message. — non-PDF → HTTP 400 showing the API's own `detail` in a rose-bordered box; API-down → exact text `Cannot reach the server. Is the API running?`, and the UI recovered after restart. (Unknown-file 404 is unreachable through the UI by design; it was verified against the API in M3.)
- [x] UI uses only `#293132`, `#CD5D67`, `#D6D5C9` plus the Josefin Sans font. — all 72 rendered elements report `Josefin Sans`; computed colors = palette + alpha variants only.
- [x] Usable on a phone-sized screen. — at 375 px: `scrollWidth 375` (no horizontal overflow), left panel stacks above the main area.
- [x] Fresh setup via PRD §16 completes in under five minutes (excluding model download). — `pip install -r requirements.txt` ≈ 3–4 min (torch CPU wheel dominates); both runtime commands start in seconds (`VITE v8.3.4 ready in 1167 ms`).
- [x] `DEVIATIONS.md` is complete and final. — signed off at M4; D-01 statuses updated to "Implemented — verified in code"; evaluation results recorded here.
- [ ] Commit the work. — **owner's call**: the index is staged for review and the owner runs the final commit (their explicit decision).

**Definition of done:** every PRD §15 success criterion passes — ✅ met.

**Known cosmetic findings, deliberately not fixed:** markdown emphasis (`**…**`) prints literally in answers — the PRD requires no markdown rendering and adding a renderer would be a feature outside the PRD (§9); the upload status box persists until the next upload (no PRD rule requires dismissal).

**Environment noise (not the app):** an external process on this machine polls `GET /health` and `GET /` on port 8000 and gets 404 — correct behaviour, since neither is a PRD endpoint.

---

## Out of scope (do not build)

Per AGENTS §9 and the PRD non-goals: no auth, no streaming, no `.txt`/`.docx`, no chat memory, no routing or state library, no extra retrievers, no prompt changes, no parameter tuning, no Kaggle paths or secrets client.
