from src.worker import _sanitize_dlq_row, _sanitize_diagnostic


def test_dlq_row_redacts_sensitive_fields_but_keeps_corporate_identity():
    safe = _sanitize_dlq_row({
        'legal_name': 'Example Limited',
        'registration_number': 'CPR-123',
        'tax_pin': 'A123456789Z',
        'contact_email': 'person@example.test',
        'phone': '+254700000000',
    })
    assert safe['legal_name'] == 'Example Limited'
    assert safe['registration_number'] == 'CPR-123'
    assert safe['tax_pin'] == '[REDACTED]'
    assert safe['contact_email'] == '[REDACTED]'
    assert safe['phone'] == '[REDACTED]'


def test_dlq_diagnostics_redact_sensitive_values():
    row = {'tax_pin': 'A123456789Z', 'legal_name': 'Example Limited'}
    message = _sanitize_diagnostic('Bad value A123456789Z in Example Limited', row)
    assert 'A123456789Z' not in message
    assert '[REDACTED]' in message
