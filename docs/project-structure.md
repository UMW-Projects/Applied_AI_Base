# Project Structure

This page explains the major files and folders.

```text
.
├── app/
├── data/
├── docs/
├── scripts/
├── config.py
├── control_families.py
├── requirements.txt
├── streamlit_app.py
└── README.md
```

## Root Files

| File | Meaning |
| --- | --- |
| `README.md` | Main landing page and quick start. |
| `requirements.txt` | Python libraries to install. |
| `streamlit_app.py` | Browser app. |
| `config.py` | Environment loading helpers. |
| `control_families.py` | Keyword detection helper used by scripts. |

## `app/`

Contains core application code.

| File | Meaning |
| --- | --- |
| `app/__init__.py` | Marks `app/` as a Python package. |
| `app/rag.py` | Main retrieval and answer engine. |
| `app/control_families.py` | Control-family keyword detection. |

## `scripts/`

Contains command-line tools.

| File | Meaning |
| --- | --- |
| `02_prepare_energy_json.py` | Extracts text from PDFs and writes JSONL chunks. |
| `03_index_pinecone.py` | Uploads corpus vectors to Pinecone. |
| `04_query_bot.py` | Runs a question from the terminal. |
| `05_eval_grounding.py` | Runs sample grounded-response checks. |
| `06_ingest_web_sources.py` | Adds web sources to Pinecone. |

## `data/`

Contains local knowledge sources and generated data.

| Path | Meaning |
| --- | --- |
| `data/pdf/` | Source PDFs. |
| `data/critical_infra_corpus.jsonl` | Extracted text chunks. |
| `data/eval_results.jsonl` | Created by evaluation script when run. |

## `docs/`

Contains end-user and maintainer documentation.

## Generated or Local-Only Folders

These may exist locally but should not be treated as project source:

- `venv/`: local Python virtual environment.
- `__pycache__/`: Python cache files.
- `.git/`: Git repository metadata.
