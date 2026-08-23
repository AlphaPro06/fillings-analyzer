"""
Splitting long documents into chunks.

Filings routinely exceed what's sensible to send in a single prompt, so we
split the extracted text into overlapping chunks. The overlap keeps sentences
that straddle a boundary from losing their context.

We chunk on characters (not tokens) for simplicity and zero extra
dependencies. A rough chars-per-token ratio keeps chunks comfortably within
model limits. This is deliberately simple; token-accurate chunking is noted
as future work.
"""

# ~4 chars per token is a common rough estimate for English prose.
DEFAULT_CHUNK_CHARS = 12_000
DEFAULT_OVERLAP_CHARS = 500


def chunk_text(
    text: str,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[str]:
    """Split text into overlapping chunks. Returns at least one chunk."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_chars:
        return [text]

    if overlap_chars >= chunk_chars:
        raise ValueError("overlap_chars must be smaller than chunk_chars")

    chunks: list[str] = []
    start = 0
    step = chunk_chars - overlap_chars
    while start < len(text):
        end = start + chunk_chars
        chunks.append(text[start:end])
        start += step
    return chunks
