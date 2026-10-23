from src.ingestion.normalizer import normalize_record


def test_registry_payload_drops_personal_fields_and_keeps_company_flags():
    record = normalize_record({
        'Company Name': 'Example Limited',
        'Registration Number': 'CPR-123',
        'Tax PIN': 'TEST-CORP-PIN',
        'Director Name': 'SAMPLE PERSON',
        'Director Email': 'redacted-value',
        'Contact Phone': 'redacted-value',
        'Company Compliance Flag': 'CLEAR',
        'Sanctions Status': 'NOT_LISTED',
    })
    payload = record['registry_payload']
    assert 'director_name' not in payload
    assert 'director_email' not in payload
    assert 'contact_phone' not in payload
    assert payload['company_compliance_flag'] == 'CLEAR'
    assert payload['sanctions_status'] == 'NOT_LISTED'
    assert record['tax_pin'] == 'TEST-CORP-PIN'
