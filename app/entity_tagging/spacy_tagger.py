"""
spaCy-based entity tagger — companies only.

IMPORTANT —  spaCy's general-purpose NER model (trained
on OntoNotes) recognizes proper-noun entity TYPES: ORG (organizations),
PERSON, GPE (places), etc. It does NOT recognize commodities like "Gold"
or "Crude Oil" — those are common nouns, not named entities in the sense
NER models are trained on, so spaCy will essentially never tag them. This
tagger therefore ONLY handles entity_type="Company" — indices, sectors,
and commodities still need the rule-based tagger. See hybrid_tagger.py,
which combines both correctly.

What this genuinely improves over the rule-based matcher: catching company
mentions in more varied phrasing/capitalization/context than a fixed regex
can (spaCy understands "Apple's iPhone division" or a company name
embedded mid-clause better than word-boundary regex does), and it's less
prone to the ticker/common-word false-positive problem (a ticker like a
hypothetical "ALL" won't get tagged just because the word "all" appears —
spaCy only flags things it recognizes as a genuine organization span).

What this does NOT fix: pronouns ("it," "the company"), epithets ("the
iPhone maker," "the Cupertino giant"), or any reference requiring
coreference resolution / entity linking — those need a fundamentally
different NLP capability spaCy's stock NER doesn't provide. Don't expect
entity recall to jump to near-100% from this change alone.

Verify against a live response before trusting this — see
check_spacy_tagger.py, which tests this exact matching logic against real
spaCy output on your own machine before it's wired into the full pipeline.
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass

from app.entity_tagging.base import BaseEntityTagger, EntityMention

logger = logging.getLogger(__name__)

# Same corporate-suffix stripping as rule_based.py, kept in sync deliberately —
# both taggers need the same notion of "Apple Inc." -> "Apple" for matching.
_SUFFIXES = [
    " Inc.", " Inc", " Corporation", " Corp.", " Corp",
    " PLC", " plc", " Ltd.", " Ltd", " Co.", " Company",
    " Group", " Holdings", ".com",
]


@dataclass
class _CompanyRef:
    entity_id: int
    name: str
    ticker_symbol: str | None


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation/whitespace, for tolerant comparison."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _name_variants(name: str) -> set[str]:
    variants = {name}
    trimmed = name
    changed = True
    while changed:
        changed = False
        for suffix in _SUFFIXES:
            if trimmed.endswith(suffix):
                trimmed = trimmed[: -len(suffix)].strip().rstrip(",").strip()
                if trimmed:
                    variants.add(trimmed)
                changed = True
    return variants


def match_span_to_company(span_text: str, companies: list[_CompanyRef]) -> int | None:
    """
    Pure matching logic, deliberately separated from spaCy itself so it can
    be unit-tested without needing the model loaded. Given one extracted
    ORG span's text, returns the matching entity_id, or None.
    """
    normalized_span = _normalize(span_text)
    if not normalized_span:
        return None

    for company in companies:
        candidates = {company.ticker_symbol} if company.ticker_symbol else set()
        candidates |= _name_variants(company.name)

        for candidate in candidates:
            normalized_candidate = _normalize(candidate)
            if not normalized_candidate:
                continue
            # Exact match, or one containing the other (handles "Apple" matching
            # "Apple Inc." and vice versa) — but guard against tiny strings
            # matching everything (e.g. a 2-character ticker inside an unrelated word).
            if normalized_span == normalized_candidate:
                return company.entity_id
            if len(normalized_candidate) >= 4 and (
                normalized_candidate in normalized_span or normalized_span in normalized_candidate
            ):
                return company.entity_id
    return None


class SpacyEntityTagger(BaseEntityTagger):
    """
    Tags COMPANY entities only, using spaCy's NER + name matching. Combine
    with RuleBasedEntityTagger (via HybridEntityTagger) for full coverage
    including indices/sectors/commodities.
    """

    def __init__(self, companies: list[_CompanyRef], model_name: str = "en_core_web_trf"):
        import spacy  # lazy import — see finbert_analyzer.py for the same pattern

        self._companies = companies
        logger.info("Loading spaCy model %s ...", model_name)
        self.nlp = spacy.load(model_name)
        logger.info("Loaded.")

    @classmethod
    def from_db_rows(cls, rows, model_name: str = "en_core_web_trf") -> "SpacyEntityTagger":
        return cls([_CompanyRef(*row) for row in rows], model_name=model_name)

    def tag(self, headline: str, body: str | None) -> list[EntityMention]:
        text = f"{headline} {body or ''}"
        doc = self.nlp(text)

        matched_counts: Counter = Counter()
        for ent in doc.ents:
            if ent.label_ != "ORG":
                continue
            entity_id = match_span_to_company(ent.text, self._companies)
            if entity_id is not None:
                matched_counts[entity_id] += 1

        return [EntityMention(entity_id=eid, mention_count=count) for eid, count in matched_counts.items()]
