# PesaGuard Datasource sandbox integration

This guide connects the PesaGuard backend to a Datasource sandbox. It does not connect a browser directly to Datasource and does not authorize a production release.

## 1. Start an isolated local Datasource

From PowerShell in the cloned pesaguard-datasource repository:

```powershell
Copy-Item example.env .env
notepad .env
```

Replace both placeholders with separate, long random local-only values:
- `REGISTRY_API_KEYS`: legacy local key for the dashboard and existing smoke test.
- `DATASOURCE_ADMIN_TOKEN`: operator-only token used to create and revoke managed keys.

Generate a random value in PowerShell with:

```powershell
[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

Set `DATASOURCE_ENVIRONMENT=sandbox`. Leave R2 settings blank. Do not put production database URLs, production keys, or R2 credentials in this local file.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start-windows-local.ps1
.\scripts\test-local-stack.ps1
```

The local stack uses SQLite, local file storage, and the sandbox environment. It does not use Supabase, production R2, or the production datasource. The local Alembic upgrade creates the managed API-key tables.

- Dashboard: http://localhost:5173
- API docs: http://localhost:8000/docs
- Readiness: http://localhost:8000/health/ready

If startup or migration fails, inspect `docker compose logs --tail 150 registry-api`. Do not use the production database as a workaround.

## 2. Create and test a sandbox key

After the stack is running and `.env` contains both local-only secrets, run:

```powershell
.\scripts\create-sandbox-key.ps1
```

The helper creates a 90-day key with only `registry:read`, tests search and metrics against localhost, and prints the secret once. Save it directly into the PesaGuard backend's local secret configuration. Do not paste it into chat, commit it, or place it in React/VITE variables. You can also create the key from the dashboard's **API Keys** page using the local operator token.

A managed key begins with `pg_sandbox_`. A sandbox key presented to a production-configured datasource must return HTTP 403 and `API_KEY_ENVIRONMENT_MISMATCH`.

## 3. Configure the PesaGuard backend

Add these server-side variables to the PesaGuard backend's local `.env` (adapt the names to the project's existing configuration conventions):

```dotenv
PESAGUARD_DATASOURCE_BASE_URL=http://127.0.0.1:8000
PESAGUARD_DATASOURCE_API_KEY=<the-pg_sandbox-key>
PESAGUARD_DATASOURCE_ENVIRONMENT=sandbox
```

Choose the base URL based on where PesaGuard runs:

| PesaGuard backend location | Datasource base URL |
| --- | --- |
| Directly on this Windows machine | `http://127.0.0.1:8000` |
| In a container sharing the datasource Compose network | `http://registry-api:8000` |
| In a separate local Compose project | Use a deliberately shared Docker network/service DNS or a host-gateway URL configured for that container |
| Deployed remotely | Use the HTTPS URL of a separately configured Datasource sandbox deployment |

Do not point PesaGuard at `https://pesaguard-datasource.onrender.com` until the deployment owner has explicitly confirmed it is configured as sandbox. Its environment is not assumed here.

### Example server-side Python client

This example uses `httpx`; install it in the PesaGuard backend environment if it is not already installed.

```python
import os
import httpx

BASE_URL = os.environ["PESAGUARD_DATASOURCE_BASE_URL"].rstrip("/")
API_KEY = os.environ["PESAGUARD_DATASOURCE_API_KEY"]
ENVIRONMENT = os.environ.get("PESAGUARD_DATASOURCE_ENVIRONMENT", "sandbox")

if ENVIRONMENT != "sandbox" or not API_KEY.startswith("pg_sandbox_"):
    raise RuntimeError("Refusing to run sandbox integration with a non-sandbox key/environment.")

def lookup_organization(registration_number=None, tax_pin=None):
    if bool(registration_number) == bool(tax_pin):
        raise ValueError("Provide exactly one of registration_number or tax_pin.")
    params = {"reg_no": registration_number} if registration_number else {"tax_pin": tax_pin}
    response = httpx.get(
        f"{BASE_URL}/api/v1/registry/lookup",
        params=params,
        headers={"X-API-Key": API_KEY, "X-Caller-Service": "pesaguard-backend"},
        timeout=10.0,
    )
    if response.status_code == 403:
        detail = response.json().get("detail", {})
        if isinstance(detail, dict) and detail.get("code") == "API_KEY_ENVIRONMENT_MISMATCH":
            raise RuntimeError("Datasource rejected a key from the wrong environment.")
        if isinstance(detail, dict) and detail.get("code") == "API_KEY_SCOPE_DENIED":
            raise RuntimeError("Datasource key lacks registry:read permission.")
    response.raise_for_status()
    return response.json()
```

Only call this from a trusted PesaGuard backend. Never expose the key via `VITE_*`, React, mobile apps, HTML, or API responses.

## 4. Interpret results safely

- `record_found`: a matching record exists in the imported dataset. It is not proof of current registration, KRA standing, ownership, or successful KYB.
- `not_found`: no matching record exists in the current internal dataset. It does not prove the organization is invalid.
- Timeouts/5xx: treat the datasource as temporarily unavailable; use bounded retries and do not silently mark an organization verified.
- `API_KEY_ENVIRONMENT_MISMATCH`: stop and correct the URL/key pairing. Never retry the same key against production.
- `API_KEY_SCOPE_DENIED`: create a key with the minimum required scope; do not broaden scopes without a reason.

PesaGuard should persist source, lookup timestamp, response status, and request/correlation ID where available, and present the result as registry-data evidence for review.

## 5. Remote sandbox readiness

A remote sandbox needs its own deployment, isolated database, `DATASOURCE_ENVIRONMENT=sandbox`, a unique operator token, approved sandbox storage if needed, and the additive schema migration applied after review/backup. Only create a remote key after the deployment owner confirms the environment. Store the key in the PesaGuard deployment's server-side secret manager.

Do not apply migrations to production, rotate production keys, or deploy this branch as part of local testing.
