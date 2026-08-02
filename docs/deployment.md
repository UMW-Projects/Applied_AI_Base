# Deployment

Deployment means running the app somewhere other people can access it.

## Current Repository Status

TODO: Information could not be determined automatically.

The repository does not include:

- Dockerfile.
- Docker Compose file.
- Cloud deployment configuration.
- Process manager configuration.
- Reverse proxy configuration.
- Production secrets instructions.

## Local-Only Run

The known supported run command is:

```bash
streamlit run streamlit_app.py
```

Expected result: Streamlit starts a local server, usually on port `8501`.

## Production Considerations

Before deploying for a team, decide:

1. Where Streamlit will run.
2. How secrets will be stored.
3. Who can access the app.
4. How logs will be monitored.
5. How Pinecone indexes will be backed up or recreated.
6. Whether live web search should be enabled.

## Minimal Deployment Checklist

- Python installed on the server.
- Project dependencies installed.
- `.env` or secure environment variables configured.
- Network access to OpenAI and Pinecone.
- Streamlit exposed only to approved users.
- Backups for `data/pdf/` and `data/critical_infra_corpus.jsonl`.
- Re-indexing procedure documented for your team.

## Security Warning

This app does not include built-in user login. Do not expose it directly to the public internet unless you add access control outside the app.
