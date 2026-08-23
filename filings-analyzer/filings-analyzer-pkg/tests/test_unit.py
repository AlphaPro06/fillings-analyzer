"""Unit tests: individual components in isolation, no HTTP, no real LLM."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.services.chunking import chunk_text
from app.services.pdf_service import PdfExtractionError, extract_text_from_pdf


# ---------- security ----------
def test_password_hash_roundtrip():
    h = hash_password("supersecret123")
    assert h != "supersecret123"
    assert verify_password("supersecret123", h)
    assert not verify_password("wrong", h)


def test_password_over_72_bytes_does_not_crash():
    pw = "a" * 200
    assert verify_password(pw, hash_password(pw))


def test_jwt_roundtrip_and_invalid():
    token = create_access_token("mo@example.com")
    assert decode_access_token(token) == "mo@example.com"
    assert decode_access_token("not.a.token") is None


# ---------- chunking ----------
def test_chunk_short_text_single_chunk():
    assert chunk_text("hello") == ["hello"]


def test_chunk_empty_text():
    assert chunk_text("   ") == []


def test_chunk_long_text_has_overlap():
    text = "A" * 30000
    chunks = chunk_text(text, chunk_chars=12000, overlap_chars=500)
    assert len(chunks) == 3
    assert chunks[0][-500:] == chunks[1][:500]


def test_chunk_rejects_bad_overlap():
    with pytest.raises(ValueError):
        chunk_text("A" * 100, chunk_chars=10, overlap_chars=10)


# ---------- pdf ----------
def _make_pdf(lines: list[str]) -> bytes:
    from io import BytesIO

    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf)
    y = 750
    for line in lines:
        c.drawString(100, y, line)
        y -= 20
    c.showPage()
    c.save()
    return buf.getvalue()


def test_extract_text_from_valid_pdf():
    pdf = _make_pdf(["ACME 10-K", "Risk Factors here"])
    text = extract_text_from_pdf(pdf)
    assert "ACME" in text and "Risk Factors" in text


def test_extract_text_from_invalid_pdf_raises():
    with pytest.raises(PdfExtractionError):
        extract_text_from_pdf(b"not a pdf at all")


# ---------- llm service ----------
# These test the provider-agnostic logic (single-call, map-reduce, retry) by
# mocking the innermost provider call, so they don't depend on any one vendor.
def test_llm_single_call():
    import app.services.llm_service as llm

    with patch.object(llm, "_call_provider", return_value="42%") as m:
        assert llm.analyze("What is the margin?", "Short filing.") == "42%"
        assert m.call_count == 1


def test_llm_map_reduce_for_long_doc():
    import app.services.llm_service as llm

    with patch.object(llm, "_call_provider", return_value="partial") as m:
        llm.analyze("summarize", "B" * 30000)  # 3 chunks
        # 3 map calls + 1 reduce call
        assert m.call_count == 4


def test_llm_retries_on_transient_error():
    import app.services.llm_service as llm

    with patch.object(llm, "time"):  # skip real sleeps
        with patch.object(
            llm,
            "_call_provider",
            side_effect=[ConnectionError("boom"), "recovered"],
        ) as m:
            assert llm.analyze("q", "short") == "recovered"
            assert m.call_count == 2


def test_llm_config_error_not_retried():
    """A permanent LLMError (e.g. bad config) should fail immediately."""
    import app.services.llm_service as llm

    with patch.object(
        llm, "_call_provider", side_effect=llm.LLMError("misconfigured")
    ) as m:
        try:
            llm.analyze("q", "short")
            assert False, "should have raised"
        except llm.LLMError:
            pass
        assert m.call_count == 1  # not retried
