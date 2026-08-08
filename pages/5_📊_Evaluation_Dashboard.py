"""
FinSight AI — Evaluation Dashboard page (REQ-8).

Reads v1 (and v2, once it exists) evaluation results produced by
compute_gold_standard_metrics.py, and presents the full BRD-specified
comparison: metrics table, confusion matrix, F1-by-class chart, user
testing results, abstention rate, benchmark info, and iteration notes.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.services.evaluation_service import (
    build_comparison_table,
    get_iteration_summary,
    get_user_testing_results,
    list_available_result_versions,
    load_results,
)

st.set_page_config(page_title="Evaluation Dashboard", page_icon="📊", layout="wide")
st.title("📊 Evaluation Dashboard")

available_versions = list_available_result_versions()
user_testing = get_user_testing_results()

if not available_versions:
    st.info("No evaluation results found yet. Run compute_gold_standard_metrics.py first.")
    st.stop()

default_base = "v1" if "v1" in available_versions else available_versions[0]
default_compare = "v2" if "v2" in available_versions else None

selector_col1, selector_col2 = st.columns(2)
with selector_col1:
    base_version = st.selectbox(
        "Base version",
        options=available_versions,
        index=available_versions.index(default_base),
    )
with selector_col2:
    compare_candidates = ["(none)"] + [v for v in available_versions if v != base_version]
    compare_index = compare_candidates.index(default_compare) if default_compare in compare_candidates else 0
    compare_version = st.selectbox("Compare version", options=compare_candidates, index=compare_index)

v1 = load_results(base_version)
v2 = load_results(compare_version) if compare_version != "(none)" else None

if v2 is None:
    st.caption("ℹ️ Comparison version not selected or unavailable — showing single-version metrics.")

# --- Benchmark Information ---
st.subheader("Benchmark Information")
b1, b2, b3 = st.columns(3)
b1.metric("Gold-standard size", v1.get("gold_standard_size", "—"))
b2.metric("Annotation method", v1.get("annotation_method", "—"))
kappa = v1.get("cohens_kappa")
b3.metric("Cohen's kappa", f"{kappa:.3f}" if kappa is not None else "N/A (single annotator)")

if v1.get("class_distribution"):
    dist_df = pd.DataFrame(list(v1["class_distribution"].items()), columns=["Sentiment", "Count"])
    fig = px.bar(dist_df, x="Sentiment", y="Count", title="Gold-standard sentiment class distribution",
                color="Sentiment", color_discrete_map={"positive": "#2ecc71", "negative": "#e74c3c", "neutral": "#95a5a6"})
    st.plotly_chart(fig, width="stretch")

st.divider()

# --- Model Metrics Comparison Table ---
st.subheader("Model Metrics Comparison")
rows = build_comparison_table(v1, v2, user_testing)

def _fmt(val):
    if val is None:
        return "—"
    return f"{val:.3f}" if isinstance(val, float) else str(val)

def _fmt_delta(row):
    val = row["delta"]
    if val is None:
        return "—"
    direction_arrow = "▲" if val > 0 else ("▼" if val < 0 else "=")
    if row["is_improvement"] is None:
        color = "⚪"
    else:
        color = "🟢" if row["is_improvement"] else "🔴"
    return f"{color} {direction_arrow} {val:+.3f}"

table_df = pd.DataFrame([
    {"Metric": r["metric"], f"{base_version} Result": _fmt(r["v1_result"]),
     f"{compare_version} Result": _fmt(r["v2_result"]), "Delta": _fmt_delta(r)}
    for r in rows
])
st.dataframe(table_df, width="stretch", hide_index=True)
st.caption("Signal Precision, Mean Relevance Rating, and Time to Signal are not tracked "
          "per model version in the current schema (user feedback is tied to alerts, not "
          "to a specific model version) — shown as a single current snapshot, delta N/A.")

st.divider()

# --- Confusion Matrix + F1 by Class, side by side ---
col1, col2 = st.columns(2)

with col1:
    st.subheader(f"Confusion Matrix ({base_version})")
    if v1.get("confusion_matrix"):
        labels = v1["confusion_matrix_labels"]
        fig = go.Figure(data=go.Heatmap(
            z=v1["confusion_matrix"], x=labels, y=labels,
            colorscale="Blues", text=v1["confusion_matrix"], texttemplate="%{text}",
        ))
        fig.update_layout(xaxis_title="Predicted", yaxis_title="Actual (gold)")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No confusion matrix data in v1 results.")

with col2:
    st.subheader("F1 Score by Class")
    class_f1_data = []
    for label, key in [("Positive", "positive_f1"), ("Negative", "negative_f1"), ("Neutral", "neutral_f1")]:
        class_f1_data.append({"Class": label, "Version": "v1", "F1": v1.get(key, 0)})
        if v2:
            class_f1_data.append({"Class": label, "Version": "v2", "F1": v2.get(key, 0)})
    fig = px.bar(pd.DataFrame(class_f1_data), x="Class", y="F1", color="Version", barmode="group")
    fig.update_layout(yaxis_range=[0, 1])
    st.plotly_chart(fig, width="stretch")

st.divider()

# --- User Testing Results ---
st.subheader("User Testing Results")
u1, u2, u3 = st.columns(3)
mrr = user_testing["mean_relevance_rating"]
sp = user_testing["signal_precision"]
tts = user_testing["time_to_signal_minutes"]
u1.metric("Mean Relevance Rating", f"{mrr:.2f} / 5" if mrr is not None else "No ratings yet")
u2.metric("Signal Precision", f"{sp:.1%}" if sp is not None else "No ratings yet")
u3.metric("Time to Signal", f"{tts:.1f} min" if tts is not None else "No data yet")
st.caption(f"Based on {user_testing['n_feedback']} rated alert(s) so far.")

st.divider()

# --- Abstention Rate ---
st.subheader("Abstention Rate")
a1, a2 = st.columns(2)
a1.metric(base_version, f"{v1.get('abstention_rate', 0):.1%}")
a2.metric(compare_version if v2 else "comparison", f"{v2.get('abstention_rate', 0):.1%}" if v2 else "—")

st.divider()

# --- Iteration Summary ---
st.subheader("Iteration Summary")
st.markdown(get_iteration_summary())