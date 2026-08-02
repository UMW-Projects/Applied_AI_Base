# Troubleshooting

This page lists common problems, causes, fixes, and verification steps.

## App Will Not Start

Symptoms:

```text
streamlit: command not found
```

Cause: dependencies are not installed or the virtual environment is not active.

Resolution:

```bash
source venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Verification: Streamlit prints a local URL.

## Missing OpenAI Key

Symptoms:

```text
Missing env var: OPENAI_API_KEY
```

Cause: `.env` is missing or does not include `OPENAI_API_KEY`.

Resolution:

1. Open `.env`.
2. Add:

   ```text
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. Restart the app.

Verification: ask a question again.

## Missing Pinecone Key

Symptoms:

```text
Missing OPENAI_API_KEY or PINECONE_API_KEY
```

Cause: the indexing script needs both keys.

Resolution:

```text
PINECONE_API_KEY=your_pinecone_api_key_here
```

Verification:

```bash
python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl
```

## Wrong Pinecone Index

Symptoms:

- Empty search results.
- Weak answers.
- Pinecone index not found errors.

Cause: `PINECONE_INDEX` points to an index that does not exist or does not contain this corpus.

Resolution:

1. Check `.env`.
2. Confirm the index name in Pinecone.
3. Re-run indexing:

   ```bash
   python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --reset
   ```

Verification: run a CLI query and check that sources are returned.

## `No module named app`

Symptoms:

```text
ModuleNotFoundError: No module named 'app'
```

Cause: command was run as a direct file path from the wrong context.

Resolution:

Run scripts with `python -m` from the project root:

```bash
python -m scripts.04_query_bot --q "test question"
```

Verification: output JSON appears.

## PDF Text Looks Bad

Symptoms:

- Strange spacing.
- Broken words.
- Missing text.

Cause: PDF extraction depends on the PDF's internal text layer. Some PDFs are scanned images or have unusual formatting.

Resolution:

1. Check the source PDF.
2. Replace it with a better text-based PDF if available.
3. Rebuild the corpus.

Verification:

```bash
python -m scripts.02_prepare_energy_json
```

Then inspect relevant lines in `data/critical_infra_corpus.jsonl`.

## SerpAPI Search Does Nothing

Symptoms:

- No live web sources appear.
- Debug JSON shows zero SerpAPI documents.

Cause:

- No SerpAPI key.
- `ENABLE_SERPAPI_SEARCH=false`.
- SerpAPI package or account unavailable.

Resolution:

1. Add `SERPAPI_API_KEY`.
2. Set `ENABLE_SERPAPI_SEARCH=true`.
3. Restart the app.

Verification:

```bash
python -m scripts.06_ingest_web_sources --query "CISA energy sector ICS advisory" --dry-run
```

## Evaluation Fails

Symptoms:

```text
Evaluation finished with ... failing queries.
```

Cause: a sample answer did not include required fields or grounding IDs.

Resolution:

1. Check `data/eval_results.jsonl`.
2. Confirm Pinecone contains the corpus.
3. Rebuild and re-index.
4. Run evaluation again.

Verification:

```bash
python -m scripts.05_eval_grounding
```
