"""
FinSight AI — Watchlist Management page (REQ-3).

Lets users see, add to, edit, and remove entries from their watchlist —
the entities and thresholds that drive alert generation.
"""

import streamlit as st

from app.services.dashboard_service import get_active_entities
from app.services.watchlist_service import (
    WINDOW_SIZE_OPTIONS,
    add_watchlist_entry,
    get_watchlist,
    remove_watchlist_entry,
    update_alert_threshold,
)

st.set_page_config(page_title="Watchlist", page_icon="⭐", layout="wide")
st.title("⭐ Watchlist Management")

SESSION_ID = "demo-user"  # no login system yet — see README "Scope decisions"

# --- Add Entity Form ---
with st.expander("➕ Add Entity to Watchlist", expanded=False):
    entities = get_active_entities()
    entity_names = [e["name"] for e in entities]

    with st.form("add_watchlist_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_name = st.selectbox("Select Entity", options=entity_names)
        with col2:
            threshold = st.number_input("Alert Threshold", min_value=0.0, max_value=1.0,
                                        value=0.60, step=0.05)
        with col3:
            window_size = st.selectbox("Window Size (hours)", options=WINDOW_SIZE_OPTIONS, index=0)

        submitted = st.form_submit_button("Add to Watchlist")
        if submitted:
            entity_id = next(e["entity_id"] for e in entities if e["name"] == selected_name)
            success, message = add_watchlist_entry(entity_id, SESSION_ID, threshold, window_size)
            (st.success if success else st.error)(message)

st.divider()

# --- Watchlist Table ---
st.subheader("Your Watchlist")
watchlist = get_watchlist(SESSION_ID)

if not watchlist:
    st.info("Your watchlist is empty. Add an entity above to start monitoring it.")
else:
    header = st.columns([3, 2, 2, 2])
    header[0].markdown("**Entity**")
    header[1].markdown("**Alert Threshold**")
    header[2].markdown("**Window Size**")
    header[3].markdown("**Actions**")

    for entry in watchlist:
        row = st.columns([3, 2, 2, 2])
        row[0].write(entry["entity_name"])

        new_threshold = row[1].number_input(
            "Threshold", min_value=0.0, max_value=1.0, value=entry["alert_threshold"],
            step=0.05, key=f"threshold_{entry['watchlist_id']}", label_visibility="collapsed",
        )
        if new_threshold != entry["alert_threshold"]:
            update_alert_threshold(entry["watchlist_id"], new_threshold)
            st.rerun()

        row[2].write(f"{entry['window_size_hours']}h")

        if row[3].button("🗑️ Remove", key=f"remove_{entry['watchlist_id']}"):
            remove_watchlist_entry(entry["watchlist_id"])
            st.rerun()