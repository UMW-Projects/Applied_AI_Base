# Getting Started

This guide explains the project in plain English before you install anything.

## What You Are Installing

You are installing a local browser app. Local means it runs on your computer. Browser app means you open it through a web browser, even though it is not necessarily on the public internet.

The app helps answer questions like:

- What are common energy-sector cyber risks?
- What does the document collection say about access control?
- What mitigations are recommended for remote access risk?
- What policy language could address patch management?

## Main Parts

| Part | Plain-English Meaning |
| --- | --- |
| Python | The program that runs the app. |
| Streamlit | The tool that creates the browser screen. |
| OpenAI | The service that creates embeddings and writes answers. |
| Pinecone | The service that stores searchable document meaning. |
| PDF corpus | The source document library in `data/pdf/`. |
| JSONL corpus | Extracted document text in `data/critical_infra_corpus.jsonl`. |

## Accounts You Need

You need:

1. An OpenAI API key.
2. A Pinecone API key.
3. A Pinecone index.

Optional:

1. A SerpAPI key for web-source refresh.

## Skills You Need

You do not need to know how to program.

You do need to:

1. Open a terminal.
2. Copy and paste commands.
3. Create a text file named `.env`.
4. Keep secret keys private.

## Recommended First Question

After setup, ask:

```text
What are common attack vectors against energy-sector ICS and OT systems?
```

Expected result: the app should return a cybersecurity summary, likely attack-vector sections, and a source list.

## Screenshots

![First successful app launch](../image/chat.png)

![Successful answer with sources](../image/answer.png)
