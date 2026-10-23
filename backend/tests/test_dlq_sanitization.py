from src.worker import _sanitize_dlq_row


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
