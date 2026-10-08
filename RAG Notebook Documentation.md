# RAG Notebook Documentation

A simple guide to a notebook that answers questions about a PDF using Retrieval-Augmented Generation (RAG). Made for educational purposes.

## 1. What does this notebook do?

The notebook builds a small **question-answering system** over your own documents. Instead of asking an AI model to answer from memory, it first **finds the most relevant parts of your PDF** and then gives them to the model as context. This makes answers more accurate and based on your files.

**The pipeline in one line:**

PDF → split into chunks → turn chunks into embeddings → store in ChromaDB → retrieve the best chunks for a question → send them to the LLM → get an answer

## 2. Tools and libraries used

| Library | Purpose |
| --- | --- |
| `langchain` | Framework that connects all the pieces together |
| `langchain-groq` | Connects to the Groq API to run the chat model |
| `pypdf` | Reads and extracts text from PDF files |
| `fastembed` | Creates embeddings (numbers that represent the meaning of text) |
| `chromadb` / `langchain-chroma` | Vector database that stores and searches embeddings |

**Models used:**

- Chat model: `openai/gpt-oss-20b` (through Groq)
- Embedding model: `thenlper/gte-large`

## 3. Before you run it

1. Run the notebook on **Kaggle** (it uses `kaggle_secrets`).
2. Add a secret named `GROQ_API_KEY` with your Groq API key.
3. Upload your PDF as a Kaggle dataset and update the `file_links` paths.

## 4. Step-by-step walkthrough

### Step 1: Install and import packages

Installs all required libraries with `pip` and checks that the imports work. A message *"All packages installed successfully!"* confirms it.

### Step 2: The `Models` class

Loads the API key and creates two objects:

- `chat_llm`: the language model that writes answers (`temperature=0.8`, `max_tokens=2000`).
- `embedding_model`: the model that converts text into vectors.

### Step 3: The `File_Loader` class

Takes a list of file paths and loads the ones that are allowed.

- `get_file_type()`: checks the file extension.
- `load_files()`: labels each file with its type.
- `load_allowed_files()`: reads PDFs with `PyPDFLoader` and returns the pages as documents.

Currently only `pdf` is allowed, so `.txt` and `.docx` paths in the list are skipped.

### Step 4: The `Chunker` class

Long documents are cut into smaller pieces so the search can find precise parts.

- Uses `RecursiveCharacterTextSplitter`.
- `chunk_size=1000` characters per chunk.
- `chunk_overlap=150` characters shared between neighboring chunks, so ideas are not cut in half.
- In the example run, the PDF produced **27 chunks**.

### Step 5: The `Embedding` class

Connects everything so far:

1. Creates the models.
2. Loads and splits the files into chunks.
3. Converts chunks into embeddings and saves them in **ChromaDB** (folder `./chroma_db`).

Helper methods: `get_db()` returns the vector database and `get_chunks()` returns the chunks.

### Step 6: The `Retriever` class

Searches the database for chunks related to a question. It uses **MMR (Maximal Marginal Relevance)**, which picks chunks that are relevant *and* different from each other, so you don't get four copies of the same idea. `k` is the number of chunks returned (default 4).

### Step 7: RAG classes

- **`RAG_Retrieval`**: builds the vector database once and provides an MMR retriever.
- **`RAG_Generation`**: builds the final chain:
  1. The retriever finds relevant chunks (the *context*).
  2. The prompt template combines the context and the question.
  3. The LLM writes the answer.
  4. `StrOutputParser` returns plain text.

The prompt tells the model to answer only from the context, and to say *"I don't know."* when the context is not enough.

### Step 8: Run it

```python
rag_retrieval = RAG_Retrieval(file_links)
rag = RAG_Generation(rag_retrieval, k=8)
print(rag.response("What is the significance of the title 'I Sell My Dreams'?"))
```

The model answered that the title frames the story as a marketplace for the narrator's imagination, where dreams are treated like something that can be bought and sold.

## 5. Key concepts for learners

- **Embedding:** a list of numbers that captures the meaning of text. Similar meanings give similar numbers.
- **Vector database:** stores embeddings and quickly finds the closest ones to a question.
- **Chunking:** splitting text into small pieces so retrieval is precise.
- **Retriever:** the component that picks the best chunks for a question.
- **RAG:** retrieval first, then generation, so the model answers using your documents.

## 6. Class overview

| Class | Responsibility |
| --- | --- |
| `Models` | Creates the chat model and embedding model |
| `File_Loader` | Reads allowed files (PDF) |
| `Chunker` | Splits documents into chunks |
| `Embedding` | Embeds chunks and stores them in ChromaDB |
| `Retriever` | Standalone MMR search helper |
| `RAG_Retrieval` | Builds the database and gives a retriever |
| `RAG_Generation` | Combines retrieval, prompt, and LLM to answer |

## 7. Known issues and ideas for improvement

- **Unsupported file types:** `.txt` and `.docx` are in `file_links` but are ignored. Add loaders such as `TextLoader` and `Docx2txtLoader` to support them.
- **Bug in `get_Models()`:** it returns `self.chat_Models`, which does not exist. It should return `self.Models`.
- **Unused code:** the `Retriever` class and the `query` variable are defined but never used. `RAG_Retrieval` builds its own retriever.
- **Conflicting prompt rules:** the prompt says to answer exactly "I don't know." if the context is lacking, but also says to share any helpful information. Choose one to get consistent behavior.
- **Temperature:** `0.8` makes answers more creative. For factual question answering, a lower value like `0.0` to `0.3` is usually better.
- **Repeated runs:** each run adds the same chunks to `./chroma_db` again. Delete the folder or reuse the saved database to avoid duplicates.
- **Security:** keep the API key in secrets (as done here) and never paste it into the notebook.
