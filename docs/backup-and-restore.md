# Backup and Restore

This page explains how to preserve and recover the app's data.

## What to Back Up

Back up:

1. `data/pdf/`
2. `data/critical_infra_corpus.jsonl`
3. Any URL lists used for web ingestion
4. Documentation of Pinecone settings:
   - index name
   - cloud
   - region
   - namespace
5. Secret values in a secure secrets manager

Do not store `.env` in an ordinary shared folder.

## What Does Not Need Normal Backup

`venv/` does not need backup. It can be recreated with:

```bash
python -m venv venv
pip install -r requirements.txt
```

`__pycache__/` does not need backup.

## Restore Local Files

1. Restore the repository.
2. Restore `data/pdf/`.
3. Restore or recreate `data/critical_infra_corpus.jsonl`.
4. Restore `.env` from secure storage.

If the JSONL file is missing, rebuild it:

```bash
python -m scripts.02_prepare_energy_json
```

## Restore Pinecone

If the Pinecone index is empty or lost, recreate it from local data:

```bash
python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --reset
```

Expected result: vectors are uploaded again.

## Verify Restore

Run:

```bash
python -m scripts.04_query_bot --q "What are common attack vectors against energy-sector ICS?"
```

Expected result: JSON answer with sources.

Then run:

```bash
python -m scripts.05_eval_grounding
```
