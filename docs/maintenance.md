# Maintenance

Maintenance means keeping the app useful over time.

## Regular Checklist

Weekly or before important use:

1. Confirm the app starts.
2. Ask a known test question.
3. Check that sources appear.
4. Run evaluation.
5. Confirm API keys are still valid.

## Rebuild Local Corpus

Run after changing PDFs:

```bash
python -m scripts.02_prepare_energy_json
```

Expected result: `data/critical_infra_corpus.jsonl` is rewritten.

## Re-index Pinecone

Run after rebuilding the corpus:

```bash
python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --reset
```

Warning: `--reset` clears the selected index or namespace contents.

## Update Web Sources

Dry run first:

```bash
python -m scripts.06_ingest_web_sources --dry-run
```

Then ingest:

```bash
python -m scripts.06_ingest_web_sources
```

## Update Dependencies

This repository uses `requirements.txt`.

To update a package:

1. Edit the version in `requirements.txt`.
2. Install again:

   ```bash
   pip install -r requirements.txt
   ```

3. Run evaluation:

   ```bash
   python -m scripts.05_eval_grounding
   ```

TODO: Information could not be determined automatically: the project's dependency update policy.

## Monitor Logs

For local Streamlit:

- Watch the terminal where `streamlit run streamlit_app.py` is running.
- Errors and tracebacks appear there.

For scripts:

- Watch terminal output.
- `scripts/06_ingest_web_sources.py` logs progress and warnings.

## Recover From Failure

If answers become poor or sources disappear:

1. Check `.env`.
2. Rebuild corpus.
3. Re-index Pinecone.
4. Run evaluation.
5. Ask a known test question.
