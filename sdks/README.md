# PesaGuard Developer SDK starters

These language-specific starter clients use the public HTTP API contract. They are lightweight reference implementations, not a claim that packages have been published to package registries. Pin reviewed dependencies and run the examples in your own CI before production use.

## Environment isolation

| Environment | Base URL | Required key prefix |
|---|---|---|
| Sandbox | `https://sandbox-api.pesaguard.co.ke` | `pg_sandbox_` |
| Production | `https://api.pesaguard.co.ke` | `pg_live_` |

The backend deployment must set `API_ENVIRONMENT=sandbox` or `API_ENVIRONMENT=production` consistently with its DNS route. It rejects keys from the other environment. Production credentials are issued only after a production-access request is approved and the workspace is verified. Never embed API keys in browser bundles, mobile apps, source control, or client-side environment variables.

## Available starters

- JavaScript / Node: `javascript/client.js` (Node 18+)
- Python: `python/pesaguard_client.py` (Python 3.10+, `requests`)
- PHP: `php/PesaGuardClient.php` (PHP 8.1+, cURL)
- Go: `go/client.go` (Go 1.21+)
- Java: `java/PesaGuardClient.java` (Java 17+)
- Ruby: `ruby/pesaguard_client.rb` (Ruby 3.1+, `net/http`)
- C#: `csharp/PesaGuardClient.cs` (.NET 8)

The dashboard's SDKs & Testing page also provides copyable cURL, JavaScript, Python, PHP, Go, Java, Ruby, and C# request examples and a sandbox-only API Explorer. The API's live OpenAPI document remains authoritative: `/openapi.json`, `/docs`, and `/redoc`.

## Contract

Each client must:
1. Require the API key from a server-side environment variable or secret manager.
2. Check key prefix against the selected environment before sending.
3. Use a bounded timeout and fail loudly on non-success HTTP status.
4. Avoid logging the API key or sensitive response data.
5. Keep production calls on the production hostname; never use sandbox credentials for live data.
