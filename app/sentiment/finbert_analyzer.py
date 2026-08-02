"""
FinBERT sentiment analyzer.

Model: ProsusAI/finbert — BERT further pretrained on financial text, then
fine-tuned for 3-class sentiment classification (positive/negative/neutral).
https://huggingface.co/ProsusAI/finbert

IMPORTANT — where to actually run this:
This module needs `transformers` + a torch/tensorflow backend, and on first
use downloads ~440MB of model weights from the HuggingFace Hub. That download
will fail inside network-restricted sandboxes (confirmed: huggingface.co
returns a blocked-host response in the build environment this project was
scaffolded in). Run this on an unrestricted machine — your own laptop
(PyCharm) or Google Colab both work fine, and Colab's free GPU makes batch
inference considerably faster if you're processing many articles.

The model+tokenizer are loaded once in __init__ and reused across calls —
don't construct a new FinBERTSentimentAnalyzer per article.
"""

import logging

from app import config
from app.sentiment.base import BaseSentimentAnalyzer, SentimentPrediction

logger = logging.getLogger(__name__)

MODEL_NAME = "ProsusAI/finbert"


class FinBERTSentimentAnalyzer(BaseSentimentAnalyzer):
    model_version = "v1"

    def __init__(
        self,
        confidence_threshold: float | None = None,
        max_length: int = 512,
        device: str | None = None,
    ):
        # Imported lazily so importing this module doesn't require torch to be
        # installed unless you actually instantiate the analyzer.
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else config.SENTIMENT_CONFIDENCE_THRESHOLD
        )
        self.max_length = max_length
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        logger.info("Loading %s on device=%s ...", MODEL_NAME, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        self.model.to(self.device)
        self.model.eval()

        # Read the label mapping from the model config rather than hardcoding
        # an assumed order — robust to any future model swap.
        self.id2label: dict[int, str] = {
            int(k): v.lower() for k, v in self.model.config.id2label.items()
        }
        logger.info("Loaded. Label mapping: %s", self.id2label)

    def analyze_batch(self, texts: list[str], batch_size: int = 16) -> list[SentimentPrediction]:
        """
        Run FinBERT over `texts`, internally chunked into batches of
        `batch_size` (BRD requires a batch size of at least 16 for
        throughput on CPU/GPU). Returns predictions in the same order as
        the input texts.
        """
        torch = self._torch
        results: list[SentimentPrediction] = []

        for start in range(0, len(texts), batch_size):
            chunk = texts[start : start + batch_size]
            inputs = self.tokenizer(
                chunk,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                logits = self.model(**inputs).logits
                probs = torch.nn.functional.softmax(logits, dim=-1).cpu().tolist()

            for prob_row in probs:
                results.append(self._to_prediction(prob_row))

        return results

    def _to_prediction(self, probs: list[float]) -> SentimentPrediction:
        scores = {self.id2label[i]: p for i, p in enumerate(probs)}
        top_label = max(scores, key=scores.get)
        confidence = scores[top_label]

        return SentimentPrediction(
            sentiment_label=top_label,
            positive_score=scores.get("positive", 0.0),
            negative_score=scores.get("negative", 0.0),
            neutral_score=scores.get("neutral", 0.0),
            confidence_score=confidence,
            is_abstained=confidence < self.confidence_threshold,
        )
