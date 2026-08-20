import time
import logfire
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import settings

BATCH_SIZE = 50  # Number of texts sent to Gemini in one API call.
_GEMINI_DIM = 3072  # Size of the Gemini embedding vector.

_active_model = None


# ── Model initialisation ───────────────────────────────────────────────────────

def _probe_gemini():
    """Create and verify the required Gemini embedding model."""
    try:
        model = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-2-preview",
            google_api_key=settings.GEMINI_API_KEY,
        )
        model.embed_query("probe")
        logfire.info("Gemini embeddings ready (gemini-embedding-2-preview, 3072-dim).")
        return model
    except Exception as e:
        logfire.error(f"Gemini embeddings are unavailable: {e}")
        raise RuntimeError(
            "Gemini embeddings are unavailable. Check GEMINI_API_KEY and network access."
        ) from e


def _init():
    """Initialise the Gemini embedding model once per process."""
    global _active_model
    if _active_model is not None:
        return

    _active_model = _probe_gemini()


# ── Public helpers ─────────────────────────────────────────────────────────────

def get_embedding_dim() -> int:
    """Return the dimension used by the required Gemini embedding model."""
    _init()
    return _GEMINI_DIM


# ── Batch embedding with retry ─────────────────────────────────────────────────

def _embed_batch(batch: list[str]) -> list[list[float]]:
    # Exponential backoff: 1 s → 2 s → 4 s → 8 s (4 attempts total)
    for attempt in range(4):
        try:
            return _active_model.embed_documents(batch)
        except Exception as e:
            err = str(e).lower()
            is_rate_limit = any(
                value in err
                for value in ("429", "rate", "quota", "resource_exhausted")
            )
            if is_rate_limit and attempt < 3:
                wait = 2 ** attempt
                logfire.warning(
                    f"Gemini rate limit hit — retrying in {wait}s "
                    f"(attempt {attempt + 1}/4)."
                )
                time.sleep(wait)
            else:
                logfire.error(f"Gemini embedding failed: {e}")
                raise

    raise RuntimeError("Gemini rate limit persisted after 4 attempts.")


# ── Public API (same signatures as before) ─────────────────────────────────────

def embed_query(query: str) -> list[float]:
    _init()
    return _active_model.embed_query(query)


def embed_texts(texts: list[str]) -> list[list[float]]:
    _init()
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        with logfire.span("Embed batch", model="gemini", start=i, size=len(batch)):
            all_embeddings.extend(_embed_batch(batch))
    return all_embeddings
