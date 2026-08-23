from io import BytesIO

from pypdf import PdfReader


class PdfExtractionError(Exception):
    """Raised when a PDF cannot be read or contains no extractable text."""


def extract_text_from_pdf(raw_bytes: bytes) -> str:
    """
    Extract text from a PDF's bytes.

    Note: this works for text-based PDFs (the vast majority of filings).
    Scanned/image-only PDFs would need OCR — that's noted as future work.
    """
    try:
        reader = PdfReader(BytesIO(raw_bytes))
    except Exception as exc:  # pypdf raises various errors on malformed files
        raise PdfExtractionError(f"Could not read PDF: {exc}") from exc

    pages_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages_text.append(text)

    combined = "\n\n".join(pages_text).strip()
    if not combined:
        raise PdfExtractionError(
            "No extractable text found. The PDF may be scanned/image-only."
        )
    return combined
