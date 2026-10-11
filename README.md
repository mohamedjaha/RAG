# RAG Notebook Documentation

A simple guide to a notebook that answers questions about PDF files using Retrieval-Augmented Generation (RAG). Made for educational purposes.

## 1. What does this notebook do?

The notebook builds a small **question-answering system** over your own documents. Instead of asking an AI model to answer from memory, it first **finds the most relevant parts of your PDFs** and then gives them to the model as context. This makes answers more accurate and grounded in your files.

**The pipeline in one line:**

PDF → split into chunks → turn chunks into embeddings → store in ChromaDB → retrieve the best chunks for a question → send them to the LLM → get an answer

The notebook also includes **test suites** that automatically check how well the system answers questions (see Step 9).

## 2. Tools and libraries used

| Library | Purpose |
| --- | --- |
| `langchain` / `langchain-community` | Framework that connects all the pieces together |
| `langchain-groq` | Connects to the Groq API to run the chat model |
| `pypdf` | Reads and extracts text from PDF files |
| `fastembed` | Creates embeddings (numbers that represent the meaning of text) |
| `chromadb` / `langchain-chroma` | Vector database that stores and searches embeddings |
| `sentence-transformers` | Provides the cross-encoder reranker (used only by the optional `Retriever` class) |

**Models used:**

- Chat model: `openai/gpt-oss-20b` (through Groq)
- Embedding model: `thenlper/gte-large`
- Reranker (optional, in the `Retriever` class): `cross-encoder/ms-marco-MiniLM-L-6-v2`

## 3. Before you run it

1. Run the notebook on **Kaggle** (it uses `kaggle_secrets`).
2. Add a secret named `GROQ_API_KEY` with your Groq API key.
3. Upload your PDF(s) as a Kaggle dataset and update the `file_links` paths.
4. The first run downloads the embedding model from the Hugging Face Hub. You may see a warning about unauthenticated requests; setting an `HF_TOKEN` is optional but gives faster downloads.

## 4. Step-by-step walkthrough

### Step 1: Install and import packages

Installs the required libraries with `pip` and checks that the imports work. The message *"All packages installed successfully!"* confirms it. A `DeprecationWarning` about `langchain-community` appears; it is harmless for this notebook.

### Step 2: The `Models` class

Loads the API key from Kaggle secrets and creates two objects:

- `chat_llm`: the language model that writes answers (`temperature=0.2`, `max_tokens=4000`).
- `embedding_model`: the model that converts text into vectors.

### Step 3: The `File_Loader` class

Takes a list of file paths and loads the ones that are allowed.

- `get_file_type()`: checks the file extension.
- `load_files()`: labels each file with its type.
- `load_allowed_files()`: reads PDFs with `PyPDFLoader` and returns the pages as documents.

Currently only `pdf` is allowed, so `.txt` and `.docx` paths in the list are skipped. In the example run, the first PDF loaded as **11 page documents**.

### Step 4: The `Chunker` class

Long documents are cut into smaller pieces so the search can find precise parts.

- Uses `RecursiveCharacterTextSplitter`.
- Default `chunk_size=1000` characters per chunk.
- Default `chunk_overlap=150` characters shared between neighboring chunks, so ideas are not cut in half.
- In the example run (one PDF, default settings), this produced **27 chunks**.

### Step 5: The `Embedding` class

Connects everything so far:

1. Creates the models.
2. Loads and splits the files into chunks. Note that this class passes its own defaults, **`chunk_size=800`** and `chunk_overlap=150`, which override the `Chunker` defaults.
3. Converts chunks into embeddings and saves them in **ChromaDB** (folder `./chroma_db`).

Helper methods: `get_db()` returns the vector database and `get_chunks()` returns the chunks.

### Step 6: The `Retriever` class (optional hybrid search)

A standalone, more advanced retriever. It is **defined but not used** by the final RAG chain. It combines three techniques:

1. **Semantic search (MMR):** finds chunks by meaning. MMR (Maximal Marginal Relevance) picks chunks that are relevant *and* different from each other. Up to 20 candidates are fetched.
2. **Keyword search (BM25):** finds chunks that contain the same words as the question. Up to 20 candidates are fetched.
3. **Reciprocal Rank Fusion (RRF):** merges the two ranked lists into one, rewarding chunks that rank well in both.

Finally, a **cross-encoder reranker** reads each (question, chunk) pair together and scores it more precisely. The top `k` chunks (default 5) are returned.

To use it you would need `rank_bm25` and `sentence-transformers` installed, since the `pip` cell does not install them.

### Step 7: RAG classes

- **`RAG_Retrieval`**: builds the vector database once and provides a plain **MMR retriever** (`get_retriever(k=5)`).
- **`RAG_Generation`**: builds the final chain (default `k=8` chunks):
  1. The retriever finds relevant chunks (the *context*).
  2. The prompt template combines the context and the question.
  3. The LLM writes the answer.
  4. `StrOutputParser` returns plain text.

The prompt has three rules: say exactly *"I don't know."* when the context is not enough, share any helpful information you have, and try to use all of the context.

### Step 8: Run it

The final `file_links` list now contains two PDFs (the short story and an IBM StoredIQ deployment guide), plus the unsupported `.txt` and `.docx` paths, which are ignored.

```python
rag_retrieval = RAG_Retrieval(file_links)
rag = RAG_Generation(rag_retrieval)
print(rag.response("What is the significance of the title 'I Sell My Dreams'?"))
```

The model explained that the title works on two levels: literally, the character trades her dreams for a living, and metaphorically, it points to dreams, hope, and imagination being turned into something that can be sold.

### Step 9: Automatic tests

Three test cells check the system with question lists. Each test has keywords that a correct answer should contain. Answers are normalized first (lowercase, no accents, no punctuation tricks), then checked. Each question gets one status:

| Status | Meaning |
| --- | --- |
| `PASS` | The answer contains an expected keyword (or, for unanswerable questions, the model correctly said it didn't know) |
| `MISS (idk)` | The question is answerable, but the model said it didn't know |
| `WRONG` | The model answered, but without the expected keyword |
| `HALLUCINATED` | The question is unanswerable, but the model gave an answer anyway |
| `EMPTY` | The model returned nothing |

The tests wait 15 seconds between questions (`time.sleep(15)`) to avoid hitting the Groq rate limit.

**Results in the example run:**

| Test set | Document | Score |
| --- | --- | --- |
| Test 1 | Short story (plot details) | 7 / 8 |
| Test 2 | Short story (details + unanswerable questions) | 8 / 11 |
| Test 3 | IBM StoredIQ guide (technical facts + unanswerable questions) | 22 / 28 |

Notable failures:

- **Hallucinations:** the model invented answers for "What is Neruda's favorite color?" and "What was Frau Frieda's real name?", which the story never states.
- **Missed answers:** for some questions the model said "I don't know." even though the answer existed, such as the finger the snake ring was worn on.
- **Technical details:** exact numbers and ports (disk size, storage per TB, a port number) were sometimes wrong or missed. Retrieving more precise chunks, or using the hybrid `Retriever`, may help.

Note that the keyword check is simple: a `WRONG` result can occasionally be a correct answer phrased differently.

## 5. Key concepts for learners

- **Embedding:** a list of numbers that captures the meaning of text. Similar meanings give similar numbers.
- **Vector database:** stores embeddings and quickly finds the closest ones to a question.
- **Chunking:** splitting text into small pieces so retrieval is precise.
- **Retriever:** the component that picks the best chunks for a question.
- **MMR:** a search method that balances relevance with variety.
- **BM25:** a classic keyword-matching search. It is good at exact terms, such as port numbers or names.
- **Hybrid search:** combining semantic and keyword search to get the strengths of both.
- **RRF (Reciprocal Rank Fusion):** a simple way to merge several ranked lists into one.
- **Reranker (cross-encoder):** a model that re-scores a short list of results by reading the question and each chunk together.
- **Hallucination:** when the model confidently states something that is not in the documents.
- **RAG:** retrieval first, then generation, so the model answers using your documents.

## 6. Class overview

| Class | Responsibility |
| --- | --- |
| `Models` | Creates the chat model and embedding model |
| `File_Loader` | Reads allowed files (PDF) |
| `Chunker` | Splits documents into chunks |
| `Embedding` | Embeds chunks and stores them in ChromaDB |
| `Retriever` | Optional hybrid search (MMR + BM25 + RRF + reranker); not used in the final chain |
| `RAG_Retrieval` | Builds the database and gives an MMR retriever |
| `RAG_Generation` | Combines retrieval, prompt, and LLM to answer |


