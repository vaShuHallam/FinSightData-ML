"""
FinSight AI — Entity Explorer page (REQ-6).

Lets users drill into a single entity's signal history and sentiment
trends: a sentiment-over-time chart, a daily positive/negative/neutral
distribution, recent articles, full signal history, and an entity
metadata card with a one-click "Add to Watchlist" action.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from Dashboard.services.dashboard_service import get_active_entities
from Dashboard.services.entity_explorer_service import (
    TIME_RANGE_TO_HOURS,
    add_to_watchlist,
    get_entity_metadata,
    get_recent_articles,
    get_signal_distribution,
    get_signal_history,
    get_sentiment_history,
)

st.set_page_config(page_title="Entity Explorer", page_icon="🔍", layout="wide")
st.title("🔍 Entity Explorer")

SESSION_ID = "demo-user"  # no login system yet — see README "Scope decisions"

entities = get_active_entities()
if not entities:
    st.info("No entities found. Run seed_entities.py first.")
    st.stop()

entity_names = [e["name"] for e in entities]
selected_name = st.selectbox("Select Entity", options=entity_names)
selected_id = next(e["entity_id"] for e in entities if e["name"] == selected_name)

col1, col2, col3 = st.columns(3)
with col1:
    time_range = st.radio("Time range", options=list(TIME_RANGE_TO_HOURS.keys()), index=1)
    hours = TIME_RANGE_TO_HOURS[time_range]
with col2:
    window_choice = st.selectbox("Window size (optional)", options=["All", "6 hours", "12 hours", "24 hours"])
    window_size_hours = {"All": None, "6 hours": 6, "12 hours": 12, "24 hours": 24}[window_choice]
with col3:
    st.write("")  # vertical alignment spacer
    st.write("")
    if st.button("⭐ Add to Watchlist"):
        success, message = add_to_watchlist(selected_id, SESSION_ID)
        (st.success if success else st.error)(message)

# --- Entity metadata card ---
metadata = get_entity_metadata(selected_id, SESSION_ID)
if metadata:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Type", metadata["entity_type"])
    m2.metric("Sector", metadata["sector"] or "—")
    m3.metric("Ticker", metadata["ticker_symbol"] or "—")
    m4.metric("On Your Watchlist", "Yes" if metadata["is_on_watchlist"] else "No")

st.divider()

# --- Sentiment history chart ---
st.subheader("Sentiment History")
history = get_sentiment_history(selected_id, hours, window_size_hours)
if history:
    df = pd.DataFrame(history)
    fig = px.line(df, x="timestamp", y="score", markers=True,
                 labels={"score": "Aggregate Sentiment Score", "timestamp": "Time"})
    fig.update_layout(yaxis_range=[-1, 1])
    st.plotly_chart(fig, width="stretch")
else:
    st.info("No signals in this time range yet.")

# --- Signal distribution chart ---
st.subheader("Signal Distribution (articles per day)")
distribution = get_signal_distribution(selected_id, hours)
if distribution:
    df = pd.DataFrame(distribution).melt(
        id_vars="date", value_vars=["positive", "negative", "neutral"],
        var_name="Sentiment", value_name="Count",
    )
    fig = px.bar(df, x="date", y="Count", color="Sentiment", barmode="stack",
                color_discrete_map={"positive": "#2ecc71", "negative": "#e74c3c", "neutral": "#95a5a6"})
    st.plotly_chart(fig, width="stretch")
else:
    st.info("No articles in this time range yet.")

st.divider()

# --- Recent articles table ---
st.subheader("Recent Articles")
articles = get_recent_articles(selected_id, limit=20)
if articles:
    df = pd.DataFrame(articles).rename(columns={
        "headline": "Headline", "published_at": "Published At",
        "sentiment_label": "Sentiment", "confidence": "Confidence",
    })
    st.dataframe(df, width="stretch", hide_index=True)
else:
    st.info("No articles found for this entity.")

# --- Signal history table ---
st.subheader("Signal History")
signal_history = get_signal_history(selected_id)
if signal_history:
    df = pd.DataFrame(signal_history).rename(columns={
        "signal_strength": "Strength", "aggregate_score": "Score", "article_count": "Articles",
        "window_hours": "Window", "window_start": "Window Start", "window_end": "Window End",
    })
    st.dataframe(df, width="stretch", hide_index=True)
else:
    st.info("No signals generated for this entity yet.")