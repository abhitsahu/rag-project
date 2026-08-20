import logfire
import re
from app.agents.state import AgentState
from app.config import settings
from app.gateway import portkey_client, extract_cache_status


_THINKING_BLOCK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


def _public_answer(content: str | None) -> str:
    """Remove model reasoning markup before it reaches the chat or memory."""
    answer = _THINKING_BLOCK.sub("", content or "")
    if "<think>" in answer.lower():
        # Be conservative if a provider returns an incomplete thinking block.
        answer = re.split(r"<think>", answer, maxsplit=1, flags=re.IGNORECASE)[0]
    return answer.strip() or "I couldn't generate a response. Please try again."


def generate_node(state: AgentState):
    """
    Synthesizes a response using both Documentation Context AND Conversation History.
    Uses the native Portkey client (not LangChain) so we can read the
    x-portkey-cache-status response header and surface Cache: Hit in the UI.
    """
    query = state["current_query"]

    history_str = ""
    for msg in state["messages"][:-1]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n"

    user_msg = state["messages"][-1]["content"] if state["messages"] else ""

    if query == "CONVERSATIONAL":
        logfire.info("Generating conversational response using memory.")
        prompt = f"""
        You are a friendly and helpful Enterprise AI Assistant.
        Answer the user's latest message using the CONVERSATION HISTORY below.
        Return only the response the user should read. Never reveal analysis,
        chain-of-thought, planning notes, or <think> tags.

        CONVERSATION HISTORY:
        {history_str}

        LATEST MESSAGE:
        "{user_msg}"
        """
    else:
        logfire.info("Generating technical RAG response.")
        max_context_chars = 25000
        full_context = ""

        for doc in state["documents"]:
            if len(full_context) + len(doc) < max_context_chars:
                full_context += doc + "\n\n"
            else:
                logfire.warning("Context truncated to fit Groq TPM limits.")
                break

        prompt = f"""
        You are a Senior Technical Architect.
        Answer the question using the TECHNICAL CONTEXT provided.
        Return only the response the user should read. Never reveal analysis,
        chain-of-thought, planning notes, or <think> tags.

        TECHNICAL CONTEXT:
        {full_context}

        CONVERSATION HISTORY:
        {history_str}

        USER QUESTION:
        "{user_msg}"
        """

    with logfire.span("✍️ LLM Synthesis"):
        try:
            response = portkey_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=f"@{settings.GROQ_SLUG}/{settings.GROQ_MODEL}",
                temperature=0.1,
                reasoning_format="hidden",
            )
            content = _public_answer(response.choices[0].message.content)
            cache_status = extract_cache_status(response)
            is_cache_hit = cache_status == "HIT"

            if is_cache_hit:
                logfire.info("⚡ Gateway Cache Hit — response served from Portkey cache.")
                plan_update = state["plan"] + ["Cache: Hit ⚡"]
                status = "Cache hit — instant response."
            else:
                logfire.info("✅ Response synthesised via LLM.")
                plan_update = state["plan"]
                status = "Response generated."

            return {
                "final_answer": content,
                "status": status,
                "plan": plan_update,
                "messages": [{"role": "assistant", "content": content}]
            }

        except Exception as e:
            logfire.error(f"LLM Generation failed: {e}")
            raise e
