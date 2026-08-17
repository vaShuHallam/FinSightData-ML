"""
FinSight AI — main Dashboard page (REQ-2), the landing screen.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

#!import all functions from dashboard_service
from app.services.dashboard_service import (
    WINDOW_LABEL_TO_HOURS,
    get_active_entities,
    get_pipeline_status,
    get_sentiment_timeline,
    get_signal_summary,
    get_top_signals,
    get_unacknowledged_alert_count,
    get_watchlist_signals,
)

st.set_page_config(page_title="FinSight AI — Dashboard", page_icon="📊", layout="wide")

# No login system yet — every user shares this single demo session_id.
SESSION_ID = "demo-user"


# --- Data loading, cached briefly so widget interactions don't hammer the DB ---
# 
@st.cache_data(ttl=30)
def _load_summary(hours: int):
    # Load the sentiment summary for the selected time period.
    return get_signal_summary(hours=hours)


@st.cache_data(ttl=30)
def _load_timeline(entity_ids: tuple[int, ...], hours: int):
    # Load sentiment signals for the selected entities and time period.
    return get_sentiment_timeline(entity_ids=list(entity_ids) or None, hours=hours)


@st.cache_data(ttl=30)
def _load_top_signals():
    # Load the 20 strongest/latest signals for the dashboard.
    return get_top_signals(limit=20)


@st.cache_data(ttl=30)
def _load_watchlist_signals(session_id: str):
     # Load the active watchlist signals for the current user/session.
    return get_watchlist_signals(session_id)


@st.cache_data(ttl=30)
def _load_alert_count():
     # Load the number of unacknowledged alerts.
    return get_unacknowledged_alert_count()


@st.cache_data(ttl=30)
def _load_pipeline_status():
    # Load the most recent pipeline run and its current status.
    return get_pipeline_status()


@st.cache_data(ttl=300)
def _load_entities():
    # Load all active entities used by the entity-selection widgets.
    return get_active_entities()


# --- Sidebar: entity filter, refresh, watchlist panel ---
st.sidebar.title("FinSight AI")

entities = _load_entities()
entity_name_to_id = {e["name"]: e["entity_id"] for e in entities}
selected_names = st.sidebar.multiselect("Filter by entity", options=list(entity_name_to_id.keys()))
selected_ids = tuple(entity_name_to_id[n] for n in selected_names)

if st.sidebar.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
st.sidebar.subheader("Your Watchlist")
watchlist_rows = _load_watchlist_signals(SESSION_ID)
if not watchlist_rows:
    st.sidebar.caption("No entities on your watchlist yet.")
else:
    for row in watchlist_rows:
        score = row["aggregate_score"]
        strength = row["signal_strength"] or "No signal yet"
        score_str = f"{score:+.2f}" if score is not None else "—"
        st.sidebar.markdown(f"**{row['entity']}** — {strength} ({score_str})")


# --- Active alerts banner ---
alert_count = _load_alert_count()
if alert_count > 0:
    st.warning(f"🔔 **{alert_count} unacknowledged alert{'s' if alert_count != 1 else ''}** — "
               f"see the Alert Centre page in the sidebar.")

# --- Pipeline status indicator ---
status = _load_pipeline_status()
if status:
    icon = "✅" if status["status"] == "completed" else "❌"
    st.caption(f"{icon} Last pipeline run: **{status['run_type']}** — "
               f"{status['status']} at {status['completed_at']}")
else:
    st.caption("No pipeline runs recorded yet.")

st.title("📊 Dashboard")

# --- Time window selector ---
window_label = st.radio("Aggregation window", options=list(WINDOW_LABEL_TO_HOURS.keys()),
                        index=2, horizontal=True)
window_hours = WINDOW_LABEL_TO_HOURS[window_label]

# --- Signal summary cards ---
summary = _load_summary(window_hours)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Signals", summary["total_signals"])
c2.metric("Bullish", summary["bullish_signals"])
c3.metric("Bearish", summary["bearish_signals"])
c4.metric("Neutral", summary["neutral_signals"])
c5.metric("Articles Processed", summary["articles_processed"])

st.divider()

# --- Sentiment timeline chart ---
st.subheader("Sentiment Timeline")
timeline = _load_timeline(selected_ids, window_hours)
if timeline:
    df = pd.DataFrame(timeline)
    fig = px.line(df, x="timestamp", y="score", color="entity", markers=True,
                  labels={"score": "Aggregate Sentiment Score", "timestamp": "Time"})
    fig.update_layout(yaxis_range=[-1, 1])
    st.plotly_chart(fig, width="stretch")
else:
    st.info("No signals in this window yet. Run the pipeline (ingestion → sentiment → "
            "signals) to populate this chart.")

st.divider()

# --- Top signals feed ---
st.subheader("Top Signals")
top_signals = _load_top_signals()
if top_signals:
    df = pd.DataFrame(top_signals)
    df = df.rename(columns={
        "entity": "Entity", "signal_strength": "Strength",
        "article_count": "Articles", "aggregate_score": "Score", "window_end": "As of",
    })
    st.dataframe(df, width="stretch", hide_index=True)
else:
    st.info("No signals yet.")