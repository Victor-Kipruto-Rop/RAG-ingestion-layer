import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.entity_resolution import find_existing_organization
from src.models import Organization


@pytest.fixture
def registry_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Organization(
                id="org-a",
                legal_name="Alpha Limited",
                normalized_legal_name="ALPHA LIMITED",
                registration_number="REG-A",
                normalized_registration_number="REG-A",
                tax_pin="PIN-A",
                normalized_tax_pin="PIN-A",
            ),
            Organization(
                id="org-b",
                legal_name="Beta Limited",
                normalized_legal_name="BETA LIMITED",
                registration_number="REG-B",
                normalized_registration_number="REG-B",
                tax_pin="PIN-B",
                normalized_tax_pin="PIN-B",
            ),
        ])
        db.commit()
        yield db
    engine.dispose()


def test_matching_registration_and_tax_pin_resolve_same_record(registry_db):
    result = find_existing_organization(registry_db, "REG-A", "PIN-A")
    assert result is not None
    assert result.id == "org-a"


def test_registration_and_pin_pointing_to_different_records_are_rejected(registry_db):
    with pytest.raises(ValueError, match="identifier_conflict"):
        find_existing_organization(registry_db, "REG-A", "PIN-B")


def test_existing_registration_with_changed_tax_pin_is_rejected(registry_db):
    with pytest.raises(ValueError, match="different tax PIN"):
        find_existing_organization(registry_db, "REG-A", "PIN-NEW")


def test_existing_tax_pin_with_different_registration_is_rejected(registry_db):
    with pytest.raises(ValueError, match="different registration number"):
        find_existing_organization(registry_db, "REG-NEW", "PIN-A")
