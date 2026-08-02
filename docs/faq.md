# FAQ

## What is this app?

It is a cybersecurity research assistant for energy-sector critical infrastructure documents.

## What is RAG?

RAG means retrieval-augmented generation. The app searches documents first, then uses an AI model to write an answer from those documents.

## Do I need to know Python?

No. You only need to copy and paste commands. Maintainers need Python knowledge for code changes.

## What is an API key?

An API key is a secret password for a software service. This app uses API keys for OpenAI, Pinecone, and optionally SerpAPI.

## Where do I put API keys?

Put them in a `.env` file in the project root.

## Should I share my `.env` file?

No. Treat it like a password.

## Where is the data stored?

PDFs are stored in `data/pdf/`. Extracted chunks are stored in `data/critical_infra_corpus.jsonl`. Search vectors are stored in Pinecone.

## Does the app save chat history forever?

No. Chat history is stored in Streamlit session state while the app session is active.

## Can I add more PDFs?

Yes. Add PDFs to `data/pdf/`, rebuild the corpus, and re-index Pinecone.

## Why do answers mention sources?

Sources help you check where the answer came from. This is important for compliance and policy work.

## Does this replace legal or compliance advice?

No. It is a research and drafting aid. A qualified reviewer should verify final compliance decisions.

## Can I run without internet?

Only partly. You need internet access for OpenAI and Pinecone calls. If those fail, local fallback retrieval may still produce limited answers from local chunks.

## Is there a public API?

No public HTTP API was found.

## Is there a login system?

No user login system was found.
