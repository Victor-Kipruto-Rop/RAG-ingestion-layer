"""Conservative fuzzy matching and identifier resolution helpers.

Similarity identifies review candidates only. Conflicting official identifiers are
not silently merged or overwritten; they are sent to the ingestion dead-letter flow.
"""
import re
import unicodedata

from rapidfuzz.distance import JaroWinkler
from sqlalchemy import select

from .models import Organization

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


def find_existing_organization(db, registration_number, tax_pin):
    """Resolve an existing row only when supplied identifiers do not conflict."""
    by_registration = None
    by_tax_pin = None

    if registration_number:
        by_registration = db.scalar(
            select(Organization)
            .where(Organization.normalized_registration_number == registration_number)
            .limit(1)
        )
    if tax_pin:
        by_tax_pin = db.scalar(
            select(Organization)
            .where(Organization.normalized_tax_pin == tax_pin)
            .limit(1)
        )

    if by_registration and by_tax_pin and by_registration.id != by_tax_pin.id:
        raise ValueError(
            'identifier_conflict: registration number and tax PIN resolve to different records'
        )

    if by_registration and registration_number and tax_pin and by_registration.normalized_tax_pin:
        if by_registration.normalized_tax_pin != tax_pin:
            raise ValueError(
                'identifier_conflict: registration number is already associated with a different tax PIN'
            )

    if by_tax_pin and registration_number and by_tax_pin.normalized_registration_number:
        if by_tax_pin.normalized_registration_number != registration_number:
            raise ValueError(
                'identifier_conflict: tax PIN is already associated with a different registration number'
            )

    return by_registration or by_tax_pin
