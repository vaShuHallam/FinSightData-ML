"""
FinSight AI — Article Inspector page , the transparency feature.

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

#! --- Search + filters ---
# Allow the user to search by article headline or body text.
search = st.text_input("Search by keyword or headline", placeholder="e.g. earnings")

col1, col2, col3 = st.columns(3)
with col1:
    # Allow the user to filter articles by sentiment.
    sentiment_filter = st.radio("Filter by sentiment", options=SENTIMENT_OPTIONS, horizontal=True)
with col2:
    # Retrieve the active entities from the database.
    entities = get_active_entities()
    entity_names = ["All"] + [e["name"] for e in entities]
    entity_choice = st.selectbox("Filter by entity", options=entity_names)
    # Convert the selected entity name into its entity_id.
    entity_id = None if entity_choice == "All" else next(
        e["entity_id"] for e in entities if e["name"] == entity_choice
    )
with col3:
     # Allow the user to select a publication date range.
    date_range = st.date_input("Publication date range", value=(), format="YYYY-MM-DD")
    date_from = date_range[0] if len(date_range) >= 1 else None
    date_to = date_range[1] if len(date_range) >= 2 else None

#! GET ARTICLES
# ---------------------------------------------------------
# Send all selected filters to the service layer.
articles = get_articles(
    search=search,
    sentiment=sentiment_filter,
    entity_id=entity_id,
    date_from=date_from,
    date_to=date_to,
)

st.caption(f"{len(articles)} article(s) matching current filters")
# Map the database sentiment values to user-friendly badges
_BADGE = {"positive": "🟢 Positive", "negative": "🔴 Negative", "neutral": "⚪ Neutral"}

#! ARTICLE LIST
if articles:
    df = pd.DataFrame(articles)
    # Create a new "Sentiment" column.
    df["Sentiment"] = df["sentiment_label"].map(lambda s: _BADGE.get(s, "— not yet analyzed —"))
    display_df = df.rename(columns={
        "headline": "Headline", "source_name": "Source", "published_at": "Published At",
    })[["Headline", "Source", "Published At", "Sentiment"]]
    st.dataframe(display_df, width="stretch", hide_index=True)

    st.divider()
    #!  ARTICLE DETAIL
    st.subheader("Article Detail")

    labels = [PLACEHOLDER] + [f"{a['headline'][:70]} ({a['source_name']})" for a in articles]
     # Let the user select which article they want to inspect.
    selected_label = st.selectbox("View details for:", options=labels, key=DETAIL_KEY)
    # Only load article details if the user actually selected an article instead of the placeholder.
    if selected_label != PLACEHOLDER:
        selected = articles[labels.index(selected_label) - 1]
        detail = get_article_detail(selected["article_id"])
        # Make sure the article still exists.
        if detail:
             #! CLOSE DETAIL
             # It resets the selectbox value back to the
            def _close_detail():
                st.session_state[DETAIL_KEY] = PLACEHOLDER

            st.button("✕ Close", on_click=_close_detail)

            st.markdown(f"### {detail['headline']}")
            # ARTICLE METADATA
            meta1, meta2, meta3 = st.columns(3)
            with meta1:
                 # If a source URL exists, make the source name clickable
                if detail["source_url"]:
                    st.markdown(f"**Source:** [{detail['source_name']}]({detail['source_url']})")
                else:
                    st.markdown(f"**Source:** {detail['source_name']}")
            with meta2:
                 #  Publication date
                st.markdown(f"**Published At:** {detail['published_at']}")
            with meta3:
                cred = detail["source_credibility_score"]
                if cred is not None:
                    # Select an icon based on the credibility score
                    icon = "🟢" if cred > 0.7 else ("🟡" if cred >= 0.4 else "🔴")
                    st.markdown(f"**Source Credibility:** {icon} {cred:.2f}")

            st.divider()
            # !SENTIMENT INFORMATION

            label = detail["sentiment_label"]
            # If the article has already been analyzed
            if label:
                # Display the sentiment badge.
                st.markdown(f"**Sentiment:** {_BADGE.get(label, label)}")

                s1, s2, s3, s4 = st.columns(4)
             
                s1.metric("Positive", f"{detail['positive_score']:.3f}")
                s2.metric("Negative", f"{detail['negative_score']:.3f}")
                s3.metric("Neutral", f"{detail['neutral_score']:.3f}")
                # If FinBERT abstained, display that instead of displaying the confidence number.
                if detail["is_abstained"]:
                    s4.metric("Confidence", "Abstained")
                    st.caption("Abstained — low confidence")
                else:
                    s4.metric("Confidence", f"{detail['confidence_score']:.3f}")
                #  Display the model version and recency weight.
                st.caption(f"Model version: {detail['model_version']}  |  "
                          f"Recency weight: {detail['recency_weight']:.3f}"
                          if detail["recency_weight"] is not None else
                          f"Model version: {detail['model_version']}")
            else:
                st.info("This article hasn't been analyzed by FinBERT yet.")
                
              # !DETECTED ENTITIES
            st.markdown("**Entities Detected**")
            if detail["entities"]:
                tag_cols = st.columns(len(detail["entities"]))
                for col, ent in zip(tag_cols, detail["entities"]):
                    with col:
                         # Display the entity as a button.
                        if st.button(f"🏷️ {ent['name']}", key=f"tag_{ent['entity_id']}_{selected['article_id']}"):
                            st.caption(f"Would open Entity Explorer for {ent['name']} (page coming soon).")
            else:
                st.caption("No entities detected in this article.")

            st.markdown("**Article Body**")
            st.text_area("Article Body", value=detail["body"] or "(No body text available)",
                        height=200, disabled=True, label_visibility="collapsed")
else:
    st.info("No articles match your current filters. Try widening the date range or clearing filters.")