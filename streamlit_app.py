# streamlit_app.py
# Energy Sector Cybersecurity Risk Mitigation Bot (RAG UI)

import json
import time
import uuid
import streamlit as st  # type: ignore[import]
from app.rag import generate_grounded_response

st.set_page_config(
    page_title="Energy Cybersecurity RAG",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1180px;
        padding-top: 1.4rem;
        padding-bottom: 3rem;
    }
    [data-testid="stSidebar"] {
        background: #f7f8fa;
        border-right: 1px solid #e6e9ef;
    }
    .app-header {
        border: 1px solid #d9dee8;
        border-radius: 8px;
        padding: 1.05rem 1.2rem;
        background: #ffffff;
        margin-bottom: 1rem;
    }
    .app-header h1 {
        margin: 0 0 .25rem 0;
        font-size: 1.75rem;
        line-height: 1.2;
        letter-spacing: 0;
        color: #162033;
    }
    .app-header p {
        margin: 0;
        color: #596579;
        font-size: .98rem;
    }
    .quick-row {
        margin-top: .4rem;
        margin-bottom: .6rem;
    }
    div[data-testid="stChatMessage"] {
        border: 1px solid #e1e5ec;
        border-radius: 8px;
        background: #ffffff;
        padding: .35rem .55rem;
    }
    .stButton > button {
        border-radius: 6px;
        border-color: #cfd6e2;
        background: #ffffff;
        color: #1f2a3d;
        min-height: 2.35rem;
    }
    .stButton > button:hover {
        border-color: #6f7d94;
        color: #111827;
    }
    h2, h3 {
        letter-spacing: 0;
        color: #162033;
    }
    div[data-testid="stCaptionContainer"] {
        color: #5f6b7a;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

QUICK_PROMPTS = [
    "Identify the most common attack vectors used against energy-sector ICS/OT systems.",
    "Using Energy Sector sources, categorize top cybersecurity risks by OT, IT, and cyber-physical systems.",
    "Draft policy recommendations to reduce insecure remote access risk for electric utilities.",
]

# =========================
# State
# =========================
def _init_state():
    if "conversations" not in st.session_state:
        st.session_state.conversations = {}

    if "active_chat_id" not in st.session_state:
        st.session_state.active_chat_id = None

    if "settings" not in st.session_state:
        st.session_state.settings = {
            "top_k": 8,
            "min_recurring_reviews": 2,
            "debug_on": False,
        }

    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None


def _new_chat():
    cid = str(uuid.uuid4())
    st.session_state.conversations[cid] = {
        "title": "New cybersecurity query",
        "messages": [],
        "created": time.time(),
    }
    st.session_state.active_chat_id = cid


def _ensure_active():
    if not st.session_state.conversations:
        _new_chat()
        return

    if st.session_state.active_chat_id not in st.session_state.conversations:
        newest = max(
            st.session_state.conversations.items(),
            key=lambda x: x[1]["created"]
        )[0]
        st.session_state.active_chat_id = newest


def _sorted():
    return sorted(
        st.session_state.conversations.items(),
        key=lambda x: x[1]["created"],
        reverse=True
    )


def _delete(cid):
    st.session_state.conversations.pop(cid, None)
    if not st.session_state.conversations:
        _new_chat()
    else:
        _ensure_active()


# =========================
# Init
# =========================
_init_state()
if not st.session_state.active_chat_id:
    _new_chat()
_ensure_active()

cid = st.session_state.active_chat_id
convo = st.session_state.conversations[cid]

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.header("Energy Cyber RAG")

    if st.button("New analysis", use_container_width=True):
        _new_chat()
        st.rerun()

    st.divider()

    ids = [i[0] for i in _sorted()]

    selected = st.radio(
        "History",
        ids,
        index=ids.index(cid) if cid in ids else 0,
        format_func=lambda x: st.session_state.conversations[x]["title"],
    )
    st.session_state.active_chat_id = selected
    convo = st.session_state.conversations[selected]

    st.divider()

    with st.expander("⚙️ Settings"):
        st.session_state.settings["top_k"] = st.slider(
            "Retrieved evidence chunks",
            3, 30,
            st.session_state.settings["top_k"]
        )
        st.session_state.settings["debug_on"] = st.toggle(
            "Debug mode",
            st.session_state.settings["debug_on"]
        )

    st.divider()
    st.caption("Best for NERC CIP, CISA, DOE C2M2, NIST, OT/ICS risk, and energy-sector policy development.")

# =========================
# Header
# =========================
st.markdown(
    """
    <div class="app-header">
        <h1>Energy Sector Cybersecurity Risk Mitigation Assistant</h1>
        <p>Grounded policy and risk analysis over NERC CIP, CISA, DOE, NIST, FERC, and OT/ICS cybersecurity sources.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="quick-row"></div>', unsafe_allow_html=True)
quick_cols = st.columns(3)
for idx, quick_prompt in enumerate(QUICK_PROMPTS):
    with quick_cols[idx]:
        if st.button(quick_prompt, use_container_width=True):
            st.session_state.pending_prompt = quick_prompt
            st.rerun()

# =========================
# Render history
# =========================
for m in convo["messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("Ask about energy-sector cyber risk, policy, controls, or compliance gaps...")
active_prompt = prompt or st.session_state.pending_prompt
if st.session_state.pending_prompt:
    st.session_state.pending_prompt = None

# =========================
# Rendering helpers
# =========================
def _source_index(out: dict) -> dict:
    index = {}
    for source in out.get("retrieval_sources", []):
        if isinstance(source, dict) and source.get("chunk_id"):
            index[source["chunk_id"]] = source
    for source in out.get("sources", []):
        if isinstance(source, dict) and source.get("chunk_id"):
            index[source["chunk_id"]] = source
    return index


def _source_label(source: dict) -> str:
    title = source.get("document_title") or source.get("source_file") or source.get("source_url") or "Source"
    page = source.get("page_number")
    if page not in (None, "", 0, "0"):
        return f"{title}, p. {page}"
    return str(title)


def _render_source_list(source_items: list):
    seen = set()
    rendered = False

    for source in source_items:
        if not isinstance(source, dict):
            continue

        url = source.get("source_url")
        label = _source_label(source)
        key = url or source.get("source_file") or source.get("document_title") or label
        if key in seen:
            continue
        seen.add(key)
        rendered = True

        if url:
            st.markdown(f"- [{label}]({url})")
        else:
            source_file = source.get("source_file")
            if source_file:
                st.markdown(f"- {label} (`{source_file}`)")
            else:
                st.markdown(f"- {label}")

    if not rendered:
        st.write("_No sources returned._")


def _sources_for_ids(source_ids: list, index: dict) -> list:
    sources = []
    for source_id in source_ids or []:
        if isinstance(source_id, dict):
            sources.append(source_id)
        elif source_id in index:
            sources.append(index[source_id])
    return sources


def render_response(out: dict):
    source_index = _source_index(out)
    attack_vectors = out.get("attack_vectors", [])
    risk_categories = out.get("risk_categories", [])
    has_structured_findings = bool(attack_vectors or risk_categories)

    summary = out.get("answer_summary") or out.get("summary") or ""
    if summary:
        st.subheader("Answer")
        st.write(summary)
        st.divider()

    points = out.get("key_points", [])
    if points and not has_structured_findings:
        st.subheader("Key Points")
        for p in points:
            if isinstance(p, dict):
                text = p.get("point") or p.get("text") or str(p)
                st.markdown(f"- **{text}**")
                point_sources = _sources_for_ids(p.get("source_chunk_ids", []), source_index)
                if point_sources:
                    _render_source_list(point_sources)
            else:
                st.markdown(f"- **{p}**")

        st.divider()

    if attack_vectors:
        st.subheader("Attack Vectors")
        for vector in attack_vectors:
            if not isinstance(vector, dict):
                st.markdown(f"- {vector}")
                continue
            st.markdown(f"- **{vector.get('vector', 'Attack vector')}**")
            if vector.get("how_it_is_used"):
                st.write(vector.get("how_it_is_used"))
            if vector.get("typical_targets"):
                st.caption(f"Typical targets: {vector.get('typical_targets')}")
            if vector.get("mitigation_focus"):
                st.caption(f"Mitigation focus: {vector.get('mitigation_focus')}")
            vector_sources = vector.get("sources") or _sources_for_ids(vector.get("evidence", []), source_index)
            if vector_sources:
                _render_source_list(vector_sources)
        st.divider()

    if risk_categories:
        st.subheader("Risk Categories")
        for category in risk_categories:
            if not isinstance(category, dict):
                continue
            st.markdown(f"**{category.get('category', 'Risk Category')}**")
            for risk in category.get("risks", []) or []:
                if not isinstance(risk, dict):
                    st.markdown(f"- {risk}")
                    continue
                st.markdown(f"- **{risk.get('risk', 'Risk')}**")
                if risk.get("why_it_matters"):
                    st.write(risk.get("why_it_matters"))
                if risk.get("mitigation_focus"):
                    st.caption(f"Mitigation focus: {risk.get('mitigation_focus')}")
                risk_sources = risk.get("sources") or _sources_for_ids(risk.get("evidence", []), source_index)
                if risk_sources:
                    _render_source_list(risk_sources)
        st.divider()

    reqs = out.get("key_requirements", [])
    if reqs:
        st.subheader("Key Requirements")
        for r in reqs:
            if isinstance(r, dict):
                st.markdown(f"- **{r.get('requirement', '')}**")
                _render_source_list(_sources_for_ids(r.get("evidence", []), source_index))
            else:
                st.markdown(f"- **{r}**")

        st.divider()

    recs = out.get("policy_recommendations", [])
    if recs:
        st.subheader("🛡️ Policy Recommendations")
        for r in recs:
            if isinstance(r, dict):
                st.markdown(f"**→ {r.get('recommendation', '')}**")
                st.write(r.get("justification", ""))
                _render_source_list(_sources_for_ids(r.get("evidence", []), source_index))
            elif isinstance(r, str):
                st.markdown(f"**→ {r}**")
            else:
                st.write(r)

        st.divider()

    draft = out.get("draft_policy_language", [])
    if draft:
        st.subheader("📄 Draft Policy Language")
        for d in draft:
            if isinstance(d, dict):
                st.markdown(f"### {d.get('section', 'Section')}")
                st.code(d.get("text", ""))
            else:
                st.code(str(d))
        st.divider()

    st.subheader("Sources")
    source_items = []
    for r in out.get("key_requirements", []):
        if isinstance(r, dict):
            source_items.extend(_sources_for_ids(r.get("evidence", []), source_index))

    for r in out.get("policy_recommendations", []):
        if isinstance(r, dict):
            source_items.extend(_sources_for_ids(r.get("evidence", []), source_index))

    for p in out.get("key_points", []):
        if isinstance(p, dict):
            source_items.extend(_sources_for_ids(p.get("source_chunk_ids", []), source_index))

    for s in out.get("sources", []):
        if isinstance(s, dict):
            source_items.append(s)
        elif isinstance(s, str):
            source_items.extend(_sources_for_ids([s], source_index))

    if not source_items:
        source_items = out.get("retrieval_sources", [])
    _render_source_list(source_items)

    if st.session_state.settings["debug_on"]:
        with st.expander("Debug JSON"):
            st.code(json.dumps(out, indent=2))


# =========================
# Chat flow
# =========================
if active_prompt:
    convo["messages"].append({"role": "user", "content": active_prompt})

    with st.chat_message("user"):
        st.markdown(active_prompt)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving evidence, refreshing web sources, and building grounded analysis..."):
            out = generate_grounded_response(
                query=active_prompt,
                top_k=st.session_state.settings["top_k"],
                min_recurring_reviews=2,
                include_debug=st.session_state.settings["debug_on"],
            )

        if "error" in out:
            st.error(out["error"])
            st.code(out.get("raw_output", ""))
        else:
            render_response(out)

            convo["messages"].append({
                "role": "assistant",
                "content": out.get("answer_summary", "") or out.get("summary", "")
            })
