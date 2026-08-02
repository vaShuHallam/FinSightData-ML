"""
FinSight AI — Signal Feed page (REQ-4).

Shows every signal across all entities and time windows, with search,
filtering, sorting, CSV export, and a drill-down Signal Detail view.
"""

import pandas as pd
import streamlit as st

from app.services.signal_feed_service import (
    ENTITY_TYPE_OPTIONS,
    SORT_OPTIONS,
    STRENGTH_OPTIONS,
    get_all_signals,
    get_contributing_articles,
    get_signal_detail,
)

st.set_page_config(page_title="Signal Feed", page_icon="📡", layout="wide")
st.title("📡 Signal Feed")

# --- Search + filter panel ---
search = st.text_input("Search by entity name", placeholder="e.g. Apple")

col1, col2, col3, col4 = st.columns(4)
with col1:
    strengths = st.multiselect("Signal strength", options=STRENGTH_OPTIONS)
with col2:
    entity_types = st.multiselect("Entity type", options=ENTITY_TYPE_OPTIONS)
with col3:
    window_choice = st.selectbox("Window size", options=["All", "6h", "12h", "24h"])
    window_hours = {"All": None, "6h": 6, "12h": 12, "24h": 24}[window_choice]
with col4:
    sort_by = st.selectbox("Sort by", options=SORT_OPTIONS)

date_range = st.date_input("Date range (window end)", value=(), format="YYYY-MM-DD")
date_from = date_range[0] if len(date_range) >= 1 else None
date_to = date_range[1] if len(date_range) >= 2 else None

# --- Fetch + display ---
signals = get_all_signals(
    search=search,
    strengths=strengths or None,
    entity_types=entity_types or None,
    window_hours=window_hours,
    date_from=date_from,
    date_to=date_to,
    sort_by=sort_by,
)

st.caption(f"{len(signals)} signal(s) matching current filters")

if signals:
    df = pd.DataFrame(signals)
    display_df = df.rename(columns={
        "entity_name": "Entity Name", "entity_type": "Entity Type",
        "signal_strength": "Signal Strength", "aggregate_score": "Aggregate Score",
        "article_count": "Article Count", "window_hours": "Window",
        "window_start": "Window Start", "window_end": "Window End",
    })[["Entity Name", "Entity Type", "Signal Strength", "Aggregate Score",
        "Article Count", "Window", "Window Start", "Window End"]]

    st.dataframe(display_df, width="stretch", hide_index=True)

    st.download_button(
        "⬇️ Export filtered results as CSV",
        data=display_df.to_csv(index=False),
        file_name="finsight_signals.csv",
        mime="text/csv",
    )

    st.divider()

    # --- Signal Detail View ---
    st.subheader("Signal Detail")
    labels = ["— select a signal —"] + [
        f"{s['entity_name']} — {s['window_end']} ({s['signal_strength']})" for s in signals
    ]
    selected_label = st.selectbox("View Details for:", options=labels)

    if selected_label != "— select a signal —":
        selected = signals[labels.index(selected_label) - 1]
        detail = get_signal_detail(selected["signal_id"])

        if detail:
            d1, d2, d3 = st.columns(3)
            d1.metric("Signal Strength", detail["signal_strength"])
            d2.metric("Aggregate Score", f"{detail['aggregate_score']:+.3f}")
            d3.metric("Positive / Negative / Neutral",
                      f"{detail['positive_count']} / {detail['negative_count']} / {detail['neutral_count']}")

            st.markdown("**Contributing Articles**")
            articles = get_contributing_articles(
                detail["entity_id"], detail["window_start"], detail["window_end"]
            )
            if articles:
                articles_df = pd.DataFrame(articles).rename(columns={
                    "headline": "Headline", "sentiment_label": "Sentiment", "confidence": "Confidence",
                })[["Headline", "Sentiment", "Confidence"]]
                st.dataframe(articles_df, width="stretch", hide_index=True)
                st.caption("Open an article in the Article Inspector page (coming soon) for full detail.")
            else:
                st.info("No contributing articles found for this window.")
else:
    st.info("No signals match your current filters. Try widening the date range or clearing filters.")