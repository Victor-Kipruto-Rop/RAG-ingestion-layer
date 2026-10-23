"""Conservative fuzzy matching helpers. Similarity identifies review candidates, never proof of identity."""
import re
import unicodedata
from rapidfuzz.distance import JaroWinkler

_LEGAL_SUFFIXES = {
    'LIMITED', 'LTD', 'LTD.', 'PLC', 'LLC', 'INC', 'INCORPORATED',
    'CORPORATION', 'CORP', 'COMPANY', 'CO', 'CO.', 'LLP', 'LP',
    'PUBLIC', 'PRIVATE', 'PTY',
}

def normalize_name_for_match(value):
    if not value:
        return ''
    text = unicodedata.normalize('NFKC', str(value)).upper()
    tokens = re.findall(r'[A-Z0-9]+', text)
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return ' '.join(tokens)

def similarity_score(left, right):
    left_norm = normalize_name_for_match(left)
    right_norm = normalize_name_for_match(right)
    if not left_norm or not right_norm:
        return 0.0
    return round(JaroWinkler.normalized_similarity(left_norm, right_norm) * 100, 2)

def is_review_candidate(left, right, threshold=92.0):
    return similarity_score(left, right) >= float(threshold)
