# PesaGuard Registry Python SDK

## Install locally

```bash
python -m pip install -e ".[test]"
```

## Sandbox example

Use a sandbox key beginning with `pg_sandbox_`. Keep it in an environment variable and never put it in browser JavaScript.

```python
import os
from pesaguard import PesaGuardClient

with PesaGuardClient(
    os.environ["PESAGUARD_API_KEY"],
    environment="sandbox",
) as client:
    print(client.search("sample organization", limit=10))
    # Or use one exact identifier:
    # print(client.lookup(registration_number="CPR/12345"))
```

For production, use `environment="production"` and a `pg_live_` key issued only after production access approval. The default hosts are intentionally separate:

- Sandbox: `https://sandbox-api.pesaguard.co.ke`
- Production: `https://api.pesaguard.co.ke`

The client rejects a key prefix that does not match its selected environment, and rejects using the known opposite-environment host. A custom HTTPS gateway can be supplied with `base_url` when its routing and environment isolation have been verified.

## Supported methods

- `search(query, limit=20)` — registry-name search.
- `lookup(registration_number=...)` or `lookup(tax_pin=...)` — exact identifier lookup; supply exactly one.
- `PesaGuardError` — API/network errors, with `status_code` and `response_body` where available.

This client uses the public read-only lookup/search surface. It does not create payments, certify government records, or grant access to internal ingestion or warehouse operations.


## Webhook signature verification

Verify the exact raw request body before parsing JSON. The timestamped HMAC verifier uses a constant-time comparison and a default five-minute replay window:

```python
from pesaguard import verify_webhook_signature

raw_body = request.get_data(cache=True, as_text=False)  # Flask example
signature = request.headers.get("PesaGuard-Signature", "")
if not verify_webhook_signature(raw_body, signature, webhook_secret):
    abort(401)
```

Run SDK tests with `python -m pip install -e ".[test]" && pytest`.
