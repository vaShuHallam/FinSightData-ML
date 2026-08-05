"""
Hybrid entity tagger: spaCy for companies, rule-based regex for everything
else (indices, sectors, commodities — categories spaCy's NER structurally
can't recognize, since they're common nouns, not proper-noun named
entities). See spacy_tagger.py's module docstring for the full reasoning.

Merge policy when both taggers find the same entity: use the rule-based
tagger's mention_count (exact regex counting is more precise for counting
literal occurrences than spaCy's span count). Entities found ONLY by
spaCy (company mentions the regex missed due to phrasing/context) are
still included, using spaCy's count.
"""

from app.entity_tagging.base import BaseEntityTagger, EntityMention
from app.entity_tagging.rule_based import RuleBasedEntityTagger
from app.entity_tagging.spacy_tagger import SpacyEntityTagger


class HybridEntityTagger(BaseEntityTagger):
    def __init__(self, rule_based: RuleBasedEntityTagger, spacy_tagger: SpacyEntityTagger):
        self._rule_based = rule_based
        self._spacy = spacy_tagger

    def tag(self, headline: str, body: str | None) -> list[EntityMention]:
        rule_based_mentions = {m.entity_id: m.mention_count for m in self._rule_based.tag(headline, body)}
        spacy_mentions = {m.entity_id: m.mention_count for m in self._spacy.tag(headline, body)}

        merged: dict[int, int] = dict(rule_based_mentions)  # rule-based counts take precedence
        for entity_id, count in spacy_mentions.items():
            if entity_id not in merged:
                merged[entity_id] = count

        return [EntityMention(entity_id=eid, mention_count=count) for eid, count in merged.items()]
