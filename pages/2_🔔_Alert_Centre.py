"""
FinSight AI — Alert Centre page (REQ-5).

Active Alerts get full interactive rows (acknowledge, rate relevance, view
the triggering signal inline). All Alerts is a filterable read-only history.
"""

import pandas as pd
import streamlit as st

from Dashboard.services.alert_centre_service import (
    ALERT_TYPE_OPTIONS,
    STATUS_OPTIONS,
    acknowledge_alert,
    acknowledge_all_active,
    get_active_alerts,
    get_all_alerts,
    get_existing_rating,
    get_signal_for_alert,
    save_relevance_rating,
)
from Dashboard.services.dashboard_service import get_active_entities

st.set_page_config(page_title="Alert Centre", page_icon="🔔", layout="wide")
st.title("🔔 Alert Centre")

# A message set just before st.rerun() never actually reaches the browser,
# since the rerun happens before that frame renders — carry it across the
# rerun via session_state instead, and show/clear it here at the top.
if st.session_state.get("flash_message"):
    st.success(st.session_state.flash_message)
    st.session_state.flash_message = None

# --- Active Alerts ---
st.subheader("Active Alerts")
active_alerts = get_active_alerts()

if not active_alerts:
    st.info("No active alerts right now.")
else:
    if st.button(f"✅ Acknowledge All ({len(active_alerts)})"):
        count = acknowledge_all_active()
        st.session_state.flash_message = f"Acknowledged {count} alert(s)."
        st.rerun()

    for alert in active_alerts:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 2])
            c1.markdown(f"**{alert['entity_name']}** — {alert['alert_type']}")
            c2.write(f"Score: {alert['aggregate_score']:+.3f} (threshold {alert['threshold']:.2f})")
            c3.caption(f"Created: {alert['created_at']}")

            st.caption(f"📰 {alert['trigger_headline'] or '(no headline recorded)'}")

            r1, r2, r3 = st.columns([2, 1, 1])
            with r1:
                existing = get_existing_rating(alert["alert_id"])
                rating = st.select_slider(
                    "Rate relevance", options=[1, 2, 3, 4, 5],
                    value=existing or 3, format_func=lambda x: "⭐" * x,
                    key=f"rate_{alert['alert_id']}", label_visibility="collapsed",
                )
                if rating != (existing or 3) or existing is None:
                    if st.button("Submit rating", key=f"submit_rate_{alert['alert_id']}"):
                        success, message = save_relevance_rating(alert["alert_id"], rating)
                        (st.success if success else st.error)(message)
            with r2:
                if st.button("Acknowledge", key=f"ack_{alert['alert_id']}"):
                    acknowledge_alert(alert["alert_id"])
                    st.rerun()
            with r3:
                with st.expander("View Signal"):
                    signal = get_signal_for_alert(alert["signal_id"])
                    if signal:
                        st.write(f"**{signal['signal_strength']}** — score {signal['aggregate_score']:+.3f}")
                        st.write(f"{signal['article_count']} articles "
                                f"({signal['positive_count']} pos / {signal['negative_count']} neg / "
                                f"{signal['neutral_count']} neu)")
                        st.caption(f"Window: {signal['window_start']} → {signal['window_end']}")
                    else:
                        st.caption("Signal not found.")

st.divider()

# --- All Alerts (filterable history) ---
st.subheader("All Alerts")

search = st.text_input("Search by entity name", placeholder="e.g. Apple")

col1, col2, col3, col4 = st.columns(4)
with col1:
    alert_types = st.multiselect("Alert type", options=ALERT_TYPE_OPTIONS)
with col2:
    entities = get_active_entities()
    entity_names = ["All"] + [e["name"] for e in entities]
    entity_choice = st.selectbox("Entity", options=entity_names)
    entity_id = None if entity_choice == "All" else next(
        e["entity_id"] for e in entities if e["name"] == entity_choice
    )
with col3:
    status = st.selectbox("Status", options=STATUS_OPTIONS)
with col4:
    date_range = st.date_input("Date range", value=(), format="YYYY-MM-DD")
    date_from = date_range[0] if len(date_range) >= 1 else None
    date_to = date_range[1] if len(date_range) >= 2 else None

all_alerts = get_all_alerts(
    search=search, alert_types=alert_types or None, entity_id=entity_id,
    date_from=date_from, date_to=date_to, status=status,
)

st.caption(f"{len(all_alerts)} alert(s) matching current filters")

if all_alerts:
    df = pd.DataFrame(all_alerts).rename(columns={
        "entity_name": "Entity Name", "alert_type": "Alert Type",
        "trigger_headline": "Trigger Headline", "aggregate_score": "Aggregate Score",
        "threshold": "Threshold", "created_at": "Created At", "status": "Status",
    })[["Entity Name", "Alert Type", "Trigger Headline", "Aggregate Score",
        "Threshold", "Created At", "Status"]]
    st.dataframe(df, width="stretch", hide_index=True)
else:
    st.info("No alerts match your current filters.")