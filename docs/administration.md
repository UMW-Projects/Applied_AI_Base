# Administration

Administration means keeping the app's data and settings healthy.

## Add New PDFs

1. Place PDF files in `data/pdf/`.
2. Rebuild the corpus:

   ```bash
   python -m scripts.02_prepare_energy_json
   ```

3. Re-index in Pinecone:

   ```bash
   python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --reset
   ```

Expected result: Pinecone contains vectors for the updated corpus.

## Change the Pinecone Index

1. Open `.env`.
2. Change:

   ```text
   PINECONE_INDEX=your-new-index-name
   ```

3. Re-run indexing:

   ```bash
   python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl
   ```

Expected result: the app searches the new index.

## Use a Namespace

A namespace separates groups of vectors inside the same Pinecone index.

Index into a namespace:

```bash
python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --namespace nerc-cip
```

Then set:

```text
PINECONE_NAMESPACE=nerc-cip
```

Expected result: the app searches only that namespace.

## Refresh Web Sources

Run default discovery:

```bash
python -m scripts.06_ingest_web_sources
```

Run a specific query:

```bash
python -m scripts.06_ingest_web_sources --query "CISA energy sector ICS advisory"
```

Run direct URLs:

```bash
python -m scripts.06_ingest_web_sources --url https://example.gov/source
```

Preview only:

```bash
python -m scripts.06_ingest_web_sources --dry-run
```

## Run Evaluation

```bash
python -m scripts.05_eval_grounding
```

Expected result: pass or failure messages and `data/eval_results.jsonl`.

## Restart the App

1. In the terminal running Streamlit, press `Control+C`.
2. Start it again:

   ```bash
   streamlit run streamlit_app.py
   ```
