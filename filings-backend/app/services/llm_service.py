"""
LLM analysis service.

Responsibilities:
  * Talk to an LLM backend — either Ollama (local, free) or the Anthropic API.
    The choice is controlled by settings.llm_provider.
  * Retry transient failures with exponential backoff.
  * Handle documents too long for one call via a map-reduce over chunks:
      map:    ask the question against each chunk
      reduce: combine the per-chunk answers into one final answer

The provider only affects the single innermost "make one model call" step.
All chunking, retry, and map-reduce logic is provider-agnostic.
"""

import time

from app.core.config import settings
from app.services.chunking import chunk_text


class LLMError(Exception):
    """Raised when the LLM cannot produce an answer after retries."""


_SYSTEM_PROMPT = (
    "You are a financial-filing analyst. Answer questions about the provided "
    "filing text accurately and concisely. If the answer is not contained in "
    "the text, say so plainly rather than guessing."
)

_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 1.0


def _call_ollama(prompt: str, max_tokens: int) -> str:
    """Make one call to a local Ollama server via its OpenAI-compatible API."""
    from openai import OpenAI

    client = OpenAI(
        base_url=settings.ollama_base_url,
        api_key="ollama",  # Ollama ignores the key, but the SDK requires one.
    )
    resp = client.chat.completions.create(
        model=settings.ollama_model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _call_anthropic(prompt: str, max_tokens: int) -> str:
    """Make one call to the Anthropic Messages API."""
    from anthropic import Anthropic

    if not settings.anthropic_api_key:
        raise LLMError("ANTHROPIC_API_KEY is not configured")
    client = Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [b.text for b in message.content if getattr(b, "type", "") == "text"]
    return "".join(parts).strip()


def _call_groq(prompt: str, max_tokens: int) -> str:
    """Make one call to Groq's OpenAI-compatible API (hosted, fast, free tier)."""
    from openai import OpenAI

    if not settings.groq_api_key:
        raise LLMError("GROQ_API_KEY is not configured")
    client = OpenAI(
        base_url=settings.groq_base_url,
        api_key=settings.groq_api_key,
    )
    resp = client.chat.completions.create(
        model=settings.groq_model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _call_provider(prompt: str, max_tokens: int) -> str:
    """Dispatch a single model call to the configured provider."""
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        return _call_ollama(prompt, max_tokens)
    if provider == "groq":
        return _call_groq(prompt, max_tokens)
    if provider == "anthropic":
        return _call_anthropic(prompt, max_tokens)
    raise LLMError(f"Unknown LLM provider: {settings.llm_provider!r}")


def _call_with_retry(prompt: str, max_tokens: int) -> str:
    """One model call wrapped in exponential-backoff retry.

    LLMError (e.g. misconfiguration) is treated as permanent and not retried;
    other exceptions are treated as transient and retried with backoff.
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            answer = _call_provider(prompt, max_tokens)
            if not answer:
                raise LLMError("Model returned an empty response")
            return answer
        except LLMError:
            # Configuration / permanent errors: don't retry.
            raise
        except Exception as exc:  # transient: network, timeout, 5xx, etc.
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_BASE_BACKOFF_SECONDS * (2 ** attempt))

    raise LLMError(f"LLM call failed after {_MAX_RETRIES} attempts: {last_exc}")


def _build_prompt(question: str, context: str) -> str:
    return (
        f"Filing text:\n\n{context}\n\n"
        f"---\n\nQuestion: {question}"
    )


def analyze(question: str, document_text: str) -> str:
    """
    Answer a question about a document.

    Short docs -> one call. Long docs -> map over chunks, then reduce.
    """
    chunks = chunk_text(document_text)
    if not chunks:
        raise LLMError("Document has no analyzable text")

    # Common case: fits in a single call.
    if len(chunks) == 1:
        return _call_with_retry(_build_prompt(question, chunks[0]), max_tokens=1024)

    # Long document: map the question over each chunk...
    partial_answers = []
    for i, chunk in enumerate(chunks):
        partial = _call_with_retry(
            _build_prompt(question, chunk),
            max_tokens=512,
        )
        partial_answers.append(f"[Section {i + 1}]\n{partial}")

    # ...then reduce the partials into one coherent answer.
    reduce_prompt = (
        f"A reader asked: {question}\n\n"
        f"Here are notes extracted from different sections of the filing:\n\n"
        + "\n\n".join(partial_answers)
        + "\n\n---\n\nSynthesize these notes into one clear, non-repetitive "
        "answer to the question."
    )
    return _call_with_retry(reduce_prompt, max_tokens=1024)
