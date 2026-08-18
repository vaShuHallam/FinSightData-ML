"""
Compute the gold-standard evaluation metrics (BRD Stage 4 / REQ-8).

Two modes:

  --mode dual (default): two independent annotators. Computes Cohen's
  kappa between them, builds gold from where they agree, writes
  disagreements to a separate file for manual discussion.

  --mode single: one annotator's completed file is used directly as gold.
  Cohen's kappa is NOT computed in this mode — it is mathematically
  defined as agreement between two independent raters, so with only one
  rater there is no second set of labels to measure agreement against.
  If you moved to single-annotator labeling after an initial low-agreement
  dual-annotator pass, state this explicitly in your methodology writeup,
  e.g.: "Initial two-annotator labeling showed low agreement (kappa=X);
  we moved to single-expert annotation for the gold standard, so
  inter-annotator reliability is not available under this revised
  approach."

Usage:
    python compute_gold_standard_metrics.py
    python compute_gold_standard_metrics.py --mode single --gold-file annotation_expert.xlsx
"""

import argparse
import json
from datetime import datetime, timezone

from openpyxl import Workbook, load_workbook
from sklearn.metrics import classification_report, cohen_kappa_score, confusion_matrix

from Dashboard.db import get_session
from Dashboard.models import Article, ArticleEntity, Entity, ModelVersion, SentimentResult

VALID_LABELS = {"positive", "negative", "neutral"}
LABEL_ORDER = ["positive", "negative", "neutral"]  # fixed order for confusion matrix rows/cols


def read_annotations(path: str) -> dict[int, dict]:
    """Returns {article_id: {'sentiment': str|None, 'entities': set[str]}}"""
    wb = load_workbook(path, data_only=True)
    ws = wb["Annotations"]
    result = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        article_id, headline, body, source, published, sentiment, entities = row
        if article_id is None:
            continue
        sentiment_clean = (sentiment or "").strip().lower() or None
        if sentiment_clean and sentiment_clean not in VALID_LABELS:
            print(f"WARNING: article {article_id} has invalid sentiment value "
                  f"'{sentiment}' — treating as unlabeled.")
            sentiment_clean = None
        entity_set = {e.strip() for e in (entities or "").split(",") if e.strip()}
        result[int(article_id)] = {"sentiment": sentiment_clean, "entities": entity_set}
    return result


def compute_kappa_and_gold(ann1: dict, ann2: dict) -> tuple[float, dict[int, str], list[int]]:
    shared_ids = sorted(set(ann1) & set(ann2))
    labeled_ids = [
        aid for aid in shared_ids
        if ann1[aid]["sentiment"] is not None and ann2[aid]["sentiment"] is not None
    ]
    if len(labeled_ids) < len(shared_ids):
        print(f"NOTE: {len(shared_ids) - len(labeled_ids)} article(s) not yet labeled by "
              f"both annotators — excluded from kappa/metrics for now.")

    labels1 = [ann1[aid]["sentiment"] for aid in labeled_ids]
    labels2 = [ann2[aid]["sentiment"] for aid in labeled_ids]
    kappa = cohen_kappa_score(labels1, labels2) if labeled_ids else float("nan")

    gold, disagreements = {}, []
    for aid, l1, l2 in zip(labeled_ids, labels1, labels2):
        if l1 == l2:
            gold[aid] = l1
        else:
            disagreements.append(aid)
    return kappa, gold, disagreements


def read_gold_directly(path: str) -> dict[int, str]:
    """Single-annotator mode: one file's labels become the gold set directly. No kappa."""
    annotations = read_annotations(path)
    gold = {aid: data["sentiment"] for aid, data in annotations.items() if data["sentiment"] is not None}
    unlabeled = len(annotations) - len(gold)
    if unlabeled:
        print(f"NOTE: {unlabeled} article(s) have no sentiment label yet — excluded from the gold set.")
    return gold


def write_disagreements_file(disagreements: list[int], ann1: dict, ann2: dict, path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Disagreements"
    ws.append(["Article ID", "Annotator 1 said", "Annotator 2 said"])
    with get_session() as session:
        for aid in disagreements:
            article = session.get(Article, aid)
            headline = article.headline if article else "(unknown)"
            ws.append([f"{aid}: {headline}", ann1[aid]["sentiment"], ann2[aid]["sentiment"]])
    ws.column_dimensions["A"].width = 70
    wb.save(path)


def score_finbert_against_gold(gold: dict[int, str]) -> dict:
    with get_session() as session:
        rows = (
            session.query(Article.article_id, SentimentResult.sentiment_label, SentimentResult.is_abstained)
            .join(SentimentResult, SentimentResult.article_id == Article.article_id)
            .filter(Article.article_id.in_(gold.keys()))
            .filter(SentimentResult.entity_id.is_(None))
            .all()
        )

    y_true, y_pred, abstained_count = [], [], 0
    for article_id, predicted_label, is_abstained in rows:
        if article_id not in gold:
            continue
        y_true.append(gold[article_id])
        y_pred.append(predicted_label)
        if is_abstained:
            abstained_count += 1

    if not y_true:
        return {"error": "No FinBERT predictions found for the gold-labeled articles. "
                         "Run run_sentiment.py on these articles first."}

    report = classification_report(y_true, y_pred, labels=sorted(VALID_LABELS),
                                   output_dict=True, zero_division=0)

    cm = confusion_matrix(y_true, y_pred, labels=LABEL_ORDER).tolist()

    class_distribution = {label: y_true.count(label) for label in LABEL_ORDER}

    return {
        "n_scored": len(y_true),
        "macro_f1": report["macro avg"]["f1-score"],
        "positive_f1": report.get("positive", {}).get("f1-score", 0.0),
        "negative_f1": report.get("negative", {}).get("f1-score", 0.0),
        "neutral_f1": report.get("neutral", {}).get("f1-score", 0.0),
        "abstention_rate": abstained_count / len(y_true),
        "confusion_matrix": cm,
        "confusion_matrix_labels": LABEL_ORDER,
        "class_distribution": class_distribution,
    }


def score_entity_extraction(gold: dict[int, str], ann1: dict, ann2: dict) -> dict:
    with get_session() as session:
        tp = fp = fn = 0
        for article_id in gold:
            annotated = ann1[article_id]["entities"] | ann2[article_id]["entities"]
            annotated_normalized = {e.lower() for e in annotated}

            tagged_names = {
                name for (name,) in
                session.query(Entity.name)
                .join(ArticleEntity, ArticleEntity.entity_id == Entity.entity_id)
                .filter(ArticleEntity.article_id == article_id)
                .all()
            }
            tagged_normalized = {n.lower() for n in tagged_names}

            tp += len(annotated_normalized & tagged_normalized)
            fp += len(tagged_normalized - annotated_normalized)
            fn += len(annotated_normalized - tagged_normalized)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {"entity_precision": precision, "entity_recall": recall, "tp": tp, "fp": fp, "fn": fn}


def save_results(version_label: str, kappa: float, sentiment_scores: dict, entity_scores: dict,
                 n_gold: int, annotation_method: str) -> None:
    with get_session() as session:
        mv = session.query(ModelVersion).filter_by(version_label=version_label).first()
        if mv:
            mv.macro_f1_score = sentiment_scores.get("macro_f1")
            mv.entity_precision = entity_scores.get("entity_precision")
            mv.entity_recall = entity_scores.get("entity_recall")

    results = {
        "version_label": version_label,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "gold_standard_size": n_gold,
        "annotation_method": annotation_method,
        "cohens_kappa": kappa if kappa == kappa else None,  # NaN check: NaN != NaN
        **sentiment_scores,
        **entity_scores,
    }
    filename = f"evaluation_results_{version_label}.json"
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {filename}")


def _print_scores(label: str, scores: dict) -> None:
    print(f"\n--- {label} ---")
    for k, v in scores.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute gold-standard evaluation metrics.")
    parser.add_argument("--mode", choices=["dual", "single"], default="dual",
                       help="'dual' = two independent annotators, computes Cohen's kappa. "
                            "'single' = one annotator's file used directly as gold, no kappa.")
    parser.add_argument("--gold-file", default="annotation_batch_annotator1.xlsx",
                       help="Used only in --mode single.")
    parser.add_argument("--annotator1", default="annotation_batch_annotator1.xlsx")
    parser.add_argument("--annotator2", default="annotation_batch_annotator2.xlsx")
    parser.add_argument("--version-label", default="v1")
    args = parser.parse_args()

    if args.mode == "single":
        print("Running in SINGLE-ANNOTATOR mode — Cohen's kappa is NOT computed "
              "(it requires two independent raters). State this explicitly in your "
              "methodology write-up.\n")
        gold = read_gold_directly(args.gold_file)
        gold_annotations = read_annotations(args.gold_file)
        kappa = float("nan")
        print(f"Gold-standard articles: {len(gold)}")

        sentiment_scores = score_finbert_against_gold(gold)
        _print_scores("FinBERT sentiment performance vs. gold standard", sentiment_scores)

        entity_scores = score_entity_extraction(gold, gold_annotations, gold_annotations)
        _print_scores("Entity tagging performance vs. gold standard", entity_scores)

        if "error" not in sentiment_scores:
            save_results(args.version_label, kappa, sentiment_scores, entity_scores, len(gold),
                        annotation_method="Single expert annotator")

    else:
        ann1 = read_annotations(args.annotator1)
        ann2 = read_annotations(args.annotator2)

        kappa, gold, disagreements = compute_kappa_and_gold(ann1, ann2)

        print(f"Cohen's kappa (sentiment agreement): {kappa:.4f}")
        print(f"Gold-standard articles (agreed):     {len(gold)}")
        print(f"Disagreements (excluded for now):    {len(disagreements)}")

        if disagreements:
            write_disagreements_file(disagreements, ann1, ann2, "disagreements_to_resolve.xlsx")
            print("Saved disagreements_to_resolve.xlsx — discuss these, update annotator1's "
                 "file to reflect your agreed answer, and re-run this script.")

        sentiment_scores = score_finbert_against_gold(gold)
        _print_scores("FinBERT sentiment performance vs. gold standard", sentiment_scores)

        entity_scores = score_entity_extraction(gold, ann1, ann2)
        _print_scores("Entity tagging performance vs. gold standard", entity_scores)

        if "error" not in sentiment_scores:
            save_results(args.version_label, kappa, sentiment_scores, entity_scores, len(gold),
                        annotation_method="Two independent annotators, resolved via agreement")