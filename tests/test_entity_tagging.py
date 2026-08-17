from app.entity_tagging.rule_based import RuleBasedEntityTagger


def test_entity_tagger_matches_full_name_core_name_and_ticker_without_double_counting():
    tagger = RuleBasedEntityTagger.from_db_rows([(1, "Apple Inc.", "AAPL")])

    mentions = tagger.tag(
        "Apple Inc. reports strong results",
        "Apple expects growth, while AAPL gains in pre-market trading.",
    )

    assert len(mentions) == 1
    assert mentions[0].entity_id == 1
    assert mentions[0].mention_count == 3


def test_entity_tagger_is_case_insensitive():
    tagger = RuleBasedEntityTagger.from_db_rows([(1, "Microsoft Corporation", "MSFT")])

    mentions = tagger.tag("microsoft announces results", "MSFT shares rise as MICROSOFT forecasts growth")

    assert mentions[0].entity_id == 1
    assert mentions[0].mention_count == 3


def test_entity_tagger_detects_multiple_known_entities():
    tagger = RuleBasedEntityTagger.from_db_rows(
        [
            (1, "Apple Inc.", "AAPL"),
            (2, "Microsoft Corporation", "MSFT"),
        ]
    )

    mentions = tagger.tag("Apple and Microsoft compete", "AAPL rises while MSFT falls")
    by_entity = {mention.entity_id: mention.mention_count for mention in mentions}

    assert by_entity == {1: 2, 2: 2}


def test_entity_tagger_returns_empty_list_when_no_entity_matches():
    tagger = RuleBasedEntityTagger.from_db_rows([(1, "Apple Inc.", "AAPL")])

    assert tagger.tag("Tesla raises guidance", "TSLA shares gain") == []


def test_entity_tagger_does_not_match_ticker_inside_larger_word():
    tagger = RuleBasedEntityTagger.from_db_rows([(1, "Apple Inc.", "AAPL")])

    assert tagger.tag("The word AAPLXYZ is not a ticker mention", None) == []


def test_entity_tagger_handles_missing_article_body():
    tagger = RuleBasedEntityTagger.from_db_rows([(1, "NVIDIA Corporation", "NVDA")])

    mentions = tagger.tag("NVIDIA reports results", None)

    assert mentions[0].entity_id == 1
    assert mentions[0].mention_count == 1
