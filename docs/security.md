# Security

This project handles cybersecurity research data and secret API keys. Treat it carefully.

## Secrets

Secrets include:

- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `SERPAPI_API_KEY`
- `SERPAPI_KEY`

Rules:

1. Store secrets in `.env` for local use.
2. Do not commit `.env`.
3. Do not paste keys into screenshots.
4. Rotate keys if they are exposed.

## User Access

No built-in user login was found.

If deploying beyond your own computer, protect access with external controls such as:

- VPN.
- Private network.
- Reverse proxy authentication.
- Cloud identity access.

## Data Sensitivity

The project sends retrieved context to OpenAI for answer generation. Do not add confidential, regulated, or sensitive documents unless your organization has approved that use.

## Web Ingestion Risk

The web ingestion script can ingest external content.

Use trusted sources when possible. The script prefers domains such as:

- `cisa.gov`
- `energy.gov`
- `nist.gov`
- `ferc.gov`
- `nerc.com`
- National lab and research domains

Be careful with `--allow-any-domain`. It can ingest less trusted content.

## Dependency Risk

Dependencies are installed from Python package indexes. Keep them updated and review changes before production use.

## Incident Response

If a key is leaked:

1. Revoke the key in the provider dashboard.
2. Create a new key.
3. Update `.env` or deployment secrets.
4. Restart the app.
5. Review provider usage logs.
