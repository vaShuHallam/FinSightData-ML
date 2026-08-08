from app import config
from app.sentiment.base import BaseSentimentAnalyzer, SentimentPrediction

POSITIVE_TOKENS = {
    "beat", "beats", "growth", "gain", "gains", "record", "strong", "surge", "up",
    "rise", "rises", "bullish", "outperform", "improve", "improves", "profit",
}
NEGATIVE_TOKENS = {
    "miss", "missed", "drop", "drops", "fall", "falls", "slide", "slides", "down",
    "bearish", "weak", "loss", "losses", "cut", "cuts", "risk", "risks", "decline",
}


class LexiconSentimentAnalyzer(BaseSentimentAnalyzer):
    model_version = "v1-lexicon"

    def __init__(self, confidence_threshold: float | None = None):
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else config.SENTIMENT_CONFIDENCE_THRESHOLD
        )

    def analyze_batch(self, texts: list[str], batch_size: int = 16) -> list[SentimentPrediction]:
        del batch_size
        return [self._analyze_one(text or "") for text in texts]

    def _analyze_one(self, text: str) -> SentimentPrediction:
        words = [w.strip(".,;:!?()[]{}\"'").lower() for w in text.split()]
        pos = sum(1 for w in words if w in POSITIVE_TOKENS)
        neg = sum(1 for w in words if w in NEGATIVE_TOKENS)

        total = max(pos + neg, 1)
        pos_score = pos / total
        neg_score = neg / total
        neu_score = 1.0 - max(pos_score, neg_score)

        if pos > neg:
            label = "positive"
            confidence = pos_score
        elif neg > pos:
            label = "negative"
            confidence = neg_score
        else:
            label = "neutral"
            confidence = neu_score

        return SentimentPrediction(
            sentiment_label=label,
            positive_score=round(pos_score, 4),
            negative_score=round(neg_score, 4),
            neutral_score=round(max(0.0, min(1.0, neu_score)), 4),
            confidence_score=round(confidence, 4),
            is_abstained=confidence < self.confidence_threshold,
        )
