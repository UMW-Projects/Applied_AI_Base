# Upgrading

Upgrading means changing dependencies, models, or services without breaking the app.

## Upgrade Python Packages

1. Activate the virtual environment.
2. Edit `requirements.txt`.
3. Install:

   ```bash
   pip install -r requirements.txt
   ```

4. Run evaluation:

   ```bash
   python -m scripts.05_eval_grounding
   ```

## Change the OpenAI Answer Model

1. Open `.env`.
2. Change:

   ```text
   OPENAI_MODEL=gpt-4.1-mini
   ```

3. Restart Streamlit.
4. Ask a known question.
5. Run evaluation.

## Change the Embedding Model

Changing the embedding model affects vector dimensions and search behavior.

1. Open `.env`.
2. Change:

   ```text
   OPENAI_EMBED_MODEL=text-embedding-3-small
   ```

3. Re-index Pinecone:

   ```bash
   python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --reset
   ```

4. Run evaluation.

Warning: do not mix embeddings from different models in the same Pinecone index or namespace.

## Upgrade Source Documents

1. Add or replace PDFs in `data/pdf/`.
2. Rebuild:

   ```bash
   python -m scripts.02_prepare_energy_json
   ```

3. Re-index:

   ```bash
   python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --reset
   ```

4. Run evaluation.

## Rollback

If an upgrade causes problems:

1. Restore the previous `requirements.txt` or `.env`.
2. Reinstall dependencies if needed.
3. Re-index Pinecone if embeddings changed.
4. Restart the app.
5. Run evaluation.
