"""
Rule-based entity tagger.

Matches article text against the names and ticker symbols already sitting in
the `entities` table — no ML model, no external download required.

Why this exists instead of the BRD's specified SpaCy NER: SpaCy's language
models are distributed via GitHub release assets, which this build
environment's network policy blocks (confirmed: a live download attempt
returned HTTP 403 from release-assets.githubusercontent.com). Rather than
ship untested code, this rule-based matcher is a fully working, fully tested
stand-in that satisfies the same requirement — populating article_entities —
using only the data already in the database.

Design:
    For each entity, build one case-insensitive regex combining:
      - the full entity name (e.g. "Apple Inc.")
      - "core" variants with common corporate suffixes stripped
        (e.g. "Apple Inc." -> "Apple")
      - the ticker symbol, if present (e.g. "AAPL")
    Variants are tried longest-first in a single alternation, so "Apple Inc."
    in the text is counted once (as the fuller match) rather than twice
    (once as "Apple Inc.", once again as "Apple").

Known limitation (worth noting in the report): short tickers that are also
common English words (e.g. a hypothetical ticker "ALL") can over-match.
Acceptable for a rule-based v1; a proper NER model resolves this by using
sentence context, which is exactly the upgrade path once SpaCy is available.
"""

import re
from dataclasses import dataclass

from app.entity_tagging.base import BaseEntityTagger, EntityMention

# Corporate suffixes stripped when deriving a shorter matchable name variant.
_SUFFIXES = [
    " Inc.", " Inc", " Corporation", " Corp.", " Corp",
    " PLC", " plc", " Ltd.", " Ltd", " Co.", " Company",
    " Group", " Holdings", ".com",
]


@dataclass
class _EntityRef:
    entity_id: int
    name: str
    ticker_symbol: str | None


def _name_variants(name: str) -> list[str]:
    """Return the full name plus progressively suffix-stripped variants, longest first."""
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
    return sorted(variants, key=len, reverse=True)


def _build_pattern(entity: _EntityRef) -> re.Pattern:
    parts = [re.escape(v) for v in _name_variants(entity.name)]
    if entity.ticker_symbol:
        parts.append(re.escape(entity.ticker_symbol))
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)


class RuleBasedEntityTagger(BaseEntityTagger):
    """
    Matches article text against a fixed list of known entities.

    Patterns are precompiled once in __init__ for efficiency across many
    articles in a single pipeline run.
    """

    def __init__(self, entities: list[_EntityRef]):
        self._entities = entities
        self._patterns: dict[int, re.Pattern] = {
            e.entity_id: _build_pattern(e) for e in entities
        }

    @classmethod
    def from_db_rows(cls, rows: list[tuple[int, str, str | None]]) -> "RuleBasedEntityTagger":
        """Build from (entity_id, name, ticker_symbol) tuples, e.g. a DB query result."""
        return cls([_EntityRef(*row) for row in rows])

    def tag(self, headline: str, body: str | None) -> list[EntityMention]:
        text = f"{headline} {body or ''}"
        mentions: list[EntityMention] = []
        for entity_id, pattern in self._patterns.items():
            count = len(pattern.findall(text))
            if count > 0:
                mentions.append(EntityMention(entity_id=entity_id, mention_count=count))
        return mentions
