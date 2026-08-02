# Contributing

This guide explains how to make changes without surprising future users.

## Before You Change Code

1. Read [Architecture](architecture.md).
2. Read [Developer Guide](developer-guide.md).
3. Start the app locally.
4. Run the evaluation script.

```bash
python -m scripts.05_eval_grounding
```

Expected result: sample queries pass or clearly report what failed.

## Documentation Changes

When changing docs:

1. Keep language plain.
2. Explain every command.
3. Mark unknowns instead of guessing.
4. Keep README and `docs/` consistent.
5. Add screenshot placeholders when screenshots are not available.

Use this phrase when the repository does not reveal an answer:

```text
TODO: Information could not be determined automatically.
```

## Code Changes

When changing code:

1. Keep retrieval grounded in source chunks.
2. Preserve source citations.
3. Do not invent document IDs.
4. Avoid changing metadata shape unless you also update indexing and docs.
5. Run evaluation after changes.

## Adding Source Documents

1. Add PDFs to `data/pdf/`.
2. Rebuild the corpus:

   ```bash
   python -m scripts.02_prepare_energy_json
   ```

3. Re-index Pinecone:

   ```bash
   python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --reset
   ```

4. Run evaluation:

   ```bash
   python -m scripts.05_eval_grounding
   ```

## Commit Checklist

Before committing:

- App starts locally.
- Evaluation has been run or the reason it was skipped is documented.
- `.env` is not committed.
- Generated cache folders are not committed.
- Documentation matches the changed behavior.

TODO: Information could not be determined automatically: the preferred branch, pull request, and code review process.
