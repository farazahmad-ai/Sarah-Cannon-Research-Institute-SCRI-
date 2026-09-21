"""Async batch embedding service for SCRI Oncology Copilot.

Generates 1536-dimensional dense vectors from protocol chunk texts using
the text-embedding-3-small model via OpenAI-compatible API (OpenRouter).

Design decisions:
- Batches up to 64 texts per API call to stay well under the 2048-input
  limit and minimize round-trips without triggering rate limit bursts.
- Exponential backoff handles transient 429 / 5xx errors automatically.
- embed_texts() is the only public function -- callers pass plain strings
  and receive plain list[float] vectors with no library-specific types.
"""

from __future__ import annotations

import asyncio
import logging

from openai import APIStatusError, AsyncOpenAI, RateLimitError

from app.config import settings

logger = logging.getLogger(__name__)

# Texts per single API call (OpenAI allows up to 2048; 64 is a safe batch)
_BATCH_SIZE = 64

# Backoff parameters for rate-limit retries
_MAX_RETRIES = 5
_INITIAL_BACKOFF_S = 1.0
_BACKOFF_MULTIPLIER = 2.0

# In-memory LRU-style cache for repeated query embeddings (e.g. quick prompts)
_EMBEDDING_CACHE: dict[str, list[float]] = {}
_MAX_CACHE_SIZE = 500


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts using batched async API calls with caching.

    Args:
        texts: Plain strings to embed (use chunk.embed_text, not chunk.chunk_text,
               so that the context prefix is encoded into the vector).

    Returns:
        List of 1536-dimensional float vectors, one per input text, in the
        same order as the input list.

    Raises:
        RuntimeError: If the API returns vectors with unexpected dimensions.
    """
    if not texts:
        return []

    # Check cache first
    uncached_indices: list[int] = []
    uncached_texts: list[str] = []
    result_vectors: list[list[float] | None] = [None] * len(texts)

    for i, t in enumerate(texts):
        if t in _EMBEDDING_CACHE:
            result_vectors[i] = _EMBEDDING_CACHE[t]
        else:
            uncached_indices.append(i)
            uncached_texts.append(t)

    # If all were cached, return immediately
    if not uncached_texts:
        return [v for v in result_vectors if v is not None]

    all_vectors: list[list[float]] = []
    total_batches = (len(uncached_texts) + _BATCH_SIZE - 1) // _BATCH_SIZE

    async with AsyncOpenAI(
        api_key=settings.effective_api_key,
        base_url=settings.effective_base_url,
    ) as client:
        for batch_idx in range(total_batches):
            batch = uncached_texts[batch_idx * _BATCH_SIZE : (batch_idx + 1) * _BATCH_SIZE]
            vectors = await _embed_batch_with_retry(client, batch, batch_idx, total_batches)
            all_vectors.extend(vectors)

    # Sanity check: verify embedding dimensions match pgvector column definition
    if all_vectors and len(all_vectors[0]) != settings.OPENAI_EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"Embedding dimension mismatch: expected {settings.OPENAI_EMBEDDING_DIMENSIONS}, "
            f"got {len(all_vectors[0])}. Check OPENAI_EMBEDDING_MODEL in config."
        )

    # Populate cache and results
    for idx_in_uncached, original_idx in enumerate(uncached_indices):
        vec = all_vectors[idx_in_uncached]
        t = uncached_texts[idx_in_uncached]
        if len(_EMBEDDING_CACHE) >= _MAX_CACHE_SIZE:
            # Pop oldest key to keep bounded memory
            _EMBEDDING_CACHE.pop(next(iter(_EMBEDDING_CACHE)))
        _EMBEDDING_CACHE[t] = vec
        result_vectors[original_idx] = vec

    return [v for v in result_vectors if v is not None]


async def _embed_batch_with_retry(
    client: AsyncOpenAI,
    batch: list[str],
    batch_idx: int,
    total_batches: int,
) -> list[list[float]]:
    """Call the embeddings API for one batch with exponential backoff on rate limits.

    Retries on:
      - 429 RateLimitError (token or request quota exceeded)
      - 5xx APIStatusError (transient server errors)

    Raises immediately on 4xx client errors (bad request, auth failure) since
    retrying would not resolve the underlying configuration problem.
    """
    backoff = _INITIAL_BACKOFF_S

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=batch,
            )
            vectors = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
            logger.info(
                "Embedded batch %d/%d (%d texts, attempt %d)",
                batch_idx + 1,
                total_batches,
                len(batch),
                attempt,
            )
            return vectors

        except RateLimitError:
            if attempt == _MAX_RETRIES:
                logger.error("Rate limit exceeded after %d retries on batch %d", _MAX_RETRIES, batch_idx + 1)
                raise
            logger.warning(
                "Rate limited on batch %d (attempt %d/%d). Retrying in %.1fs...",
                batch_idx + 1,
                attempt,
                _MAX_RETRIES,
                backoff,
            )
            await asyncio.sleep(backoff)
            backoff *= _BACKOFF_MULTIPLIER

        except APIStatusError as exc:
            # Retry on server errors (5xx), raise immediately on client errors (4xx)
            if exc.status_code >= 500:
                if attempt == _MAX_RETRIES:
                    logger.error("Server error after %d retries on batch %d: %s", _MAX_RETRIES, batch_idx + 1, exc)
                    raise
                logger.warning(
                    "Server error %d on batch %d (attempt %d/%d). Retrying in %.1fs...",
                    exc.status_code,
                    batch_idx + 1,
                    attempt,
                    _MAX_RETRIES,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff *= _BACKOFF_MULTIPLIER
            else:
                raise

    # Unreachable, but satisfies type checker
    raise RuntimeError(f"Failed to embed batch {batch_idx + 1} after {_MAX_RETRIES} attempts")
