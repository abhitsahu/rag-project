import os
import streamlit as st
import requests
import time
import uuid
import re
import logfire
from dotenv import load_dotenv


# Load environment variables explicitly from the root directory
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=env_path)


# Initialize Logfire
try:
    token = os.getenv("LOGFIRE_TOKEN")
    if not token:
        print("ERROR: LOGFIRE_TOKEN is empty or None!")
    logfire.configure(token=token)
    # logfire.instrument_requests() # Disabled due to OpenTelemetry bug on Windows: MeterProvider.get_meter() got multiple values for argument 'version'
    LOGFIRE_STATUS = "Connected & Tracing"
except Exception as e:
    print(f"Logfire Init Error in UI: {e}")
    LOGFIRE_STATUS = f"Standby (Error: {e})"
    


# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Enterprise Agentic RAG",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Keep the interface deliberately lean: this only refines Streamlit's native
# controls, so the application remains just as simple to operate and maintain.
st.markdown(
    """
    <style>
        :root {
            --surface: rgba(15, 23, 42, .72);
            --surface-strong: rgba(17, 27, 51, .94);
            --border: rgba(148, 163, 184, .16);
            --text: #e7edf8;
            --muted: #94a3b8;
            --accent: #7c8cff;
            --accent-bright: #64d9ff;
        }

        .stApp {
            background:
                radial-gradient(circle at 8% -12%, rgba(100, 217, 255, .19), transparent 28rem),
                radial-gradient(circle at 93% 8%, rgba(124, 140, 255, .17), transparent 30rem),
                #08111f;
            color: var(--text);
        }

        .main .block-container {
            max-width: 1120px;
            padding: clamp(1.5rem, 4vw, 3.5rem) clamp(1rem, 4vw, 3rem) 8rem;
        }

        h1 {
            margin: 0 0 2rem !important;
            font-size: clamp(1.8rem, 3.4vw, 2.7rem) !important;
            font-weight: 750 !important;
            letter-spacing: -.045em;
            background: linear-gradient(105deg, #f8fbff 15%, #b8c7ff 55%, #75e1ff);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        section[data-testid="stSidebar"] {
            background: rgba(8, 17, 31, .96);
            border-right: 1px solid var(--border);
        }

        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 1rem;
        }

        section[data-testid="stSidebar"] h1 {
            font-size: 1.35rem !important;
            margin-bottom: .65rem !important;
        }

        [data-testid="stSidebar"] hr {
            margin: 1.15rem 0;
            border-color: var(--border);
        }

        [data-testid="stAlert"] {
            border: 1px solid var(--border);
            border-radius: .85rem;
            background: rgba(30, 41, 59, .58);
            color: var(--text);
        }

        [data-testid="stChatMessage"] {
            margin: 0 0 1rem;
            padding: clamp(.85rem, 2vw, 1.2rem);
            border: 1px solid var(--border);
            border-radius: 1rem;
            background: var(--surface);
            box-shadow: 0 14px 35px rgba(0, 0, 0, .13);
            animation: message-in .28s ease-out both;
        }

        [data-testid="stChatMessageAvatar"] {
            background: linear-gradient(145deg, rgba(124, 140, 255, .3), rgba(100, 217, 255, .16));
            border: 1px solid rgba(148, 163, 184, .22);
        }

        [data-testid="stChatMessage"] p,
        [data-testid="stChatMessage"] li {
            line-height: 1.7;
        }

        [data-testid="stChatInput"] {
            border: 0 !important;
            border-radius: 1rem;
            background: rgba(15, 23, 42, .94);
            box-shadow: 0 15px 42px rgba(0, 0, 0, .26);
            transition: background .2s ease, box-shadow .2s ease, transform .2s ease;
        }

        [data-testid="stChatInput"]:focus-within {
            background: rgba(18, 30, 54, .98);
            box-shadow: 0 0 0 3px rgba(100, 217, 255, .12), 0 15px 42px rgba(0, 0, 0, .28);
            transform: translateY(-1px);
        }

        [data-testid="stChatInput"] [data-baseweb="textarea"],
        [data-testid="stChatInput"] textarea,
        [data-testid="stChatInput"] textarea:focus-visible {
            border: 0 !important;
            outline: 0 !important;
            box-shadow: none !important;
            background: transparent !important;
        }

        [data-testid="stChatInput"] textarea {
            color: var(--text);
            caret-color: var(--accent-bright);
        }

        [data-testid="stChatInput"] textarea::placeholder {
            color: #8090a8;
        }

        .stButton > button {
            min-height: 2.7rem;
            border: 1px solid rgba(148, 163, 184, .22);
            border-radius: .75rem;
            font-weight: 650;
            transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
        }

        .stButton > button[kind="primary"] {
            border: 0;
            color: #f8fbff;
            background: linear-gradient(120deg, #6678f5, #509be9);
            box-shadow: 0 10px 24px rgba(80, 113, 238, .26);
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            border-color: rgba(100, 217, 255, .5);
        }

        .stButton > button[kind="primary"]:hover {
            box-shadow: 0 14px 30px rgba(80, 113, 238, .38);
        }

        [data-testid="stStatusWidget"],
        [data-testid="stExpander"] {
            border: 1px solid var(--border);
            border-radius: .9rem;
            background: rgba(15, 23, 42, .62);
            overflow: hidden;
        }

        [data-testid="stExpander"] details summary {
            padding: .2rem 0;
            font-weight: 600;
        }

        [data-testid="stMarkdownContainer"] code {
            border: 1px solid rgba(148, 163, 184, .18);
            border-radius: .35rem;
            background: rgba(2, 6, 23, .62);
            color: #bdeaff;
        }

        [data-testid="stMarkdownContainer"] pre {
            border: 1px solid var(--border);
            border-radius: .75rem;
        }

        .app-footer {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            gap: .4rem 1rem;
            margin: 2.5rem 0 0;
            padding: 1.1rem 0 0;
            border-top: 1px solid var(--border);
            color: var(--muted);
            font-size: .82rem;
        }

        .app-footer a {
            color: #9bdff7;
            text-decoration: none;
        }

        .app-footer a:hover {
            color: #d4f4ff;
            text-decoration: underline;
        }

        button:focus-visible {
            outline: 2px solid var(--accent-bright) !important;
            outline-offset: 2px;
        }

        @keyframes message-in {
            from { opacity: 0; transform: translateY(7px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @media (max-width: 768px) {
            .main .block-container {
                padding: 1.25rem 1rem 7.25rem;
            }

            h1 {
                margin-bottom: 1.3rem !important;
            }

            [data-testid="stChatMessage"] {
                border-radius: .85rem;
            }
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration: .01ms !important;
                animation-iteration-count: 1 !important;
                scroll-behavior: auto !important;
                transition-duration: .01ms !important;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- AVATARS ---
AI_AVATAR = "🤖"
USER_AVATAR = "👤"


# --- SESSION MANAGEMENT ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    logfire.info(f"✨ New User Session Created: {st.session_state.session_id}")

if "messages" not in st.session_state:
    st.session_state.messages = []


_THINKING_BLOCK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


def public_response(content: str | None) -> str:
    """Defence-in-depth: never render a provider's hidden reasoning in the UI."""
    answer = _THINKING_BLOCK.sub("", content or "")
    if "<think>" in answer.lower():
        answer = re.split(r"<think>", answer, maxsplit=1, flags=re.IGNORECASE)[0]
    return answer.strip() or "No response."


# --- SIDEBAR ---
with st.sidebar:
    st.title("🧠 Agent OS")
    st.markdown("---")
    st.success(f"Logfire: {LOGFIRE_STATUS}")
    st.info(f"Memory ID: {st.session_state.session_id[:8]}")
    
    if st.button("🗑️ Clear History & Memory", width="stretch", type="primary"):
        logfire.warn(f"🗑️ Memory Wipe Triggered for session: {st.session_state.session_id}")
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

# --- MAIN CHAT ---
st.title("🤖 Enterprise Agentic Assistant")


def render_assistant_details(message: dict) -> None:
    """Show high-level workflow metadata without exposing model reasoning."""
    steps = message.get("thought_process", [])
    if steps:
        with st.expander("Thinking", expanded=False):
            st.caption("Workflow summary — internal model reasoning is kept private.")
            for step in steps:
                st.caption(f"• {step}")

    sources = message.get("sources", [])
    if sources:
        with st.expander(f"Retrieved context ({len(sources)} chunks)", expanded=False):
            for index, source in enumerate(sources, start=1):
                with st.expander(f"Source {index}", expanded=False):
                    st.write(source)


# Display history
for message in st.session_state.messages:
    avatar = AI_AVATAR if message["role"] == "assistant" else USER_AVATAR
    with st.chat_message(message["role"], avatar=avatar):
        content = public_response(message["content"]) if message["role"] == "assistant" else message["content"]
        st.markdown(content)
        if message["role"] == "assistant":
            render_assistant_details(message)

# Chat Input
if prompt := st.chat_input("Ask about your documentation..."):
    # START TRACE: User Interaction
    with logfire.span("💬 User Chat Interaction", user_query=prompt, session_id=st.session_state.session_id):
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(prompt)

        # Assistant Response
        with st.chat_message("assistant", avatar=AI_AVATAR):
            try:
                with st.spinner("Thinking…"):
                    # DISTRIBUTED TRACE: Calling Backend
                    with logfire.span("📡 Calling RAG Backend"):
                        # Get backend URL from env, or default to local if not set
                        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
                        url = f"{base_url}/query"
                        payload = {"q": prompt, "thread_id": st.session_state.session_id}
                        response = requests.post(url, json=payload, timeout=60)
                        response.raise_for_status()
                        data = response.json()
            except requests.RequestException as e:
                logfire.error(f"❌ UI-Backend Connection Failed: {e}")
                st.error("Backend Offline. Please check that the API is running.")
                st.stop()

            # Final Answer Streaming
            answer_placeholder = st.empty()
            full_answer = public_response(data.get("answer"))
            
            curr_text = ""
            for char in full_answer:
                curr_text += char
                answer_placeholder.markdown(curr_text + "▌")
                time.sleep(0.005)
            
            answer_placeholder.markdown(full_answer)
            render_assistant_details(data)
            st.session_state.messages.append({
                "role": "assistant",
                "content": full_answer,
                "thought_process": data.get("thought_process", []),
                "sources": data.get("sources", []),
            })
            logfire.info("✅ Chat cycle completed successfully.")

st.markdown(
    """
    <footer class="app-footer">
        <span>© 2026 Enterprise Agentic RAG</span>
        <span>Need help? Contact <a href="mailto:sahuabhit27@gmail.com">sahuabhit27@gmail.com</a></span>
    </footer>
    """,
    unsafe_allow_html=True,
)
