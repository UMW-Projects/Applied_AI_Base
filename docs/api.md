# API

No public HTTP API endpoints were found in this repository.

The project exposes two practical interfaces:

1. A Streamlit browser app.
2. Command-line scripts.

## Browser Interface

Run:

```bash
streamlit run streamlit_app.py
```

Purpose: starts the user interface.

Authentication: none inside the app.

## Command-Line Query Interface

Run:

```bash
python -m scripts.04_query_bot --q "What are NERC CIP access control requirements?"
```

Parameters:

| Parameter | Required? | Default | Meaning |
| --- | --- | --- | --- |
| `--q` | Yes | None | Question to ask. |
| `--top_k` | No | `8` | Number of evidence chunks to retrieve. |
| `--min_recurring_reviews` | No | `2` | Passed into the response function. Current code does not show strong active use of this value. |
| `--debug` | No | Off | Includes debug details in output. |

Expected response: JSON printed to the terminal.

## Internal Python Function

Main function:

```python
from app.rag import generate_grounded_response

out = generate_grounded_response(
    query="What are common OT attack vectors?",
    top_k=8,
    include_debug=False,
)
```

This is an internal code interface, not a web API.

## Error Responses

The code may return a dictionary containing `error` if generation or parsing fails in certain paths. It may also return lower-confidence fallback answers when external services fail.

TODO: Information could not be determined automatically: a formal API contract beyond the observed JSON fields.
