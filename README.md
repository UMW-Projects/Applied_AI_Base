# Cybersecurity RAG Assistant

This project is a local question-answering application for critical infrastructure sector cybersecurity research. It helps users ask plain-English questions about critical infrastructure cybersecurity and receive answers grounded in a document collection.

The application is built with Python, Streamlit, OpenAI, and Pinecone. In simple terms:

- Python runs the application.
- Streamlit provides the browser-based chat screen.
- OpenAI turns questions and documents into searchable meaning and writes the final answer.
- Pinecone stores searchable document chunks.

## Who This Is For

This project is for:

- Critical sector cybersecurity analysts.
- Policy researchers 
- Developers maintaining a retrieval-augmented generation system.

It is not a general chatbot. It is designed for grounded analysis over critical infrastructure cybersecurity documents.

## What It Can Do

- Answer questions about critical sector cybersecurity risks.
- Retrieve evidence from local PDF-derived text chunks.
- Cite the source documents used for an answer.
- Group findings by cybersecurity control family.
- Draft policy recommendations and action plans.
- Refresh the knowledge base with selected web sources.
- Run through a browser interface or a command-line script.

## Screenshots

![Streamlit chat screen](image/chat.png)

![Answer with sources expanded](image/answer.png)

## Quick Start

These instructions assume you have successfully cloned the repository and are working in the ~/github/Applied_AI_Base directory.

### 1. Install Python

Python is the program that runs this project.

Install Python 3.10 or newer. The repository has been used with Python 3.13, based on the local virtual environment.

Check your version:

```bash
python3 --version
```

What this does: prints the Python version installed on your computer.

Expected output:

```text
Python 3.x.x
```

If the command is not found, install Python and try again.

### 2. Create a Virtual Environment

A virtual environment is a private folder for this project's Python libraries. It keeps this project separate from other Python projects on your computer.

On macOS or Linux:

```bash
python -m venv venv
```

On Windows:

```powershell
python -m venv venv
```

What this does: creates a folder named `venv/`.

Expected output: usually no text appears. That is normal.

### 3. Turn On the Virtual Environment

On macOS or Linux:

```bash
source venv/bin/activate
```

On Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

What this does: tells your terminal to use this project's private Python setup.

Expected output: your terminal prompt may show `(venv)`.

### 4. Install the Project Libraries

```bash
pip install -r requirements.txt
```

What this does: downloads the Python libraries listed in `requirements.txt`.

Why it matters: the application cannot run until these libraries are installed.

Expected output: many lines ending with a success message.

Common error: if you see `pip: command not found`, try:

```bash
python -m pip install -r requirements.txt
```

### 5. Create Your `.env` File

An environment variable is a setting the app reads when it starts. A `.env` file is a simple text file that stores these settings.

Create a file named `.env` in the project root:

```text
OPENAI_API_KEY=your_openai_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX=energy-cyber-index
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
OPENAI_EMBED_MODEL=text-embedding-3-small
OPENAI_MODEL=gpt-4.1-mini
```

Do not share your `.env` file. It contains secret keys.

### 6. Build the Local Corpus

Researchers populate data/pdf/ with publicly available source documents before running the ingestion pipeline. This command extracts text from them and creates a searchable text file.

```bash
python -m scripts.02_prepare_energy_json
```

What this does: reads PDFs and writes `data/critical_infra_corpus.jsonl`.

Expected output: lines that begin with `Processing:` and end with `Done!`.

### 7. Upload the Corpus to Pinecone

Pinecone is the searchable memory for the app.

```bash
python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --reset
```

What this does: turns each text chunk into a searchable vector and stores it in Pinecone.

Why it matters: without this step, the app may fall back to a slower local search or return weaker answers.

Expected output: progress bars and `Indexing complete`.

Warning: `--reset` deletes the existing contents of the selected Pinecone index before uploading the current corpus.

### 8. Start the Browser App

```bash
streamlit run streamlit_app.py
```

What this does: starts the web interface on your computer.

Expected output: Streamlit prints a local address, usually:

```text
Local URL: http://localhost:8501
```

Open that address in your browser.

## Requirements

| Requirement | Needed? | Notes |
| --- | --- | --- |
| Python 3.10 or newer | Yes | Python runs the app and scripts. |
| OpenAI API key | Yes | Used for embeddings and final answers. |
| Pinecone account and API key | Yes for full retrieval | Used to store and search document vectors. |
| SerpAPI key | Optional | Used for live web discovery and refresh. |
| Internet access | Yes for setup and external services | Needed to install packages and call OpenAI, Pinecone, and optional SerpAPI. |
| Docker | No | This repo does not include Docker files. |
| Traditional database | No | The app uses JSONL files and Pinecone, not PostgreSQL, MySQL, or SQLite. |

## Environment Variables

| Name | Required? | Default | Description | Example |
| --- | --- | --- | --- | --- |
| `OPENAI_API_KEY` | Yes | None | Secret key for OpenAI. | `sk-...` |
| `PINECONE_API_KEY` | Yes for Pinecone search | None | Secret key for Pinecone. | `pcsk_...` |
| `PINECONE_INDEX` | Yes for Pinecone search | `reviews-index` in the indexing script only | Pinecone index name. Use one consistent value. | `energy-cyber-index` |
| `PINECONE_CLOUD` | Needed when creating an index | `aws` | Pinecone cloud provider. | `aws` |
| `PINECONE_REGION` | Needed when creating an index | `us-east-1` | Pinecone region. | `us-east-1` |
| `PINECONE_NAMESPACE` | No | Empty string | Optional Pinecone namespace. A namespace separates groups of vectors inside one index. | `nerc-cip` |
| `OPENAI_EMBED_MODEL` | No | `text-embedding-3-small` | OpenAI model used to create searchable vectors. | `text-embedding-3-small` |
| `OPENAI_MODEL` | No | `gpt-4.1-mini` | OpenAI model used to write answers. | `gpt-4.1-mini` |
| `SERPAPI_API_KEY` | Optional | None | Secret key for SerpAPI web search. | `abc123` |
| `SERPAPI_KEY` | Optional | None | Alternate name supported for SerpAPI. | `abc123` |
| `ENABLE_SERPAPI_SEARCH` | Optional | `true` | Set to `false` to stop automatic live search during questions. | `false` |
| `SERPAPI_MAX_RESULTS` | Optional | `3` | Number of live search results used during a question. | `3` |
| `SERPAPI_QUERY_TEMPLATE` | Optional | `{query} critical infrastructure cybersecurity energy sector` | Search phrase pattern for live web search. | `{query} NERC CIP advisory` |
| `PINECONE_ID_STRATEGY` | Optional | `url` | How live web chunk IDs are made. `content` uses text content instead. | `url` |
| `CHROMA_PERSIST_PATH` | No active use found | `./chroma_fcc_storage` | Present in `config.py`, but not used by the current RAG flow. | `./chroma_fcc_storage` |
| `CHROMA_COLLECTION_NAME` | No active use found | `fcc_documents` | Present in `config.py`, but not used by the current RAG flow. | `fcc_documents` |

## Running the Project

### Development

Use development mode when you are editing or testing the project locally.

```bash
streamlit run streamlit_app.py
```

Expected result: the browser app opens and lets you ask questions.

### Command-Line Query

Use this when you want a JSON answer in the terminal.

```bash
python -m scripts.04_query_bot --q "What are NERC CIP access control requirements?"
```

Add debug information:

```bash
python -m scripts.04_query_bot --q "How should incident response be handled in OT systems?" --debug
```

### Testing and Evaluation

This repository does not include a separate unit test suite. It does include an evaluation script that checks sample grounded responses.

```bash
python -m scripts.05_eval_grounding
```

What this does: runs several sample questions and writes results to `data/eval_results.jsonl`.

Expected output: `[PASS]` lines or a list of failed checks.

### Production

TODO: Information could not be determined automatically.

No production deployment files, process manager files, container files, or cloud deployment configuration were found in the repository.

## Repository Structure

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

| Path | Purpose |
| --- | --- |
| `app/` | Core application code for retrieval and answer generation. |
| `app/rag.py` | Main retrieval-augmented generation pipeline. |
| `app/control_families.py` | Control-family keyword detection. |
| `control_families.py` | Duplicate top-level control-family helper used by scripts. |
| `data/` | Local corpus and source PDFs. |
| `data/pdf/` | PDF documents used to build the corpus. |
| `data/critical_infra_corpus.jsonl` | Extracted text chunks used for retrieval. |
| `scripts/` | Command-line maintenance and workflow scripts. |
| `streamlit_app.py` | Browser-based user interface. |
| `config.py` | Environment loading helpers. |
| `requirements.txt` | Python libraries needed by the project. |
| `docs/` | Full end-user and maintainer documentation. |

## Common Tasks

### Rebuild the corpus from PDFs

```bash
python -m scripts.02_prepare_energy_json
```

Use this after adding or removing PDF files in `data/pdf/`.

### Re-upload the corpus to Pinecone

```bash
python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --reset
```

Use this after rebuilding the corpus.

### Add web sources to Pinecone

```bash
python -m scripts.06_ingest_web_sources --url https://example.gov/example-page
```

Use this when you have a specific source URL to ingest.

Preview without writing to Pinecone:

```bash
python -m scripts.06_ingest_web_sources --dry-run
```

### Ask a question in the terminal

```bash
python -m scripts.04_query_bot --q "What are common attack vectors against energy-sector ICS?"
```

### Restart the app

Stop Streamlit with `Control+C`, then run:

```bash
streamlit run streamlit_app.py
```

## Troubleshooting

### `Missing env var: OPENAI_API_KEY`

Cause: the app cannot find your OpenAI key.

Fix: create or update `.env` and include:

```text
OPENAI_API_KEY=your_openai_api_key_here
```

Verification: restart the app and ask a question.

### `Missing OPENAI_API_KEY or PINECONE_API_KEY`

Cause: the indexing script needs both keys.

Fix: add both values to `.env`.

Verification:

```bash
python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl
```

### `No module named app`

Cause: the script was run as a file path instead of a Python module.

Fix: run scripts with `python -m`.

Use:

```bash
python -m scripts.04_query_bot --q "test question"
```

Avoid:

```bash
python scripts/04_query_bot.py
```

### Empty or weak answers

Likely causes:

- The Pinecone index is empty.
- `PINECONE_INDEX` points to the wrong index.
- The corpus was not rebuilt after PDF changes.
- The question does not match the available documents.

Fix:

```bash
python -m scripts.02_prepare_energy_json
python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --reset
```

## FAQ

### What is RAG?

RAG means retrieval-augmented generation. In plain English, the app first searches documents, then asks an AI model to answer using those documents.

### Where is my data stored?

The local source documents are in `data/pdf/`. Extracted text is in `data/critical_infra_corpus.jsonl`. Search vectors are stored in Pinecone.

### Does this app have user accounts?

No. No login, roles, or user account system was found in this repository.

### Does this app have an API?

No HTTP API endpoints were found. The app is used through Streamlit or command-line scripts.

### Is there a database?

There is no traditional database. The project uses local files and Pinecone.

### Can I use it without Pinecone?

Partly. The code can fall back to local keyword retrieval if Pinecone access fails, but Pinecone is required for the intended vector search workflow.

## More Documentation

Start with [docs/README.md](docs/README.md).

Recommended reading order:

1. [Getting Started](docs/getting-started.md)
2. [Configuration](docs/configuration.md)
3. [First Run](docs/first-run.md)
4. [Daily Usage](docs/daily-usage.md)
5. [Troubleshooting](docs/troubleshooting.md)
6. [Developer Guide](docs/developer-guide.md)
