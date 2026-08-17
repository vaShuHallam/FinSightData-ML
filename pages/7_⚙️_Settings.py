"""
FinSight AI — Settings / Pipeline Configuration page (REQ-9).
"""

import pandas as pd
import streamlit as st

from app import config
from app.services.settings_service import (
    ENTITY_TYPE_OPTIONS,
    SECTOR_OPTIONS,
    add_entity,
    deactivate_entity,
    get_all_entities,
    get_current_settings,
    get_model_version_log,
    get_pipeline_status_by_stage,
    get_source_credibility_table,
    save_settings,
    update_entity,
    update_source_credibility,
)

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")

# --- Access control (NFR 4.2 REQ-5) ---
# This page is restricted to project team members. Nothing below this
# block renders until authenticated — st.stop() halts the script here,
# so pipeline controls and entity management are never sent to the
# browser for an unauthenticated visitor, not just hidden/disabled.
if not st.session_state.get("settings_authenticated", False):
    st.title("⚙️ Settings / Pipeline Configuration")
    st.info("This page is restricted to project team members.")

    if not config.SETTINGS_PASSWORD:
        st.warning("SETTINGS_PASSWORD is not set in .env — this page is currently "
                  "unprotected. Set SETTINGS_PASSWORD to enable access control.")

    password = st.text_input("Team password", type="password")
    if st.button("Log in"):
        if config.SETTINGS_PASSWORD and password == config.SETTINGS_PASSWORD:
            st.session_state.settings_authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

# --- Authenticated from here on ---
if st.button("🚪 Log out"):
    st.session_state.settings_authenticated = False
    st.rerun()

st.title("⚙️ Settings / Pipeline Configuration")

# --- Pipeline Status ---
st.subheader("Pipeline Status")
status = get_pipeline_status_by_stage()
cols = st.columns(len(status))
for col, (stage, info) in zip(cols, status.items()):
    icon = {"completed": "✅", "failed": "❌", "running": "🔄", "never run": "⚪"}.get(info["status"], "⚪")
    col.metric(stage.capitalize(), f"{icon} {info['status']}")
    col.caption(f"{info['articles_processed']} processed")
    if info["completed_at"]:
        col.caption(str(info["completed_at"]))

st.divider()

# --- Run Pipeline ---
st.subheader("Run Pipeline")
st.caption("Runs fetch → tag → sentiment → aggregate in sequence. This can take a while "
          "(FinBERT alone may take a minute+ to load on first run) — the page will be "
          "unresponsive until it finishes, this is normal for Streamlit's execution model.")
pipeline_query = st.text_input("Ingestion query", value="stock market OR earnings OR shares")

if st.button("▶️ Run Full Pipeline"):
    with st.spinner("Fetching articles..."):
        from app.ingestion.newsapi_fetcher import NewsAPIFetcher
        from app.ingestion.pipeline import run_ingestion
        ingestion_summary = run_ingestion(NewsAPIFetcher(), query=pipeline_query, max_results=50)
    st.write(f"Fetch: {ingestion_summary}")

    with st.spinner("Tagging entities..."):
        from app.entity_tagging.pipeline import build_rule_based_tagger, run_entity_tagging
        tagging_summary = run_entity_tagging(build_rule_based_tagger())
    st.write(f"Entity tagging: {tagging_summary}")

    with st.spinner("Running sentiment analysis (FinBERT — may take a while)..."):
        from app.sentiment.finbert_analyzer import FinBERTSentimentAnalyzer
        from app.sentiment.pipeline import run_sentiment_analysis
        sentiment_summary = run_sentiment_analysis(FinBERTSentimentAnalyzer())
    st.write(f"Sentiment: {sentiment_summary}")

    with st.spinner("Aggregating signals..."):
        from app.signals.pipeline import run_signal_aggregation
        signal_summary = run_signal_aggregation()
    st.write(f"Signals: {signal_summary}")

    st.success("Full pipeline run complete.")
    st.cache_data.clear()

st.divider()

# --- Configuration settings ---
st.subheader("Configuration")
current = get_current_settings()

c1, c2, c3 = st.columns(3)
with c1:
    confidence_threshold = st.number_input(
        "Confidence Threshold", min_value=0.0, max_value=1.0,
        value=current["confidence_threshold"], step=0.05,
    )
with c2:
    window_options = [6, 12, 24]
    current_window = current["aggregation_window_hours"]
    if current_window not in window_options:
        window_options = sorted(window_options + [current_window])  # show the real current value even if non-standard
    aggregation_window = st.selectbox(
        "Aggregation Window (hours)", options=window_options,
        index=window_options.index(current_window),
    )
with c3:
    alert_threshold = st.number_input(
        "Default Alert Threshold", min_value=0.0, max_value=1.0,
        value=current["default_alert_threshold"], step=0.05,
    )

if st.button("💾 Save Configuration"):
    save_settings(confidence_threshold, aggregation_window, alert_threshold)
    st.success("Settings saved. Changes take effect the next time the app or a pipeline "
              "script starts — not instantly within this running session.")

st.divider()

# --- Entity Management ---
st.subheader("Entity Management")
entities = get_all_entities()
if entities:
    df = pd.DataFrame(entities).rename(columns={
        "name": "Name", "ticker_symbol": "Ticker", "entity_type": "Type",
        "sector": "Sector", "exchange": "Exchange", "is_active": "Active",
    })[["Name", "Ticker", "Type", "Sector", "Exchange", "Active"]]
    st.dataframe(df, width="stretch", hide_index=True)

with st.expander("➕ Add Entity"):
    with st.form("add_entity_form", clear_on_submit=True):
        ae1, ae2, ae3 = st.columns(3)
        with ae1:
            new_name = st.text_input("Entity Name *")
            new_ticker = st.text_input("Ticker Symbol")
        with ae2:
            new_type = st.selectbox("Entity Type *", options=ENTITY_TYPE_OPTIONS)
            new_sector = st.selectbox("Sector *", options=SECTOR_OPTIONS)
        with ae3:
            new_exchange = st.text_input("Exchange")
            new_active = st.toggle("Is Active", value=True)

        if st.form_submit_button("Save Entity"):
            if not new_name:
                st.error("Entity Name is required.")
            else:
                success, message = add_entity(new_name, new_ticker, new_type, new_sector, new_exchange, new_active)
                (st.success if success else st.error)(message)

with st.expander("✏️ Edit / Deactivate Entity"):
    if entities:
        entity_names = [e["name"] for e in entities]
        selected = st.selectbox("Select entity to edit", options=entity_names, key="edit_entity_select")
        entity = next(e for e in entities if e["name"] == selected)

        ee1, ee2, ee3 = st.columns(3)
        eid = entity["entity_id"]  # suffix every key with this so switching entities resets the form
        with ee1:
            edit_name = st.text_input("Entity Name *", value=entity["name"], key=f"edit_name_{eid}")
            edit_ticker = st.text_input("Ticker Symbol", value=entity["ticker_symbol"] or "", key=f"edit_ticker_{eid}")
        with ee2:
            edit_type = st.selectbox("Entity Type *", options=ENTITY_TYPE_OPTIONS,
                                     index=ENTITY_TYPE_OPTIONS.index(entity["entity_type"]), key=f"edit_type_{eid}")
            sector_idx = SECTOR_OPTIONS.index(entity["sector"]) if entity["sector"] in SECTOR_OPTIONS else 0
            edit_sector = st.selectbox("Sector *", options=SECTOR_OPTIONS, index=sector_idx, key=f"edit_sector_{eid}")
        with ee3:
            edit_exchange = st.text_input("Exchange", value=entity["exchange"] or "", key=f"edit_exchange_{eid}")
            edit_active = st.toggle("Is Active", value=entity["is_active"], key=f"edit_active_{eid}")

        col_save, col_deactivate = st.columns(2)
        if col_save.button("Save Changes", key=f"save_btn_{eid}"):
            success, message = update_entity(entity["entity_id"], edit_name, edit_ticker,
                                             edit_type, edit_sector, edit_exchange, edit_active)
            (st.success if success else st.error)(message)
            if success:
                st.rerun()
        if col_deactivate.button("🚫 Deactivate", key=f"deactivate_btn_{eid}"):
            deactivate_entity(entity["entity_id"])
            st.success(f"{entity['name']} deactivated.")
            st.rerun()

st.divider()

# --- Source Management ---
st.subheader("Source Management")
st.caption("Editing a score only affects articles fetched AFTER the change — "
          "already-ingested articles keep the credibility score they had when fetched.")
sources = get_source_credibility_table()
source_names = [s["source_name"] for s in sources]
if sources:
    df = pd.DataFrame(sources).rename(columns={"source_name": "Source", "credibility_score": "Credibility Score"})
    st.dataframe(df, width="stretch", hide_index=True)

sel_source = st.selectbox("Edit source credibility", options=source_names)
current_score = next(s["credibility_score"] for s in sources if s["source_name"] == sel_source)
new_score = st.number_input("New credibility score", min_value=0.0, max_value=1.0, value=current_score, step=0.05)
if st.button("Save Source Credibility"):
    update_source_credibility(sel_source, new_score)
    st.success(f"Updated {sel_source} to {new_score:.2f}.")

st.divider()

# --- Model Version Log ---
st.subheader("Model Version Log")
versions = get_model_version_log()
if versions:
    df = pd.DataFrame(versions).rename(columns={
        "version_label": "Version", "model_name": "Model", "confidence_threshold": "Confidence Threshold",
        "macro_f1_score": "Macro F1", "entity_precision": "Entity Precision",
        "entity_recall": "Entity Recall", "deployed_at": "Deployed At",
    })
    st.dataframe(df, width="stretch", hide_index=True)
else:
    st.info("No model versions logged yet.")