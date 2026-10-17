# agent.md – Instructions for the AI coding agent

This project turns **`notebook/notebook.ipynb`** (the "RAG notebook") into a FastAPI + React application.
The notebook is the **source of truth** for all RAG logic. You must read it, reuse it and stay faithful to it.

---

## 1. Source-of-truth hierarchy

When two documents disagree, the higher one wins.

| Priority | Document | Governs |
| --- | --- | --- |
| 1 | `notebook/notebook.ipynb` | Everything it defines: models, loading, chunking, embedding, retrieval, fusion, reranking, prompt, generation, and the evaluation questions. |
| 2 | `PRD_Simple_RAG_API.md` | Everything the notebook is silent on: API endpoints, error codes, file upload handling, persistence rules, the React/Tailwind UI, configuration, setup. |
| 3 | `agent.md` (this file) | How you work: process, checks and reporting. |

If the notebook and the PRD conflict on RAG behavior, **follow the notebook**, do not guess, and record the conflict in `DEVIATIONS.md` (see section 7).

---

## 2. Mandatory first step: read the notebook

Before writing any code, read the whole notebook. Do not work from memory, from this file's summary or from the PRD's description of it.

Then write a short mapping (in your reply or in `DEVIATIONS.md`) from each notebook class to the code you will write. If you cannot find something in the notebook, say so; never invent it.

---

## 3. Fidelity rules

1. **Reuse the notebook's classes and logic.** Keep the class names and method names (`Models`, `File_Loader`, `Chunker`, `Embedding`, `Retriever`, `RAG_Retrieval`, `RAG_Generation`, `invoke`, `_rrf`, `_document_key`, `response`) so the notebook and `app.py` can be compared side by side.
2. **Copy values verbatim.** Model names, parameters, chunk sizes, `k` values, `rrf_k`, the RRF formula and the prompt template must match the notebook character for character.
3. **Do not "improve" the RAG logic.** No new retrievers, no changed prompt wording, no extra rules, no different models, no tuned parameters, unless the PRD explicitly requires it (section 5 lists the only allowed extensions).
4. **Fidelity beats brevity.** The PRD's "about 180 lines" is a soft goal. If it conflicts with matching the notebook, match the notebook.
5. **Import paths may change; behavior may not.** If a LangChain import path is deprecated or moved in the installed version, adapt the import only and note it in `DEVIATIONS.md`.
6. **Never silently fix notebook bugs.** Fix only what blocks the app, keep the fix minimal, and log it (section 6).

---

## 4. Quick reference (verify against the notebook; the notebook wins if this is stale)

| Component | Value in the notebook |
| --- | --- |
| Chat model | `ChatGroq(model="openai/gpt-oss-20b", temperature=0.2, max_tokens=4000)` |
| Embeddings | `FastEmbedEmbeddings(model_name="thenlper/gte-large")` |
| Allowed files | `ALLOWED_FILES = ["pdf"]`, loaded with `PyPDFLoader` |
| Chunking | `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)` as used by `Embedding` (the `Chunker` default of 1000 is overridden) |
| Vector store | `Chroma`, `persist_directory="./chroma_db"` |
| Semantic search | `as_retriever(search_type="mmr", search_kwargs={"k": 20})` (no `fetch_k` is set) |
| Keyword search | `BM25Retriever.from_documents(documents)`, `k = 20` |
| Fusion | RRF, `score += 1 / (rrf_k + rank)`, `rrf_k = 60`, rank starts at 1, key = `(page_content, str(sorted(metadata.items())))` |
| Reranker | `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")`, scores `(query, doc.page_content)` pairs, sorted by score descending |
| Final chunks | `k = 5` in `Retriever` |
| Prompt | The `template` in `RAG_Generation`, used verbatim (variables `{context}` and `{query}`) |
| Chain | `{"context": retriever, "query": RunnablePassthrough()} \| prompt \| chat_llm \| StrOutputParser()` |
| Secrets | Notebook reads `GROQ_API_KEY` from Kaggle secrets and puts it in `os.environ` |

---

## 5. Allowed extensions (the only changes beyond the notebook)

These come from the PRD because the notebook has no equivalent. Implement them without altering the notebook logic around them.

1. **Kaggle secrets → environment variable.** Read `GROQ_API_KEY` from `os.environ`; refuse to start without it.
2. **Upload-time indexing.** Index one uploaded PDF at a time instead of a hard-coded `file_links` list. Reuse `File_Loader` → `Chunker`/splitter → Chroma.
3. **Clean source name.** Set each chunk's `metadata["source"]` to the sanitized file name (`os.path.basename`).
4. **Replace on re-upload.** Delete the old chunks with the same `source` before adding the new ones.
5. **File filter.** Optional `files` filter on both semantic search (Chroma metadata filter) and BM25 (filter the chunk list before building BM25).
6. **BM25 corpus from storage.** Build BM25 from the chunks stored in Chroma, since the app no longer holds them in memory.
7. **Sources in the response.** Return `file`, `page` and a 200-character `snippet` from the same reranked chunks that were sent to the LLM. Convert `page` to 1-based for display, because `PyPDFLoader` pages are 0-based.
8. **Persist and reload.** Reuse the persistent Chroma directory across restarts.
9. **FastAPI layer, CORS, errors and the whole React/Tailwind UI** exactly as specified in the PRD.

Anything not on this list is a deviation. Do not do it without asking.

---

## 6. Known differences and notebook issues (resolve exactly as written here)

The notebook and the PRD do not fully agree. Handle each point as follows and list each one in `DEVIATIONS.md`.

| # | What the notebook does | What the PRD says | What you do |
| --- | --- | --- | --- |
| 1 | The `Retriever` class implements the full hybrid pipeline (MMR + BM25 + RRF + cross-encoder). But the final `RAG_Generation` chain actually uses `RAG_Retrieval.get_retriever()`, which is **plain MMR only**, `k=8`. | The pipeline must be hybrid. | Wire the app to `Retriever.invoke()` (it is notebook code and matches the PRD). Do not use the plain-MMR path. |
| 2 | Prompt has three rules: say exactly `"I don't know."` if the context is insufficient; "if you have any information that can help say it"; "try to use all context". | "Strict rules: use only the context, do not invent facts." | Use the notebook prompt **verbatim**. Do not add the PRD's extra rules. Ask the owner if stricter wording is wanted. |
| 3 | MMR is called with `k=20` and **no `fetch_k`** (the library default applies). | `fetch_k=40`. | Follow the notebook: do not pass `fetch_k`. |
| 4 | `Embedding.get_Models()` returns `self.chat_Models`, an attribute that does not exist (bug). | Not mentioned. | Do not copy the bug. Return `self.chat_llm` or drop the method, and log it. |
| 5 | `Embedding.__init__` rebuilds the Chroma index from all files every time it is created, which duplicates chunks when re-run on a persistent directory. | Indexing at upload time; no duplicates. | Covered by allowed extensions 2 and 4. |
| 6 | `context` is the raw list of `Document` objects passed into the prompt. | Not specified. | Keep the same behavior for the LLM input unless it breaks. Build the `sources` list separately from the same documents. |
| 7 | `Retriever` has `k=5` while `RAG_Generation` has `k=8`. | Default `k=5`. | Use `k=5` as the default (matches `Retriever`). The API's optional `k` overrides it. |
| 8 | Packages installed: langchain, langchain-community, langchain-groq, pypdf, fastembed, chromadb, langchain-chroma. `rank_bm25` and `sentence-transformers` are imported but not installed in the notebook (Kaggle preinstalls them). | `requirements.txt` includes them. | Keep them in `requirements.txt`. |

---

## 7. Process you must follow

1. Read the notebook (section 2) and the PRD.
2. Produce the mapping and the list of conflicts, then **start with the backend** (`app.py`), then the frontend.
3. Create `DEVIATIONS.md` listing every place where the code differs from the notebook, with the reason (PRD requirement, bug fix or import change). An empty file means "zero deviations"; it must exist.
4. After writing `app.py`, run a **fidelity check**: for every row of section 4, find the matching line in `app.py` and confirm the value is identical to the notebook. Report the result as a short table.
5. Run the **evaluation** (section 8).
6. Only then build the React UI, following the PRD's UI section (palette `#293132`, `#CD5D67`, `#D6D5C9`, font Josefin Sans, Tailwind CSS).

If something is unclear or missing, **stop and ask** instead of choosing silently.

---

## 8. Evaluation: the notebook's own tests are the acceptance tests

The notebook ends with three test suites. Reuse them as they are (read the questions and expected keywords from the notebook; do not rewrite them).

- Suite 1 – the story "I Sell My Dreams" (answerable questions).
- Suite 2 – the same story, answerable and unanswerable questions.
- Suite 3 – the IBM StoredIQ deployment guide (answerable and unanswerable questions).

Reuse the notebook's helpers exactly: the `norm()` function, the `IDK` phrase list and the status logic (`PASS`, `MISS (idk)`, `WRONG`, `HALLUCINATED`, `EMPTY`).

Port them to `tests/test_notebook_suites.py` so they call the running API:

1. Upload the test PDFs (`lekl101.pdf` and the IBM StoredIQ guide) through `POST /upload`.
2. Send every question through `POST /ask`.
3. Keep the `time.sleep(15)` between questions (Groq rate limits) or make the delay configurable.
4. Print each status and the final `Score: x/y` per suite.

Rules for reporting results:

- Report the real scores. Never edit questions or expected keywords to make tests pass.
- Unanswerable questions must return an "I don't know" style answer. A `HALLUCINATED` status is a failure to report, not to hide.
- If the scores are worse than what the notebook produces, suspect a deviation from the notebook first (compare against section 4 and `DEVIATIONS.md`).

---

## 9. Things you must not do

- Do not rewrite the pipeline from your own knowledge of RAG best practices.
- Do not change models, chunk sizes, `k` values, `rrf_k` or the prompt to "get better results".
- Do not add features outside the PRD (auth, streaming, `.txt`/`.docx` support, chat memory).
- Do not hard-code the notebook's Kaggle paths (`/kaggle/input/...`) or the Kaggle secrets client.
- Do not claim the app matches the notebook without having run the fidelity check and the evaluation.
- Do not duplicate or edit `notebook/notebook.ipynb`. It is read-only reference material.

---

## 10. Definition of done

- [ ] `app.py` uses the notebook's class structure and the exact values from section 4.
- [ ] The hybrid `Retriever` is the retriever used by `/ask`.
- [ ] Only the allowed extensions (section 5) differ from the notebook.
- [ ] `DEVIATIONS.md` exists and lists every difference and conflict from section 6.
- [ ] The notebook's three test suites run through the API and their real scores are reported.
- [ ] The React UI follows the PRD (palette, font, states).
- [ ] Setup works with the commands in the PRD (`uvicorn app:app --reload`, `npm run dev`).