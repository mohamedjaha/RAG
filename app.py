"""FastAPI backend for the simple RAG app (milestones M2 + M3).

Single-file port of ``docs/notebook.ipynb`` - the source of truth for all RAG
logic - plus the FastAPI layer required by the PRD. Class names, method names
and parameter values are kept identical to the notebook so both files can be
compared side by side. Every difference is recorded in ``DEVIATIONS.md``:
D-01 (owner-directed) replaces the local embedding model and cross-encoder
with the hosted Jina AI embeddings and rerank APIs.
"""

import os

# ---------------------------------------------------------------------------
# Defensive startup: drop TLS environment variables whose paths do not exist.
# This machine has a user-level SSL_CERT_FILE pointing into a deleted venv,
# which makes httpx/requests raise FileNotFoundError before sending anything
# (DEVIATIONS.md section 3, item 12). Never fail because of it.
# ---------------------------------------------------------------------------
for _name in ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
    _value = os.environ.get(_name)
    if _value and not os.path.exists(_value):
        os.environ.pop(_name, None)
        print(f"[startup] WARNING: removed {_name}={_value} (path does not exist)", flush=True)


# ---------------------------------------------------------------------------
# Minimal .env loader (no extra dependency): KEY=VALUE lines, blank lines and
# '#' comments ignored, surrounding double/single quotes stripped from values,
# variables already present in os.environ are never overwritten.
# ---------------------------------------------------------------------------
def _load_dotenv(path):
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Quote-strip the two secrets even when they came from the shell: a quoted key
# is sent literally and the API answers HTTP 401.
for _secret in ("GROQ_API_KEY", "JINA_API_KEY"):
    _value = os.environ.get(_secret)
    if _value and len(_value) >= 2 and _value[0] == _value[-1] and _value[0] in "\"'":
        os.environ[_secret] = _value[1:-1]

_MISSING = [name for name in ("GROQ_API_KEY", "JINA_API_KEY") if not os.environ.get(name)]
if _MISSING:
    raise RuntimeError(
        "Missing required environment variable(s): "
        + ", ".join(_MISSING)
        + '. Set them in the shell or in the project ".env" file before starting the app.'
    )

import re
import shutil
import time

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration (PRD section 10)
# ---------------------------------------------------------------------------
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")
CHROMA_DIR = os.environ.get("CHROMA_DIR", "./chroma_db")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173")

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Deviation D-01: hosted Jina AI embeddings and rerank (owner-directed).
# Implementation reference: DEVIATIONS.md "New deviation D-01" / D-01.3.
# Rate limits are designed for the conservative free tier (100 RPM / 100K TPM).
# ---------------------------------------------------------------------------
JINA_EMBEDDINGS_URL = "https://api.jina.ai/v1/embeddings"
JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"
JINA_EMBED_BATCH = 64  # D-01.3: batch 64-128 texts per request


def _jina_post(url, payload, what):
    """POST to a Jina AI endpoint with the D-01.3 error mapping and retries.

    401 -> "Invalid Jina API key" (no retry); 403 -> "Jina free tokens exhausted"
    (no retry); 400 -> client error (no retry); 429 -> exponential backoff with
    1s/2s/4s delays; 500/503/504 -> retry twice, then surface
    "<what> service unavailable".
    """
    headers = {
        "Authorization": "Bearer " + os.environ["JINA_API_KEY"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    backoff = (1, 2, 4)
    rate_tries = 0
    server_tries = 0

    while True:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        status = response.status_code

        if status == 200:
            return response.json()
        if status == 401:
            raise RuntimeError(f"Invalid Jina API key (HTTP 401 from the {what} endpoint).")
        if status == 403:
            raise RuntimeError(f"Jina free tokens exhausted (HTTP 403 from the {what} endpoint).")
        if status == 400:
            raise RuntimeError(f"Jina {what} client error (HTTP 400): {response.text[:300]}")
        if status == 429:
            if rate_tries >= len(backoff):
                raise RuntimeError(f"Jina {what} rate limit (HTTP 429) persisted after 3 retries.")
            time.sleep(backoff[rate_tries])
            rate_tries += 1
            continue
        if status in (500, 503, 504):
            if server_tries >= 2:
                raise RuntimeError(
                    f"Jina {what} service unavailable (HTTP {status} after 2 retries)."
                )
            time.sleep(backoff[server_tries])
            server_tries += 1
            continue
        raise RuntimeError(f"Jina {what} failed (HTTP {status}): {response.text[:300]}")


class JinaEmbeddings(Embeddings):
    """Thin LangChain `Embeddings` adapter for POST /v1/embeddings (D-01).

    `embed_documents` sends task="retrieval.passage", `embed_query` sends
    task="retrieval.query"; responses are mapped by `index`, never by array
    position (D-01.3). Chroma and MMR therefore work unchanged.
    """

    def __init__(self, model="jina-embeddings-v5-text-small", batch_size=JINA_EMBED_BATCH):
        self.model = model
        self.batch_size = batch_size

    def _embed_batch(self, texts, task):
        payload = {
            "model": self.model,
            "input": list(texts),
            "task": task,
            # their defaults conflict between official sources -> set explicitly (D-01.3)
            "normalized": True,
            "truncate": True,
        }
        body = _jina_post(JINA_EMBEDDINGS_URL, payload, "embedding")
        data = body.get("data") or []
        by_index = {int(item["index"]): item["embedding"] for item in data}
        if set(by_index) != set(range(len(texts))):
            raise RuntimeError(
                f"Jina embeddings returned {len(by_index)} vectors "
                f"for {len(texts)} input texts."
            )
        return [by_index[i] for i in range(len(texts))]

    def embed_documents(self, texts):
        vectors = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(
                self._embed_batch(texts[start:start + self.batch_size], "retrieval.passage")
            )
        return vectors

    def embed_query(self, text):
        return self._embed_batch([text], "retrieval.query")[0]


class JinaReranker:
    """D-01 replacement for `CrossEncoder.predict`.

    The Jina rerank API takes ONE `query` plus a `documents` array (it does not
    accept (query, doc) pairs); `results` arrives sorted by relevance_score
    descending and `index` maps back into the input array. Scores are returned
    in input order so `Retriever.invoke` keeps the notebook's zip/sort shape.
    """

    def __init__(self, model="jina-reranker-v3.5"):
        self.model = model

    def predict(self, query, texts):
        payload = {
            "query": query,
            "model": self.model,
            "documents": list(texts),
            "return_documents": False,
        }
        body = _jina_post(JINA_RERANK_URL, payload, "rerank")
        scores = [0.0] * len(texts)
        for item in body.get("results") or []:
            index = int(item["index"])
            if 0 <= index < len(texts):
                scores[index] = float(item["relevance_score"])
        return scores


class Models:
    def __init__(
        self,
        Chat_model="openai/gpt-oss-20b",
        embedding_model="jina-embeddings-v5-text-small"  # D-01 (notebook: "thenlper/gte-large")
    ):
        self.Chat_model = Chat_model
        self.embedding_model_name = embedding_model

        self.chat_llm = ChatGroq(
            model=self.Chat_model,
            temperature=0.2,
            max_tokens=4000,
        )

        self.embedding_model = JinaEmbeddings(
            model=self.embedding_model_name
        )


class File_Loader:
    ALLOWED_FILES = ["pdf"]

    def __init__(self, File_links):
        self.File_links = File_links

    def get_file_type(self, file_link):
        extension = os.path.splitext(file_link)[1].lower().replace(".", "")

        if extension in self.ALLOWED_FILES:
            return extension

        return "none"

    def load_files(self):
        files = []

        for file_link in self.File_links:
            file_type = self.get_file_type(file_link)

            files.append({
                "path": file_link,
                "type": file_type
            })

        return files

    def load_allowed_files(self):
        documents = []

        files = self.load_files()

        for file in files:
            if file["type"] == "pdf":
                loader = PyPDFLoader(file["path"])
                documents.extend(loader.load())

        return documents


class Chunker:
    def __init__(self, File_links, chunk_size=1000, chunk_overlap=150):

        # Chunker internally uses File_Loader
        self.file_loader = File_Loader(File_links)

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split(self):
        # Load allowed files
        documents = self.file_loader.load_allowed_files()

        # Split documents into chunks
        return self.splitter.split_documents(documents)


class Embedding:
    def __init__(
        self,
        File_links,
        embedding_model="jina-embeddings-v5-text-small",  # D-01 (notebook: "thenlper/gte-large")
        chat_model="openai/gpt-oss-20b",
        persist_directory="./chroma_db",
        chunk_size=800,
        chunk_overlap=150
    ):
        self.File_links = File_links
        self.persist_directory = persist_directory
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Use LLM class (a single shared instance for the whole app - bug B3)
        self.Models = Models(
            Chat_model=chat_model,
            embedding_model=embedding_model
        )

        # Get embedding model from LLM
        self.embedding_model = self.Models.embedding_model

        # Get chat model from LLM
        self.chat_llm = self.Models.chat_llm

        # Chunker internally uses File_Loader
        self.chunker = Chunker(
            File_links,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        # Create chunks -> happens per upload in index_file() below
        # (upload-time indexing, allowed extensions 2 and 4; fixes bug B2)
        self.chunks = []

        # Create ChromaDB on the persistent directory; the index is rebuilt at
        # upload time instead of here (AGENTS.md section 5, items 2 and 8)
        self.db = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embedding_model
        )

    def index_file(self, file_path):
        """Chunk one PDF, replace its previous chunks, embed and store them.

        PRD FR-1 / FR-3 (allowed extensions 2, 3 and 4).
        """
        source = os.path.basename(file_path)

        # Same chunking path as the notebook's __init__, for this one file;
        # Embedding passes chunk_size=800 / chunk_overlap=150 (notebook cell 11)
        self.chunker = Chunker(
            [file_path],
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        chunks = self.chunker.split()

        # Clean source name (allowed extension 3)
        for chunk in chunks:
            chunk.metadata["source"] = source

        # Replace on re-upload: drop the old chunks with this source first (FR-3)
        self.db.delete(where={"source": source})

        # Embed (Jina, retrieval.passage batches) and add to the persistent store
        self.db.add_documents(documents=chunks)

        self.chunks = chunks
        return chunks

    def get_db(self):
        return self.db

    def get_chunks(self):
        return self.chunks


class Retriever:

    def __init__(
        self,
        embedding,
        documents,
        search_type="mmr",
        k=5,                  # Final number of chunks
        candidate_k=20,       # Candidates from vector search
        bm25_k=20,            # Candidates from BM25
        reranker_model="jina-reranker-v3.5",  # D-01 (notebook: "cross-encoder/ms-marco-MiniLM-L-6-v2")
        rrf_k=60,
        files=None            # optional file filter (allowed extension 5)
    ):
        self.db = embedding.get_db()

        self.k = k
        self.rrf_k = rrf_k

        # 1. Semantic / vector retriever (no fetch_k - notebook behaviour, conflict #3);
        #    with a file filter the same search_kwargs carry a Chroma metadata filter
        search_kwargs = {"k": candidate_k}
        if files:
            search_kwargs["filter"] = {"source": {"$in": list(files)}}

        self.retriever = self.db.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs
        )

        # 2. BM25 retriever (same optional file filter on the corpus - allowed extension 5)
        bm25_documents = documents
        if files:
            wanted = set(files)
            bm25_documents = [
                doc for doc in documents
                if doc.metadata.get("source") in wanted
            ]

        self.bm25_retriever = BM25Retriever.from_documents(
            bm25_documents
        )
        self.bm25_retriever.k = bm25_k

        # 3. Reranker - hosted Jina API (D-01 replaces the local CrossEncoder)
        self.reranker = JinaReranker(model=reranker_model)

    def invoke(self, query):

        # Vector search
        semantic_docs = self.retriever.invoke(query)

        # Keyword search
        bm25_docs = self.bm25_retriever.invoke(query)

        # RRF fusion: keep all unique candidates
        candidates = self._rrf(
            semantic_docs,
            bm25_docs
        )

        if not candidates:
            return []

        # Reranker scores the query against each candidate's text
        # (D-01: the Jina API takes ONE query + a documents array,
        #  not (query, doc) pairs like CrossEncoder.predict did)
        scores = self.reranker.predict(
            query,
            [doc.page_content for doc in candidates]
        )

        # Sort by reranker score, highest first
        ranked_docs = sorted(
            zip(candidates, scores),
            key=lambda item: item[1],
            reverse=True
        )

        # Return only the final K documents
        return [
            doc for doc, score in ranked_docs[:self.k]
        ]

    def _rrf(
        self,
        semantic_docs,
        bm25_docs
    ):
        scores = {}
        documents = {}

        # Semantic results
        for rank, doc in enumerate(semantic_docs, start=1):
            key = self._document_key(doc)

            scores[key] = scores.get(key, 0) + (
                1 / (self.rrf_k + rank)
            )
            documents[key] = doc

        # BM25 results
        for rank, doc in enumerate(bm25_docs, start=1):
            key = self._document_key(doc)

            scores[key] = scores.get(key, 0) + (
                1 / (self.rrf_k + rank)
            )
            documents[key] = doc

        # Return every unique candidate in RRF order
        ranked_keys = sorted(
            scores,
            key=scores.get,
            reverse=True
        )

        return [
            documents[key]
            for key in ranked_keys
        ]

    def _document_key(self, doc):
        return (
            doc.page_content,
            str(sorted(doc.metadata.items()))
        )


class RAG_Retrieval:

    def __init__(self, embedding):
        # VectorDB is created ONCE (in the app it is built at startup;
        # upload-time indexing, allowed extension 2)
        self.embedding = embedding

    def get_retriever(self, k=5):
        retriever = self.embedding.get_db().as_retriever(
            search_type="mmr",
            search_kwargs={"k": k}
        )

        return retriever


class RAG_Generation:

    def __init__(
        self,
        retrieval,
        retriever,
        k=5,  # conflict #7: the notebook default here is 8; the app uses 5
        template="""
You are an AI assistant that answers questions using the provided context.

Rules:

- If the context does not contain enough information to answer the question,
  say exactly: "I don't know."
- if you have any information that can help say it 
- try to use all context to answer 

Context:
{context}

Question:
{query}

Answer:
"""
    ):

        self.retrieval = retrieval
        self.k = k

        # One shared Models instance for the whole app (notebook bug B3)
        self.models = self.retrieval.embedding.Models

        self.prompt = ChatPromptTemplate.from_template(template)

        # Conflict #1: the hybrid Retriever (MMR + BM25 + RRF + rerank) that the
        # caller builds for this request - NOT the plain-MMR get_retriever() path.
        self.retriever = retriever

        # Documents of the last response(), so /ask can build `sources` from the
        # exact same objects the chain sent to the LLM (conflict #6)
        self.last_docs = []

        self.chain = (
            {
                # the context stays the RAW list of Document objects (conflict #6)
                "context": RunnableLambda(self._retrieve),
                "query": RunnablePassthrough()
            }
            | self.prompt
            | self.models.chat_llm
            | StrOutputParser()
        )

    def _retrieve(self, query):
        self.last_docs = self.retriever.invoke(query)
        return self.last_docs

    def response(self, query):
        return self.chain.invoke(query)


# ---------------------------------------------------------------------------
# Singletons, built once at startup (PRD section 12: models loaded once)
# ---------------------------------------------------------------------------
EMBEDDING = Embedding(
    File_links=[],
    persist_directory=CHROMA_DIR
)
RETRIEVAL = RAG_Retrieval(EMBEDDING)

# ---------------------------------------------------------------------------
# FastAPI layer (PRD sections 5.1, 7 and 12; endpoints are synchronous so
# FastAPI runs them in a thread pool)
# ---------------------------------------------------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    files: list[str] | None = None
    k: int | None = None


def indexed_files():
    """Sorted unique source names, read from the persistent index (FR-4)."""
    data = EMBEDDING.get_db().get(include=["metadatas"])
    names = set()
    for meta in data.get("metadatas") or []:
        if isinstance(meta, dict) and meta.get("source"):
            names.add(meta["source"])
    return sorted(names)


def stored_chunks():
    """BM25 corpus: every chunk stored in Chroma (allowed extension 6)."""
    data = EMBEDDING.get_db().get(include=["documents", "metadatas"])
    contents = data.get("documents") or []
    metadatas = data.get("metadatas") or []
    return [
        Document(page_content=content, metadata=meta or {})
        for content, meta in zip(contents, metadatas)
        if content
    ]


@app.post("/upload")
def upload(file: UploadFile = File(...)):
    name = os.path.basename(file.filename or "")

    if File_Loader([name]).get_file_type(name) == "none":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type for '{name}': only these extensions "
                f"are accepted: {File_Loader.ALLOWED_FILES}."
            ),
        )

    # FR-1: save, load with PyPDF, chunk, embed, store
    path = os.path.join(UPLOAD_DIR, name)
    with open(path, "wb") as handle:
        shutil.copyfileobj(file.file, handle)

    documents = File_Loader([path]).load_allowed_files()
    if not documents:
        raise HTTPException(
            status_code=400,
            detail=f"'{name}' could not be read as a PDF.",
        )

    # FR-2: reject PDFs without a text layer
    total_chars = sum(len(re.sub(r"\s", "", doc.page_content)) for doc in documents)
    if total_chars == 0:
        raise HTTPException(
            status_code=400,
            detail=f"'{name}' contains no extractable text (scanned PDF without a text layer).",
        )

    chunks = EMBEDDING.index_file(path)

    return {
        "file": name,
        "pages": len(documents),  # PyPDFLoader default mode="page": one Document per page
        "chunks": len(chunks),
    }


@app.get("/files")
def list_files():
    return indexed_files()


@app.post("/ask")
def ask(request: AskRequest):
    question = (request.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="'question' must not be empty.")

    k = request.k if request.k is not None else 5  # default k = 5 (conflict #7)
    if k < 1:
        raise HTTPException(status_code=400, detail="'k' must be a positive integer.")

    # FR-6: nothing indexed -> 404
    indexed = indexed_files()
    if not indexed:
        raise HTTPException(
            status_code=404,
            detail="No PDF is indexed yet. Upload a PDF first.",
        )

    # FR-6: unknown file name -> 404
    files = request.files or None  # empty list means "search all PDFs"
    if files:
        unknown = sorted({name for name in files if name not in set(indexed)})
        if unknown:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Unknown file(s): {', '.join(unknown)}. "
                    f"Indexed files: {', '.join(indexed)}."
                ),
            )

    # Conflict #1: the hybrid Retriever (MMR + BM25 + RRF + Jina rerank) - NOT
    # the plain-MMR RAG_Retrieval path. BM25 is rebuilt from Chroma per request.
    retriever = Retriever(EMBEDDING, stored_chunks(), k=k, files=files)
    rag = RAG_Generation(RETRIEVAL, retriever=retriever, k=k)

    answer = rag.response(question)

    # Sources from the SAME reranked chunks sent to the LLM (allowed extension 7);
    # PyPDFLoader pages are 0-based -> displayed 1-based
    sources = [
        {
            "file": doc.metadata.get("source", ""),
            "page": int(doc.metadata.get("page") or 0) + 1,
            "snippet": doc.page_content[:200],
        }
        for doc in rag.last_docs
    ]

    return {"answer": answer, "sources": sources}
