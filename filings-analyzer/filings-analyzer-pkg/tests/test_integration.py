"""
Integration tests: exercise real HTTP endpoints through the full stack
(routing, auth, validation, DB). Only the external LLM is mocked.
"""

from io import BytesIO
from unittest.mock import patch

from reportlab.pdfgen import canvas


def _make_pdf_bytes(text: str = "ACME CORP 10-K. Revenue grew. Risks exist.") -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, text)
    c.showPage()
    c.save()
    return buf.getvalue()


# ---------- auth ----------
def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_register_and_login(client):
    r = client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "a@example.com"

    r = client.post(
        "/auth/login",
        data={"username": "a@example.com", "password": "password123"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_duplicate_email_rejected(client):
    body = {"email": "dup@example.com", "password": "password123"}
    assert client.post("/auth/register", json=body).status_code == 201
    assert client.post("/auth/register", json=body).status_code == 409


def test_login_wrong_password(client):
    client.post(
        "/auth/register",
        json={"email": "b@example.com", "password": "password123"},
    )
    r = client.post(
        "/auth/login",
        data={"username": "b@example.com", "password": "WRONG"},
    )
    assert r.status_code == 401


def test_short_password_rejected(client):
    r = client.post(
        "/auth/register",
        json={"email": "c@example.com", "password": "short"},
    )
    assert r.status_code == 422  # pydantic validation


# ---------- auth protection ----------
def test_documents_require_auth(client):
    assert client.get("/documents").status_code == 401


# ---------- document upload ----------
def test_upload_and_list_document(auth_client):
    files = {"file": ("acme.pdf", _make_pdf_bytes(), "application/pdf")}
    r = auth_client.post("/documents", files=files)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["filename"] == "acme.pdf"

    r = auth_client.get("/documents")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_upload_rejects_non_pdf(auth_client):
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    r = auth_client.post("/documents", files=files)
    assert r.status_code == 400


def test_upload_rejects_unreadable_pdf(auth_client):
    files = {"file": ("bad.pdf", b"not really a pdf", "application/pdf")}
    r = auth_client.post("/documents", files=files)
    assert r.status_code == 422


# ---------- ownership isolation ----------
def test_user_cannot_see_others_document(client):
    # User 1 uploads
    client.post("/auth/register", json={"email": "u1@example.com", "password": "password123"})
    t1 = client.post("/auth/login", data={"username": "u1@example.com", "password": "password123"}).json()["access_token"]
    files = {"file": ("secret.pdf", _make_pdf_bytes(), "application/pdf")}
    doc_id = client.post("/documents", files=files, headers={"Authorization": f"Bearer {t1}"}).json()["id"]

    # User 2 tries to fetch it -> 404 (not 403, to avoid leaking existence)
    client.post("/auth/register", json={"email": "u2@example.com", "password": "password123"})
    t2 = client.post("/auth/login", data={"username": "u2@example.com", "password": "password123"}).json()["access_token"]
    r = client.get(f"/documents/{doc_id}", headers={"Authorization": f"Bearer {t2}"})
    assert r.status_code == 404


# ---------- analysis (LLM mocked) ----------
def test_create_analysis_and_caching(auth_client):
    files = {"file": ("acme.pdf", _make_pdf_bytes(), "application/pdf")}
    doc_id = auth_client.post("/documents", files=files).json()["id"]

    with patch("app.api.analyses.analyze", return_value="Revenue grew 10%.") as mock_analyze:
        # First question -> LLM called
        r = auth_client.post(
            f"/documents/{doc_id}/analyses",
            json={"question": "How did revenue change?"},
        )
        assert r.status_code == 201
        assert r.json()["answer"] == "Revenue grew 10%."
        assert mock_analyze.call_count == 1

        # Same question again -> served from cache, LLM NOT called again
        r2 = auth_client.post(
            f"/documents/{doc_id}/analyses",
            json={"question": "How did revenue change?"},
        )
        assert r2.status_code == 201
        assert mock_analyze.call_count == 1  # still 1 -> cache hit


def test_analysis_llm_failure_returns_502(auth_client):
    from app.services.llm_service import LLMError

    files = {"file": ("acme.pdf", _make_pdf_bytes(), "application/pdf")}
    doc_id = auth_client.post("/documents", files=files).json()["id"]

    with patch("app.api.analyses.analyze", side_effect=LLMError("model down")):
        r = auth_client.post(
            f"/documents/{doc_id}/analyses",
            json={"question": "anything?"},
        )
        assert r.status_code == 502


def test_analysis_on_missing_document_404(auth_client):
    with patch("app.api.analyses.analyze", return_value="x"):
        r = auth_client.post(
            "/documents/99999/analyses",
            json={"question": "anything?"},
        )
        assert r.status_code == 404
