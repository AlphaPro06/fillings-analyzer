import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import {
  ApiError,
  askQuestion,
  clearToken,
  getToken,
  listAnalyses,
  listDocuments,
  login,
  register,
  uploadDocument,
  type AnalysisOut,
  type DocumentOut,
} from "./api";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// ============================================================
// Auth screen
// ============================================================
function AuthScreen({ onAuthed }: { onAuthed: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!email || !password) {
      setError("Enter an email and password to continue.");
      return;
    }
    setBusy(true);
    try {
      if (mode === "register") {
        await register(email, password);
      }
      await login(email, password);
      onAuthed();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Something went wrong. Try again.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <aside className="auth-brand">
        <div className="auth-brand__mark">Filings Analyzer</div>
        <h1 className="auth-brand__headline">
          Read the filing.<br />Ask the <em>hard questions.</em>
        </h1>
        <p className="auth-brand__note">
          Upload a financial filing and interrogate it in plain language — risk
          factors, revenue outlook, whatever you need to know.
        </p>
      </aside>

      <main className="auth-form-side">
        <div className="auth-card">
          <h2 className="auth-card__title">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h2>
          <p className="auth-card__sub">
            {mode === "login"
              ? "Sign in to your workspace."
              : "Start analyzing filings in seconds."}
          </p>

          {error && <div className="alert alert-error">{error}</div>}

          <div className="field">
            <label className="label" htmlFor="email">Email</label>
            <input
              id="email"
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder="you@example.com"
              autoComplete="email"
            />
          </div>

          <div className="field">
            <label className="label" htmlFor="password">Password</label>
            <input
              id="password"
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder={mode === "register" ? "At least 8 characters" : "Your password"}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </div>

          <button className="btn btn-gold" style={{ width: "100%" }} onClick={submit} disabled={busy}>
            {busy ? <span className="spinner" /> : mode === "login" ? "Sign in" : "Create account"}
          </button>

          <p className="auth-toggle">
            {mode === "login" ? "New here? " : "Already have an account? "}
            <button
              onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}
            >
              {mode === "login" ? "Create an account" : "Sign in"}
            </button>
          </p>
        </div>
      </main>
    </div>
  );
}

// ============================================================
// Workspace (main app)
// ============================================================
function Workspace({ onLogout }: { onLogout: () => void }) {
  const [docs, setDocs] = useState<DocumentOut[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisOut[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refreshDocs = useCallback(async () => {
    try {
      const d = await listDocuments();
      setDocs(d);
      if (d.length && selectedId === null) setSelectedId(d[0].id);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) onLogout();
    }
  }, [selectedId, onLogout]);

  useEffect(() => { refreshDocs(); }, [refreshDocs]);

  // load analyses when the selected document changes
  useEffect(() => {
    if (selectedId === null) { setAnalyses([]); return; }
    listAnalyses(selectedId).then(setAnalyses).catch(() => setAnalyses([]));
  }, [selectedId]);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const file = files[0];
    setError(null);
    setUploading(true);
    try {
      const doc = await uploadDocument(file);
      await refreshDocs();
      setSelectedId(doc.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed. Try another file.");
    } finally {
      setUploading(false);
    }
  }

  async function submitQuestion() {
    if (!question.trim() || selectedId === null) return;
    const q = question.trim();
    setError(null);
    setAsking(true);
    setQuestion("");
    try {
      const result = await askQuestion(selectedId, q);
      // Put newest on top; the backend returns cached results instantly.
      setAnalyses((prev) => [result, ...prev.filter((a) => a.id !== result.id)]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't get an answer. Try again.");
      setQuestion(q); // restore what they typed
    } finally {
      setAsking(false);
    }
  }

  const selectedDoc = docs.find((d) => d.id === selectedId) ?? null;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar__brand">Filings<span>·</span>Analyzer</div>
        <div className="topbar__user">
          <button className="btn btn-ghost" onClick={onLogout}>Sign out</button>
        </div>
      </header>

      <div className="workspace">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar__head">
            <h2 className="sidebar__title">Documents</h2>
            <span className="sidebar__count">{docs.length}</span>
          </div>

          <div
            className={`upload-zone ${dragging ? "drag" : ""}`}
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
          >
            <div className="upload-zone__icon">
              {uploading ? <span className="spinner spinner-ink" /> : "↑"}
            </div>
            <div className="upload-zone__text">
              {uploading ? "Uploading…" : (<><strong>Upload a PDF</strong><br />or drop it here</>)}
            </div>
            <input
              ref={fileRef}
              type="file"
              accept="application/pdf"
              hidden
              onChange={(e) => handleFiles(e.target.files)}
            />
          </div>

          <div className="doc-list">
            {docs.map((doc) => (
              <button
                key={doc.id}
                className={`doc-item ${doc.id === selectedId ? "active" : ""}`}
                onClick={() => setSelectedId(doc.id)}
              >
                <span className="doc-item__name">{doc.filename}</span>
                <span className="doc-item__date">{formatDate(doc.created_at)}</span>
              </button>
            ))}
          </div>
        </aside>

        {/* Main panel */}
        <main className="panel">
          {!selectedDoc ? (
            <div className="panel__empty">
              <div className="panel__empty-title">No document selected</div>
              <p>Upload a filing on the left to begin your analysis.</p>
            </div>
          ) : (
            <>
              <div className="doc-header">
                <div className="eyebrow doc-header__eyebrow">Now analyzing</div>
                <h1 className="doc-header__name">{selectedDoc.filename}</h1>
              </div>

              {error && <div className="alert alert-error">{error}</div>}

              <div className="ask">
                <div className="ask__row">
                  <textarea
                    className="input"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitQuestion(); }
                    }}
                    placeholder="Ask about risk factors, revenue outlook, liabilities…"
                    rows={1}
                  />
                  <button className="btn btn-gold" onClick={submitQuestion} disabled={asking || !question.trim()}>
                    {asking ? <span className="spinner" /> : "Ask"}
                  </button>
                </div>
                <div className="ask__hint">
                  Answers are grounded in the filing text. Ask the same question twice and the second
                  reply is served <strong>instantly from cache</strong>.
                </div>
              </div>

              <div className="answers">
                {asking && (
                  <div className="thinking">
                    <span className="spinner spinner-ink" />
                    Reading the filing…
                  </div>
                )}
                {analyses.map((a) => (
                  <article className="qa" key={a.id}>
                    <div className="qa__q">{a.question}</div>
                    <div className="qa__a">{a.answer}</div>
                    <div className="qa__meta">Answered {formatDate(a.created_at)}</div>
                  </article>
                ))}
                {!asking && analyses.length === 0 && (
                  <p style={{ color: "var(--ink-soft)" }}>
                    No questions yet. Ask your first one above.
                  </p>
                )}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

// ============================================================
// Root
// ============================================================
export default function App() {
  const [authed, setAuthed] = useState<boolean>(() => getToken() !== null);

  function handleLogout() {
    clearToken();
    setAuthed(false);
  }

  return authed
    ? <Workspace onLogout={handleLogout} />
    : <AuthScreen onAuthed={() => setAuthed(true)} />;
}
