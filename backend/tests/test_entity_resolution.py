from src.entity_resolution import normalize_name_for_match, similarity_score, is_review_candidate


def test_legal_suffixes_are_ignored_for_match_scoring():
    assert normalize_name_for_match('Acme Trading Limited') == normalize_name_for_match('ACME TRADING LTD')
    assert similarity_score('Acme Trading Limited', 'ACME TRADING LTD') == 100.0


def test_minor_spelling_variation_is_a_review_candidate():
    assert is_review_candidate('Greenfield Enterprizes Ltd', 'Greenfield Enterprises Limited', threshold=90)


def test_unrelated_names_do_not_match_at_high_threshold():
    assert not is_review_candidate('Greenfield Enterprises Ltd', 'Nairobi Transport Company', threshold=92)
