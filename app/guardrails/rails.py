import logfire
from langchain_groq import ChatGroq
from nemoguardrails import RailsConfig, LLMRails

from app.config import settings
from app.guardrails.colang_rules import COLANG_CONTENT, YAML_CONTENT, RAIL_INDICATORS
from app.guardrails.safety import find_sensitive_data, validate_output


_rails: LLMRails | None = None


def initialize_rails() -> None:
    """
    Build the NeMo LLMRails singleton at app startup.
    Uses the configured Groq model for low-latency intent classification.
    """
    global _rails

    guard_llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
        temperature=0,
        reasoning_format="hidden",
    )

    config = RailsConfig.from_content(
        colang_content=COLANG_CONTENT,
        yaml_content=YAML_CONTENT
    )

    _rails = LLMRails(config, llm=guard_llm)
    logfire.info(f"🛡️ NeMo Guardrails initialised ({settings.GROQ_MODEL}).")
    
    


def guard(message: str) -> tuple[bool, str | None]:
    """
    Run a user message through the NeMo rails gate.

    Returns:
        (True,  rail_response) — a rail fired; return this response immediately,
                                skip the RAG pipeline entirely.
        (False, None)          — message is clean; proceed to LangGraph.
    """
    # Run deterministic checks first: sensitive values must not be sent to an
    # external LLM, the vector store, Portkey, or request telemetry.
    sensitive_finding = find_sensitive_data(message)
    if sensitive_finding:
        logfire.warning(
            "Sensitive input blocked by guardrails",
            category=sensitive_finding.category,
        )
        return True, sensitive_finding.message

    if _rails is None:
        logfire.warning("⚠️ Guardrails not initialised — skipping gate.")
        return False, None

    with logfire.span("🛡️ Guardrails Check"):
        result = _rails.generate(messages=[{"role": "user", "content": message}])

        # NeMo returns {'role': 'assistant', 'content': '...'} — extract text
        content = result.get("content", "") if isinstance(result, dict) else str(result)

        fired = any(indicator in content for indicator in RAIL_INDICATORS)

        if fired:
            # Do not log the raw prompt; it can contain data that a future rule
            # classifies as sensitive.
            logfire.info("🛡️ Guardrails fired.")
            return True, content

        logfire.info("✅ Guardrails passed.")
        return False, None


def guard_output(answer: str | None) -> tuple[bool, str]:
    """Prevent generated answers from exposing confidential data or PII."""
    is_safe, safe_answer = validate_output(answer)
    if not is_safe:
        logfire.warning("Sensitive model output withheld by guardrails.")
        return False, safe_answer or "I can't return that response safely."
    return True, safe_answer or ""
