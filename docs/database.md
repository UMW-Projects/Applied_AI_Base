# Data and Storage

This project does not use a traditional database.

No PostgreSQL, MySQL, SQLite application tables, migrations, or object-relational models were found.

## Storage Used By This Project

| Storage | What It Holds | Location |
| --- | --- | --- |
| PDF files | Source documents | `data/pdf/` |
| JSONL file | Extracted text chunks | `data/critical_infra_corpus.jsonl` |
| Pinecone | Search vectors and metadata | External Pinecone service |
| Streamlit session state | Current chat history during a browser session | In memory while app runs |

## What Is JSONL?

JSONL means "JSON Lines". It is a text file where each line is one small data record.

In this project, each line in `data/critical_infra_corpus.jsonl` represents one chunk of document text.

## Pinecone Metadata

The indexing script stores metadata with each vector. Important fields include:

| Field | Meaning |
| --- | --- |
| `chunk_id` | Stable chunk identifier, such as `energy-000001`. |
| `source_file` | PDF filename or source URL. |
| `document_title` | Human-readable document title. |
| `organization` | Source organization label. |
| `document_type` | Type label, such as `Standard` or `Web Source`. |
| `sector` | Usually `Energy`. |
| `page_number` | PDF page number when known. |
| `chunk_index` | Chunk number within a page or source. |
| `text` | The stored text excerpt, capped for Pinecone metadata size. |
| `controls` | Detected cybersecurity control families. |
| `source_url` | URL for web-ingested sources. |
| `retrieved_at` | Date a web source was retrieved. |
| `is_external` | Whether the source came from web ingestion. |

## Migrations

No database migration system was found.

If metadata shape changes, re-run indexing:

```bash
python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --reset
```

## Backup

Back up:

1. `data/pdf/`
2. `data/critical_infra_corpus.jsonl`
3. `.env` in a secure secrets manager, not in normal file backups
4. A record of Pinecone index name, cloud, region, and namespace

Pinecone vectors can be recreated from the local corpus if the source files and settings are preserved.
