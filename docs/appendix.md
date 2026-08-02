# Appendix

## Script Reference

### Build Corpus

```bash
python -m scripts.02_prepare_energy_json
```

Creates or replaces `data/critical_infra_corpus.jsonl`.

### Index Corpus

```bash
python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl
```

Options:

| Option | Meaning |
| --- | --- |
| `--chunks` | Path to JSONL corpus. Required. |
| `--reset` | Delete existing vectors before uploading. |
| `--namespace` | Write vectors into a Pinecone namespace. |

### Query Bot

```bash
python -m scripts.04_query_bot --q "Your question"
```

Options:

| Option | Meaning |
| --- | --- |
| `--q` | Question. Required. |
| `--top_k` | Number of chunks to retrieve. |
| `--min_recurring_reviews` | Passed through to the response function. |
| `--debug` | Include debug information. |

### Evaluation

```bash
python -m scripts.05_eval_grounding
```

Options:

| Option | Meaning |
| --- | --- |
| `--top_k` | Evidence chunk count. Default is `25`. |
| `--min_recurring_reviews` | Passed through to the response function. Default is `2`. |
| `--out` | Output file. Default is `data/eval_results.jsonl`. |

### Web Ingestion

```bash
python -m scripts.06_ingest_web_sources
```

Options:

| Option | Meaning |
| --- | --- |
| `--url` | URL to ingest. Can be repeated. |
| `--urls-file` | File with one URL per line. |
| `--query` | SerpAPI query. Can be repeated. |
| `--no-default-search` | Do not run default searches. |
| `--allow-any-domain` | Allow non-preferred domains. |
| `--threshold` | Similarity threshold for duplicate skipping. |
| `--top-k` | Neighbor count for duplicate checks. |
| `--results-per-query` | SerpAPI results per query. |
| `--dry-run` | Preview without writing to Pinecone. |

## Default Search Domains

The web ingestion script prefers sources from domains including:

- `cisa.gov`
- `energy.gov`
- `nist.gov`
- `ferc.gov`
- `nerc.com`
- `inl.gov`
- `pnnl.gov`
- `ornl.gov`
- `anl.gov`
- `epri.com`
- `regulations.gov`
- `congress.gov`
- `gao.gov`

## Known Unknowns

TODO: Information could not be determined automatically:

- Production deployment process.
- Intended hosting platform.
- CI or build pipeline.
- Formal release process.
- Long-term authentication plan.
- Dependency update policy.
