/*
 * Ask your PDFs — single-file UI (PRD 8.6 allows one App.jsx).
 *
 * M7 scope: FR-10 … FR-20. The M6 layout shell and design tokens are kept;
 * this file only wires in the behavior from PRD 8.7:
 *   - UploadPanel: file picker + drag & drop -> POST /upload (field "file")
 *   - FileList:    GET /files on load and after every upload, checkboxes
 *   - AskForm:     POST /ask with question / files / k (optional fields omitted)
 *   - AnswerCard + Sources: answer and the {file, page, snippet} source cards
 *   - Message:     shared loading / error / success box (PRD 8.6)
 * API contract is taken verbatim from app.py (routes, field names, responses).
 */

import { useEffect, useRef, useState } from "react";

/* FR-19: API base URL from the Vite env, with the PRD default as fallback. */
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

/* FR-17: exact wording for an unreachable API (PRD 8.7). */
const NETWORK_ERROR = "Cannot reach the server. Is the API running?";

/*
 * FastAPI error bodies are {"detail": "..."}; 422 validation errors use an
 * array of {"loc": ..., "msg": ...} objects. Return the API's own words so
 * the error box shows exactly what the backend said (FR-17).
 */
async function readDetail(response) {
  let detail = null;
  try {
    const body = await response.json();
    detail = body ? body.detail : null;
  } catch {
    detail = null;
  }
  if (typeof detail === "string" && detail.trim() !== "") {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => (typeof item === "string" ? item : item.msg || JSON.stringify(item)))
      .join(" ");
  }
  return `Request failed (HTTP ${response.status}).`;
}

/* fetch() rejects with a TypeError when the server cannot be reached. */
function toMessage(error) {
  if (error instanceof TypeError) {
    return NETWORK_ERROR;
  }
  return (error && error.message) || String(error);
}

/* FR-16: k defaults to 5 and is clamped to the 1–10 range. */
function parseK(raw) {
  const value = Number.parseInt(raw, 10);
  if (Number.isNaN(value)) {
    return 5;
  }
  return Math.min(10, Math.max(1, value));
}

function Spinner() {
  return (
    <span
      aria-hidden="true"
      className="inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-rose"
    />
  );
}

/*
 * PRD 8.6 "Message": shared loading / error / success box.
 * - loading: inherits the ambient text color (Sand on the Ink panel, Ink on
 *   the Sand main area), so it works in both contexts.
 * - error:   Rose-bordered box with Ink text (PRD 8.2).
 * - success: Ink text on a Sand card with a Rose left border (PRD 8.2).
 */
function Message({ kind, children }) {
  if (kind === "error") {
    return (
      <p
        role="alert"
        className="rounded-lg border border-rose bg-sand px-4 py-3 text-sm font-normal text-ink"
      >
        {children}
      </p>
    );
  }
  if (kind === "success") {
    return (
      <p className="rounded-lg border-l-4 border-rose bg-sand px-4 py-3 text-sm font-normal text-ink">
        {children}
      </p>
    );
  }
  return (
    <p className="flex items-center gap-2 text-sm font-light">
      <Spinner />
      <span>{children}</span>
    </p>
  );
}

function Header() {
  return (
    <header className="bg-ink px-6 py-5 text-sand md:px-8">
      <h1 className="text-2xl font-bold md:text-3xl">Ask your PDFs</h1>
      <p className="mt-1 text-sm font-light md:text-base">
        Upload your PDFs, ask a question, get a grounded answer with its sources.
      </p>
    </header>
  );
}

/* FR-11: file picker button AND drag-and-drop zone, both posting /upload. */
function UploadPanel({ uploading, status, onFile }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    if (uploading) {
      return;
    }
    const file = event.dataTransfer.files && event.dataTransfer.files[0];
    if (file) {
      onFile(file);
    }
  }

  return (
    <section aria-labelledby="upload-heading" className="space-y-3">
      <h2 id="upload-heading" className="text-lg font-semibold">
        Upload PDF
      </h2>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!uploading) {
            setDragging(true);
          }
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`rounded-xl border bg-sand/60 px-4 py-6 text-center ${
          dragging ? "border-rose" : "border-ink/20"
        }`}
      >
        <p className="text-sm font-light text-ink">
          Drag &amp; drop a PDF here, or use the button below.
        </p>
        <input
          ref={inputRef}
          id="pdf-file"
          type="file"
          accept="application/pdf,.pdf"
          aria-label="Choose a PDF file"
          className="sr-only"
          disabled={uploading}
          onChange={(event) => {
            const file = event.target.files && event.target.files[0];
            if (file) {
              onFile(file);
            }
            /* Allow re-selecting the same file (re-upload replaces chunks). */
            event.target.value = "";
          }}
        />
        <button
          type="button"
          disabled={uploading}
          onClick={() => inputRef.current && inputRef.current.click()}
          className="mt-4 w-full cursor-pointer rounded-lg bg-rose px-4 py-2 font-semibold text-ink transition-colors hover:bg-rose/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose disabled:cursor-not-allowed disabled:opacity-50"
        >
          {uploading ? "Indexing…" : "Upload PDF"}
        </button>
      </div>
      <div aria-live="polite" className="space-y-3">
        {status ? <Message kind={status.kind}>{status.text}</Message> : null}
      </div>
    </section>
  );
}

/* FR-12 / FR-18: GET /files rendered as checkboxes, or the empty-state hint. */
function FileList({ status, error, files, selected, onToggle }) {
  const showHint = status === "ready" && files.length > 0;
  return (
    <section aria-labelledby="files-heading" className="space-y-3">
      <h2 id="files-heading" className="text-lg font-semibold">
        Indexed files
      </h2>
      <div aria-live="polite" className="space-y-3">
        {status === "loading" ? <Message kind="loading">Loading files…</Message> : null}
        {status === "error" ? <Message kind="error">{error}</Message> : null}
        {status === "ready" ? (
          <div className="rounded-xl border border-ink/20 bg-sand/60 px-4 py-4">
            {files.length === 0 ? (
              <p className="text-sm font-light text-ink">Upload a PDF to get started</p>
            ) : (
              <ul className="space-y-2">
                {files.map((name) => (
                  <li key={name}>
                    <label className="flex cursor-pointer items-start gap-2 rounded px-1 py-0.5 focus-within:ring-2 focus-within:ring-rose">
                      <input
                        type="checkbox"
                        checked={selected.includes(name)}
                        onChange={() => onToggle(name)}
                        aria-label={`Search only ${name}`}
                        className="mt-0.5 h-4 w-4 shrink-0 accent-rose focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose"
                      />
                      <span className="min-w-0 break-words text-sm font-normal text-ink">
                        {name}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}
      </div>
      {showHint ? (
        <p className="text-xs font-light">
          {selected.length > 0
            ? `Searching ${selected.length} selected file${selected.length === 1 ? "" : "s"}.`
            : "No file selected — the question searches all PDFs."}
        </p>
      ) : null}
    </section>
  );
}

/*
 * FR-14: question input, Enter or button submits.
 * FR-16: k input, default 5, range 1–10.
 * FR-18: the whole form is disabled while no PDF is indexed.
 */
function AskForm({
  question,
  onQuestion,
  kValue,
  onKValue,
  onKBlur,
  asking,
  disabled,
  onSubmit,
}) {
  const canSubmit = !disabled && !asking && question.trim() !== "";
  return (
    <form aria-labelledby="ask-heading" className="space-y-4" onSubmit={onSubmit}>
      <h2 id="ask-heading" className="text-lg font-semibold">
        Ask a question
      </h2>
      <div className="space-y-1.5">
        <label htmlFor="question" className="block text-sm font-normal">
          Question
        </label>
        <input
          id="question"
          name="question"
          type="text"
          value={question}
          onChange={(event) => onQuestion(event.target.value)}
          placeholder="e.g. What is the importance of the title?"
          disabled={disabled}
          aria-describedby="question-hint"
          className="w-full rounded-lg border border-ink/20 bg-white/40 px-3 py-2 text-ink placeholder:text-ink/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose disabled:cursor-not-allowed disabled:opacity-50"
        />
        <p id="question-hint" className="text-xs font-light">
          {disabled ? "Upload a PDF to get started." : "Press Enter to submit."}
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1.5">
          <label htmlFor="k" className="block text-sm font-normal">
            Chunks (k)
          </label>
          <input
            id="k"
            name="k"
            type="number"
            min={1}
            max={10}
            inputMode="numeric"
            value={kValue}
            onChange={(event) => onKValue(event.target.value)}
            onBlur={onKBlur}
            disabled={disabled}
            aria-describedby="k-hint"
            className="w-24 rounded-lg border border-ink/20 bg-white/40 px-3 py-2 text-ink placeholder:text-ink/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose disabled:cursor-not-allowed disabled:opacity-50"
          />
          <p id="k-hint" className="text-xs font-light">
            Default 5 (1–10).
          </p>
        </div>
        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-lg bg-rose px-5 py-2 font-semibold text-ink transition-colors hover:bg-rose/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose disabled:cursor-not-allowed disabled:opacity-50"
        >
          Ask
        </button>
      </div>
    </form>
  );
}

/* FR-15: the answer in a card (text-lg, weight 400); FR-17: "Thinking…". */
function AnswerCard({ asking, error, answer }) {
  return (
    <section aria-labelledby="answer-heading" className="space-y-3">
      <h2 id="answer-heading" className="text-lg font-semibold">
        Answer
      </h2>
      <div aria-live="polite" className="space-y-3">
        {asking ? <Message kind="loading">Thinking…</Message> : null}
        {!asking && error ? <Message kind="error">{error}</Message> : null}
        {!asking && !error ? (
          <div className="rounded-xl border border-ink/20 bg-white/40 px-5 py-4">
            {answer !== null ? (
              <p className="break-words whitespace-pre-line text-lg font-normal text-ink">
                {answer}
              </p>
            ) : (
              <p className="text-lg font-light text-ink">
                Ask a question and the answer will appear here.
              </p>
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}

/* FR-15: one small card per source — file name, page number, snippet. */
function SourceCard({ file, page, snippet }) {
  return (
    <article className="rounded-lg border border-ink/20 bg-white/40 px-4 py-3">
      <p className="break-words text-sm font-normal text-ink">
        {file} · p. {page}
      </p>
      <p className="mt-1 break-words text-sm font-light text-ink">{snippet}</p>
    </article>
  );
}

function Sources({ sources }) {
  return (
    <section aria-labelledby="sources-heading" className="space-y-3">
      <h2 id="sources-heading" className="text-lg font-semibold">
        Sources
      </h2>
      {sources.length > 0 ? (
        <div className="space-y-3">
          {sources.map((source, index) => (
            <SourceCard
              key={`${source.file}-${source.page}-${index}`}
              file={source.file}
              page={source.page}
              snippet={source.snippet}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-ink/20 bg-white/40 px-5 py-4">
          <p className="text-sm font-light text-ink">
            Sources (file, page and snippet) appear here after you ask.
          </p>
        </div>
      )}
    </section>
  );
}

export default function App() {
  /* File list (FR-12 / FR-18) */
  const [files, setFiles] = useState([]);
  const [filesStatus, setFilesStatus] = useState("loading"); // loading | ready | error
  const [filesError, setFilesError] = useState(null);
  const [selected, setSelected] = useState([]);

  /* Upload (FR-11 / FR-17) */
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null); // {kind, text}

  /* Ask (FR-13 … FR-17) */
  const [question, setQuestion] = useState("");
  const [kValue, setKValue] = useState("5");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState(null);
  const [sources, setSources] = useState([]);
  const [askError, setAskError] = useState(null);

  async function loadFiles() {
    try {
      const response = await fetch(`${API_URL}/files`);
      if (!response.ok) {
        throw new Error(await readDetail(response));
      }
      const data = await response.json();
      const names = Array.isArray(data)
        ? data.filter((name) => typeof name === "string")
        : [];
      setFiles(names);
      setFilesStatus("ready");
      setFilesError(null);
      /* Drop selections for files that no longer exist (re-upload replaced). */
      setSelected((previous) => previous.filter((name) => names.includes(name)));
      return names;
    } catch (error) {
      setFilesStatus("error");
      setFilesError(toMessage(error));
      return null;
    }
  }

  /* FR-12: GET /files on initial load. */
  useEffect(() => {
    loadFiles();
  }, []);

  /* FR-11: POST /upload as multipart with the field name app.py declares. */
  async function uploadFile(file) {
    if (!file || uploading) {
      return;
    }
    setUploading(true);
    setUploadStatus({ kind: "loading", text: "Indexing…" });
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: form,
      });
      if (!response.ok) {
        throw new Error(await readDetail(response));
      }
      const data = await response.json();
      setUploadStatus({
        kind: "success",
        text: `${data.file} · ${data.pages} pages · ${data.chunks} chunks`,
      });
      await loadFiles();
    } catch (error) {
      setUploadStatus({ kind: "error", text: toMessage(error) });
    } finally {
      setUploading(false);
    }
  }

  function toggleFile(name) {
    setSelected((previous) =>
      previous.includes(name)
        ? previous.filter((item) => item !== name)
        : [...previous, name],
    );
  }

  /* FR-13 / FR-14 / FR-16: POST /ask; files and k omitted when unchanged. */
  async function askQuestion(event) {
    event.preventDefault();
    const trimmed = question.trim();
    if (trimmed === "" || asking || noFilesYet) {
      return;
    }
    setAsking(true);
    setAskError(null);
    setAnswer(null); /* FR-17: the previous answer is cleared while in flight. */
    setSources([]);

    const body = { question: trimmed };
    if (selected.length > 0) {
      body.files = [...selected];
    }
    const k = parseK(kValue);
    if (k !== 5) {
      body.k = k; /* unchanged k is omitted so the API default (5) applies */
    }

    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        throw new Error(await readDetail(response));
      }
      const data = await response.json();
      setAnswer(typeof data.answer === "string" ? data.answer : "");
      setSources(Array.isArray(data.sources) ? data.sources : []);
    } catch (error) {
      setAskError(toMessage(error));
    } finally {
      setAsking(false);
    }
  }

  const noFilesYet = filesStatus === "ready" && files.length === 0;

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      {/* FR-20: two columns from md up; on mobile the left panel stacks above. */}
      <div className="flex flex-1 flex-col md:flex-row">
        <aside className="space-y-8 bg-ink px-6 py-6 text-sand md:w-80 md:shrink-0 lg:w-96">
          <UploadPanel uploading={uploading} status={uploadStatus} onFile={uploadFile} />
          <FileList
            status={filesStatus}
            error={filesError}
            files={files}
            selected={selected}
            onToggle={toggleFile}
          />
        </aside>
        <main className="flex-1 space-y-8 px-6 py-6 md:px-8 md:py-8">
          <AskForm
            question={question}
            onQuestion={setQuestion}
            kValue={kValue}
            onKValue={setKValue}
            onKBlur={() => setKValue(String(parseK(kValue)))}
            asking={asking}
            disabled={noFilesYet}
            onSubmit={askQuestion}
          />
          <AnswerCard asking={asking} error={askError} answer={answer} />
          <Sources sources={sources} />
        </main>
      </div>
    </div>
  );
}
