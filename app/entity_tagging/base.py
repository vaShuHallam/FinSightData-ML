"""
Base interface for entity taggers.

Mirrors app/ingestion/base.py's pattern: any tagging strategy (rule-based
matching now, SpaCy NER later) implements this same contract, so the
saving/pipeline logic doesn't care which one produced the mentions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EntityMention:
    """A single detected mention of a known entity within an article."""

    entity_id: int
    mention_count: int


class BaseEntityTagger(ABC):
    """Common contract for all entity-tagging strategies."""

    @abstractmethod
    def tag(self, headline: str, body: str | None) -> list[EntityMention]:
        """
        Return every known entity mentioned in this article's text, with a
        count of how many times each was mentioned.
        """
        raise NotImplementedError
