import uuid

import streamlit as st


def get_session_id() -> str:
    """
    Returns a stable per-browser-session ID for local usage.

    Query param `session_id` can be used to force a stable value across tabs:
    http://localhost:8501/?session_id=my-user
    """
    query_session = st.query_params.get("session_id")
    if query_session:
        st.session_state["finsight_session_id"] = str(query_session)

    if "finsight_session_id" not in st.session_state:
        st.session_state["finsight_session_id"] = f"local-{uuid.uuid4().hex[:12]}"

    return st.session_state["finsight_session_id"]
