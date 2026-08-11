"""
Hybrid entity tagger. Companies go through spaCy; everything else
(indices, sectors, commodities) goes through rule-based regex. Reason
being those are common nouns, not proper nouns, so they fall outside
what spaCy's NER is built to recognize in the first place — it's not
a matter of tuning it better. Full writeup's in spacy_tagger.py's
module docstring.

When both taggers pick up the same entity, we go with the regex
tagger's mention_count — plain regex counting is just more exact for
literal occurrence counts than spaCy's span count. If spaCy catches a
company the regex missed (usually down to phrasing), that entity
still makes it in, using spaCy's count instead.
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
