# Features

## Browser Chat

What it does: provides a Streamlit chat interface for asking cybersecurity questions.

When to use it: use this for normal analysis work.

Steps:

1. Start the app:

   ```bash
   streamlit run streamlit_app.py
   ```

2. Open the local browser URL.
3. Type a question.
4. Read the answer and sources.

Expected result: an evidence-grounded answer appears in the chat.

![Browser chat](../image/chat.png)

## Grounded Answers

What it does: searches source chunks before asking OpenAI to answer.

When to use it: always. This is the core purpose of the app.

Expected result: answers include source information such as document title, page number, source URL when available, and chunk ID.

Limitations:

- If the source collection does not contain enough evidence, the answer may be incomplete.
- If the OpenAI call fails, the code can fall back to a local synthesized response from retrieved context.

## Control-Family Detection

What it does: tags chunks with broad cybersecurity areas.

Detected control families include:

- Access control.
- Incident response.
- Risk management.
- Network security.
- Asset management.
- Monitoring and logging.
- Patch management.
- Business continuity.

When to use it: this happens automatically during indexing and retrieval.

## Policy Recommendations

What it does: creates recommended actions when the user's question asks for recommendations, action plans, fixes, next steps, policy language, or requirements.

Example:

```text
Recommend an action plan for improving monitoring and logging.
```

Expected result: the response includes requirements, recommendations, draft policy language, and sources.

## Attack-Vector Analysis

What it does: identifies likely methods attackers use against energy-sector ICS and OT environments.

Example:

```text
What are common attack vectors against energy-sector ICS?
```

Expected result: the response may include attack vectors, typical targets, mitigation focus, and evidence sources.

## Risk Categorization

What it does: groups risks into categories such as OT, IT, and cyber-physical systems when the question asks for categorization.

Example:

```text
Categorize energy-sector cybersecurity risks by OT, IT, and cyber-physical systems.
```

Expected result: grouped risks with why they matter and mitigation focus.

## Web Source Ingestion

What it does: discovers or ingests web pages and PDFs, chunks them, checks for duplicates, and stores new chunks in Pinecone.

When to use it: use this when the knowledge base needs newer or external sources.

Direct URL:

```bash
python -m scripts.06_ingest_web_sources --url https://example.gov/source
```

Dry run:

```bash
python -m scripts.06_ingest_web_sources --dry-run
```

Limitations:

- Default discovery needs SerpAPI.
- The script prefers government, research, and energy-sector domains unless `--allow-any-domain` is used.
- Some websites block scraping or provide too little readable text.
