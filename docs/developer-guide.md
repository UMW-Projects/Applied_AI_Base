# Developer Guide

This guide is for maintainers who plan to change code.

## Local Development Setup

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create `.env`.
4. Run the app:

   ```bash
   streamlit run streamlit_app.py
   ```

## Important Code Paths

### `streamlit_app.py`

Handles:

- Page setup and styling.
- Chat sessions.
- Sidebar controls.
- Quick prompts.
- Rendering structured response sections.

### `app/rag.py`

Handles:

- Query intent detection.
- Pinecone retrieval.
- Local fallback retrieval.
- Optional web search.
- Prompt construction.
- OpenAI generation.
- JSON parsing and output cleanup.

### `scripts/02_prepare_energy_json.py`

Extracts text from PDFs.

Current behavior:

- Reads every PDF in `data/pdf/`.
- Uses `PyPDF2`.
- Uses a fixed chunk size of 800 characters.
- Labels all generated chunks with organization `NERC`, sector `Energy`, document type `Standard`, and regulation family `NERC CIP`.

Maintainer note: these labels may be too broad for the mixed PDF collection. Change carefully because downstream retrieval and filters use metadata.

### `scripts/03_index_pinecone.py`

Indexes corpus chunks into Pinecone.

Current behavior:

- Infers embedding dimension from the first chunk.
- Creates the Pinecone index if missing.
- Optionally clears the index with `--reset`.
- Adds control-family metadata.

### `scripts/06_ingest_web_sources.py`

Discovers and ingests web sources.

Current behavior:

- Uses SerpAPI when configured.
- Allows direct URLs.
- Prefers selected government, research, and energy-sector domains.
- Scrapes HTML or PDF content.
- Skips likely duplicates by similarity check.
- Upserts novel chunks into Pinecone.

## Response Shape

General answers may include:

- `answer_summary`
- `key_points`
- `attack_vectors`
- `risk_categories`
- `sources`
- `used_chunk_ids`
- `confidence`
- `retrieval_sources`

Workflow answers may include:

- `answer_summary`
- `key_requirements`
- `policy_recommendations`
- `draft_policy_language`
- `sources`

## Evaluation

Run:

```bash
python -m scripts.05_eval_grounding
```

This checks:

- Response shape.
- Required fields.
- Grounding chunk IDs.

It writes:

```text
data/eval_results.jsonl
```

## Coding Notes

- Keep generated claims tied to retrieved chunks.
- Do not invent source IDs.
- Keep `.env` out of Git.
- Use `python -m scripts.name` from the project root.
- Be careful with `--reset`; it clears Pinecone index contents.

## Known Maintainability Issues

- `control_families.py` appears both at the root and inside `app/`.
- `config.py` contains Chroma settings, but current retrieval uses Pinecone.
- No automated unit test suite was found.
- No CI configuration was found.
