# Configuration

Configuration means telling the app which services and settings to use.

This project reads configuration from environment variables. An environment variable is a named setting. A `.env` file is a convenient place to store those settings for local use.

## Create `.env`

In the project root, create a file named `.env`.

Add this template:

```text
OPENAI_API_KEY=your_openai_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX=energy-cyber-index
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
OPENAI_EMBED_MODEL=text-embedding-3-small
OPENAI_MODEL=gpt-4.1-mini
ENABLE_SERPAPI_SEARCH=false
```

Replace the placeholder values with your real keys.

Warning: never commit or share `.env`. It contains secrets.

## Required Settings

| Name | Required? | Default | Used By | Description | Example |
| --- | --- | --- | --- | --- | --- |
| `OPENAI_API_KEY` | Yes | None | App and scripts | Lets the project call OpenAI. | `sk-...` |
| `PINECONE_API_KEY` | Yes for Pinecone | None | App and indexing scripts | Lets the project call Pinecone. | `pcsk_...` |
| `PINECONE_INDEX` | Yes for Pinecone | Required in app, `reviews-index` in indexing script | App and scripts | Name of the Pinecone index. | `energy-cyber-index` |

## Pinecone Settings

| Name | Required? | Default | Description | Example |
| --- | --- | --- | --- | --- |
| `PINECONE_CLOUD` | Needed when creating an index | `aws` | Cloud provider for a new Pinecone index. | `aws` |
| `PINECONE_REGION` | Needed when creating an index | `us-east-1` | Region for a new Pinecone index. | `us-east-1` |
| `PINECONE_NAMESPACE` | No | Empty | Separates vector groups inside one Pinecone index. | `nerc-cip` |
| `PINECONE_ID_STRATEGY` | No | `url` | Controls generated IDs for live web chunks. | `content` |

## OpenAI Settings

| Name | Required? | Default | Description |
| --- | --- | --- | --- |
| `OPENAI_EMBED_MODEL` | No | `text-embedding-3-small` | Model used to create vectors for search. |
| `OPENAI_MODEL` | No | `gpt-4.1-mini` | Model used to write the final answer. |

## Optional Web Search Settings

| Name | Required? | Default | Description |
| --- | --- | --- | --- |
| `SERPAPI_API_KEY` | Optional | None | SerpAPI key for Google search results. |
| `SERPAPI_KEY` | Optional | None | Alternate SerpAPI key name. |
| `ENABLE_SERPAPI_SEARCH` | Optional | `true` | Turns automatic web search on or off during questions. |
| `SERPAPI_MAX_RESULTS` | Optional | `3` | Number of web search results to use. |
| `SERPAPI_QUERY_TEMPLATE` | Optional | `{query} critical infrastructure cybersecurity energy sector` | Search query pattern. |

Tip: for predictable local demos, set `ENABLE_SERPAPI_SEARCH=false`.

## Settings Present But Not Used By Current Flow

`config.py` contains Chroma settings:

| Name | Default | Note |
| --- | --- | --- |
| `CHROMA_PERSIST_PATH` | `./chroma_fcc_storage` | No active Chroma retrieval code was found. |
| `CHROMA_COLLECTION_NAME` | `fcc_documents` | No active Chroma retrieval code was found. |

TODO: Information could not be determined automatically: whether these Chroma settings are kept for a planned feature or leftover from earlier code.

## Verify Configuration

Run:

```bash
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(bool(os.getenv('OPENAI_API_KEY')), bool(os.getenv('PINECONE_API_KEY')), os.getenv('PINECONE_INDEX'))"
```

What this does: checks whether Python can read your `.env` file.

Expected output:

```text
True True energy-cyber-index
```

If you see `False`, check spelling and make sure `.env` is in the project root.
