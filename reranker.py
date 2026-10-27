import json
import os
import re
from typing import Any, Dict, List

from openai import OpenAI


def rerank_contexts(
    query: str,
    contexts: List[Dict[str, Any]],
    top_k: int = 8,
) -> List[Dict[str, Any]]:
    """
    Rerank retrieved evidence using an LLM relevance assessment.

    Falls back to original vector ranking if reranking fails.
    """

    if not contexts:
        return []

    original = sorted(
        contexts,
        key=lambda c: float(c.get("score") or 0),
        reverse=True,
    )

    if len(original) <= 1:
        return original[:top_k]

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    candidates = []

    for i, context in enumerate(original):
        candidates.append({
            "candidate_id": i,
            "title": context.get("document_title", ""),
            "text": (context.get("text") or "")[:1200],
        })

    prompt = f"""
You are evaluating cybersecurity research evidence.

USER QUESTION:
{query}

CANDIDATE DOCUMENT CHUNKS:
{json.dumps(candidates)}

Score every candidate from 0 to 10 based on how directly
its content supports answering the user's question.

Scoring:
0 = Irrelevant
3 = Weakly related
5 = Relevant background
7 = Directly relevant
10 = Strong, specific evidence answering the question

Do not score based on document title alone.
Do not invent information.
Return one score for every candidate.

Return valid JSON only:

{{
  "scores": [
    {{"candidate_id": 0, "relevance": 8}}
  ]
}}
"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise evidence relevance evaluator. Return JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )

        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)

        scores = {}

        for item in result.get("scores", []):
            idx = int(item["candidate_id"])
            score = float(item["relevance"])

            if 0 <= idx < len(original) and 0 <= score <= 10:
                scores[idx] = score

        if len(scores) != len(original):
            return original[:top_k]

        ranked = []

        for i, context in enumerate(original):
            updated = dict(context)
            updated["rerank_score"] = scores[i]
            ranked.append(updated)

        ranked.sort(
            key=lambda c: (
                c["rerank_score"],
                float(c.get("score") or 0),
            ),
            reverse=True,
        )

        return ranked[:top_k]

    except Exception as exc:
        print(f"Reranking failed; using vector ranking: {exc}")
        return original[:top_k]


def select_diverse_contexts(
    ranked,
    top_k=8,
    max_per_document=3,
    min_relevance=5.0,
):
    """
    Select relevant evidence while limiting source duplication.

    Assumes contexts are already sorted by rerank_score.
    """

    selected = []
    remaining = []
    document_counts = {}

    for context in ranked:
        title = (
            context.get("source_file")
            or context.get("document_title")
            or context.get("chunk_id")
            or "Unknown"
        )

        score = float(context.get("rerank_score") or 0)

        if score < min_relevance:
            continue

        count = document_counts.get(title, 0)

        if count < max_per_document:
            selected.append(context)
            document_counts[title] = count + 1
        else:
            remaining.append(context)

        if len(selected) >= top_k:
            selected.sort(
                key=lambda c: float(c.get("rerank_score") or 0),
                reverse=True,
            )
            return selected

    # Fill remaining slots with relevant evidence.
    for context in remaining:
        if len(selected) >= top_k:
            break

        selected.append(context)

    selected.sort(
        key=lambda c: float(c.get("rerank_score") or 0),
        reverse=True,
    )

    return selected[:top_k]
