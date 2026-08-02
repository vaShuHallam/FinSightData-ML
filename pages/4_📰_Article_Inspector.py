"""
FinSight AI — Article Inspector page (REQ-7), the transparency feature.

Lets users inspect a single article's full text alongside FinBERT's
sentiment scores, detected entities, source credibility, and the recency
weight applied to it during signal aggregation.
"""

import pandas as pd
import streamlit as st

from app.services.article_inspector_service import (
    SENTIMENT_OPTIONS,
    get_article_detail,
    get_articles,
)
from app.services.dashboard_service import get_active_entities

st.set_page_config(page_title="Article Inspector", page_icon="📰", layout="wide")
st.title("📰 Article Inspector")

DETAIL_KEY = "article_detail_select"
PLACEHOLDER = "— select an article —"

# --- Search + filters ---
search = st.text_input("Search by keyword or headline", placeholder="e.g. earnings")

col1, col2, col3 = st.columns(3)
with col1:
    sentiment_filter = st.radio("Filter by sentiment", options=SENTIMENT_OPTIONS, horizontal=True)
with col2:
    entities = get_active_entities()
    entity_names = ["All"] + [e["name"] for e in entities]
    entity_choice = st.selectbox("Filter by entity", options=entity_names)
    entity_id = None if entity_choice == "All" else next(
        e["entity_id"] for e in entities if e["name"] == entity_choice
    )
with col3:
    date_range = st.date_input("Publication date range", value=(), format="YYYY-MM-DD")
    date_from = date_range[0] if len(date_range) >= 1 else None
    date_to = date_range[1] if len(date_range) >= 2 else None

articles = get_articles(
    search=search,
    sentiment=sentiment_filter,
    entity_id=entity_id,
    date_from=date_from,
    date_to=date_to,
)

st.caption(f"{len(articles)} article(s) matching current filters")

_BADGE = {"positive": "🟢 Positive", "negative": "🔴 Negative", "neutral": "⚪ Neutral"}

if articles:
    df = pd.DataFrame(articles)
    df["Sentiment"] = df["sentiment_label"].map(lambda s: _BADGE.get(s, "— not yet analyzed —"))
    display_df = df.rename(columns={
        "headline": "Headline", "source_name": "Source", "published_at": "Published At",
    })[["Headline", "Source", "Published At", "Sentiment"]]
    st.dataframe(display_df, width="stretch", hide_index=True)

    st.divider()
    st.subheader("Article Detail")

    labels = [PLACEHOLDER] + [f"{a['headline'][:70]} ({a['source_name']})" for a in articles]
    selected_label = st.selectbox("View details for:", options=labels, key=DETAIL_KEY)

    if selected_label != PLACEHOLDER:
        selected = articles[labels.index(selected_label) - 1]
        detail = get_article_detail(selected["article_id"])

        if detail:
            def _close_detail():
                st.session_state[DETAIL_KEY] = PLACEHOLDER

            st.button("✕ Close", on_click=_close_detail)

            st.markdown(f"### {detail['headline']}")

            meta1, meta2, meta3 = st.columns(3)
            with meta1:
                if detail["source_url"]:
                    st.markdown(f"**Source:** [{detail['source_name']}]({detail['source_url']})")
                else:
                    st.markdown(f"**Source:** {detail['source_name']}")
            with meta2:
                st.markdown(f"**Published At:** {detail['published_at']}")
            with meta3:
                cred = detail["source_credibility_score"]
                if cred is not None:
                    icon = "🟢" if cred > 0.7 else ("🟡" if cred >= 0.4 else "🔴")
                    st.markdown(f"**Source Credibility:** {icon} {cred:.2f}")

            st.divider()

            label = detail["sentiment_label"]
            if label:
                st.markdown(f"**Sentiment:** {_BADGE.get(label, label)}")

                s1, s2, s3, s4 = st.columns(4)
                s1.metric("Positive", f"{detail['positive_score']:.3f}")
                s2.metric("Negative", f"{detail['negative_score']:.3f}")
                s3.metric("Neutral", f"{detail['neutral_score']:.3f}")
                if detail["is_abstained"]:
                    s4.metric("Confidence", "Abstained")
                    st.caption("Abstained — low confidence")
                else:
                    s4.metric("Confidence", f"{detail['confidence_score']:.3f}")

                st.caption(f"Model version: {detail['model_version']}  |  "
                          f"Recency weight: {detail['recency_weight']:.3f}"
                          if detail["recency_weight"] is not None else
                          f"Model version: {detail['model_version']}")
            else:
                st.info("This article hasn't been analyzed by FinBERT yet.")

            st.markdown("**Entities Detected**")
            if detail["entities"]:
                tag_cols = st.columns(len(detail["entities"]))
                for col, ent in zip(tag_cols, detail["entities"]):
                    with col:
                        if st.button(f"🏷️ {ent['name']}", key=f"tag_{ent['entity_id']}_{selected['article_id']}"):
                            st.caption(f"Would open Entity Explorer for {ent['name']} (page coming soon).")
            else:
                st.caption("No entities detected in this article.")

            st.markdown("**Article Body**")
            st.text_area("Article Body", value=detail["body"] or "(No body text available)",
                        height=200, disabled=True, label_visibility="collapsed")
else:
    st.info("No articles match your current filters. Try widening the date range or clearing filters.")