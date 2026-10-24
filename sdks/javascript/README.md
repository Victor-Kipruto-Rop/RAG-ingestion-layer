# PesaGuard Registry JavaScript SDK

Node.js 18+ or a modern runtime with the Fetch API is required.

```bash
npm test
```

```js
import { PesaGuardClient } from "@pesaguard/registry";

const client = new PesaGuardClient({
  apiKey: process.env.PESAGUARD_API_KEY,
  environment: "sandbox",
});
const candidates = await client.search("sample organization", { limit: 10 });
console.log(candidates.items);
```

Use `environment: "production"` only with an approved `pg_live_` key and the production host. The SDK rejects mismatched key prefixes and the known opposite-environment host. Keep keys in server-side environment variables; do not bundle production keys into frontend applications.

Supported methods: `search(query, {limit})` and `lookup({registrationNumber})` or `lookup({taxPin})`. This SDK exposes the read-only registry surface only.


## Webhook signature verification

Verify the exact raw request body before JSON parsing:

```js
import { verifyWebhookSignature } from "@pesaguard/registry";

const rawBody = req.rawBody; // Buffer captured by the HTTP server before JSON parsing
const signature = req.headers["pesaguard-signature"] || "";
if (!verifyWebhookSignature(rawBody, signature, process.env.PESAGUARD_WEBHOOK_SECRET)) {
  res.status(401).end();
  return;
}
```

Run the SDK's offline contract tests with `npm test`.
