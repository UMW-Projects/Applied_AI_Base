# First Run

This guide walks through the first full setup after installation and configuration.

## Step 1: Activate the Virtual Environment

```bash
source venv/bin/activate
```

On Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

Expected result: your prompt may show `(venv)`.

## Step 2: Build the Corpus

The corpus is the searchable text collection.

```bash
python -m scripts.02_prepare_energy_json
```

What this does:

1. Opens every PDF in `data/pdf/`.
2. Extracts text from each page.
3. Splits text into chunks.
4. Writes `data/critical_infra_corpus.jsonl`.

Expected output:

```text
Processing: some-file.pdf
...
Done! JSONL corpus saved to:
.../data/critical_infra_corpus.jsonl
```

Common error:

```text
No such file or directory
```

Fix: make sure you are running the command from the project root.

## Step 3: Index the Corpus in Pinecone

```bash
python -m scripts.03_index_pinecone --chunks data/critical_infra_corpus.jsonl --reset
```

What this does:

1. Reads the JSONL corpus.
2. Creates OpenAI embeddings.
3. Creates the Pinecone index if needed.
4. Uploads vectors to Pinecone.

Expected output:

```text
Loaded chunks: ...
Indexing: ...
Indexing complete.
```

Warning: `--reset` clears the selected Pinecone index before uploading.

## Step 4: Ask a Test Question in the Terminal

```bash
python -m scripts.04_query_bot --q "What are common attack vectors against energy-sector ICS?"
```

What this does: runs the same retrieval and answer pipeline without opening the browser UI.

Expected output: formatted JSON with fields such as `answer_summary`, `key_points`, `sources`, or `attack_vectors`.

## Step 5: Start the Browser App

```bash
streamlit run streamlit_app.py
```

Expected output:

```text
Local URL: http://localhost:8501
```

Open the local URL in your browser.

## Step 6: Use a Quick Prompt

The app includes quick prompts near the top of the page.

Try one of them first. Expected result:

1. The app retrieves evidence.
2. The app writes an answer.
3. The app lists sources.

![First successful response](../image/answer.png)
