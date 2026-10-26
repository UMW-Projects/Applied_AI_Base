# scripts/05_eval_grounding.py
import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from app.rag import RERANK_METHODS, _extract_json_object, generate_grounded_response

SAMPLE_QUERIES = [
    "What are NERC CIP access control requirements?",
    "How should incident response be handled in OT environments?",
    "Recommend an action plan for improving monitoring and logging.",
    "Draft policy language for patch management in energy delivery systems.",
]

JUDGE_BATCH_SIZE = 12
JUDGE_CHUNK_CHARS = 900
USEFULNESS_CHUNK_CHARS = 600
GROUNDING_ANSWER_CHARS = 6000


def _chunk_ids_from_items(items: Any) -> List[str]:
    chunk_ids: List[str] = []
    if not isinstance(items, list):
        return chunk_ids

    for item in items:
        if isinstance(item, dict):
            if item.get("chunk_id"):
                chunk_ids.append(str(item["chunk_id"]))
            for key in ("source_chunk_ids", "evidence_chunk_ids", "grounding_chunk_ids", "evidence",):
                values = item.get(key) or []
                if isinstance(values, list):
                    chunk_ids.extend(str(v) for v in values if v)
        elif isinstance(item, str) and item.startswith("energy-"):
            chunk_ids.append(item)

    return chunk_ids


def assert_schema_and_shape(out: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(out, dict):
        return ["Output is not a dict"]

    if "error" in out:
        return [f"Response returned error: {out.get('error')}"]

    if not out.get("answer_summary"):
        errors.append("Missing or empty answer_summary")

    has_general_answer = isinstance(out.get("key_points"), list) and isinstance(out.get("sources"), list)
    has_workflow_answer = (
        isinstance(out.get("key_requirements"), list)
        and isinstance(out.get("policy_recommendations"), list)
        and isinstance(out.get("draft_policy_language"), list)
    )

    if not has_general_answer and not has_workflow_answer:
        errors.append(
            "Output must include either key_points/sources or "
            "key_requirements/policy_recommendations/draft_policy_language"
        )

    return errors


def assert_grounding_ids(out: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    referenced = set()

    referenced.update(_chunk_ids_from_items(out.get("sources")))
    referenced.update(_chunk_ids_from_items(out.get("key_points")))
    referenced.update(_chunk_ids_from_items(out.get("key_requirements")))
    referenced.update(_chunk_ids_from_items(out.get("policy_recommendations")))
    referenced.update(_chunk_ids_from_items(out.get("draft_policy_language")))

    bad = sorted(cid for cid in referenced if not cid.startswith("energy-"))
    if bad:
        errors.append("Referenced chunk_ids do not use expected energy-* format:\n" + "\n".join(bad))

    if not referenced:
        errors.append("No grounding chunk_ids referenced")

    return errors


# =========================================================
# METRICS
# =========================================================
def cited_chunk_ids(out: Dict[str, Any]) -> List[str]:
    """Every chunk_id the answer cites, including nested attack-vector/risk evidence."""
    cited: List[str] = []
    for key in ("sources", "key_points", "key_requirements", "policy_recommendations", "attack_vectors"):
        cited.extend(_chunk_ids_from_items(out.get(key)))
    for item in out.get("attack_vectors", []) or []:
        if isinstance(item, dict):
            cited.extend(_chunk_ids_from_items(item.get("sources")))
    for category in out.get("risk_categories", []) or []:
        if isinstance(category, dict):
            risks = category.get("risks", []) or []
            cited.extend(_chunk_ids_from_items(risks))
            for risk in risks:
                if isinstance(risk, dict):
                    cited.extend(_chunk_ids_from_items(risk.get("sources")))
    cited.extend(str(c) for c in out.get("used_chunk_ids", []) or [] if c)
    return sorted(set(cited))


def _judge_json(client: OpenAI, model: str, system: str, user: str) -> Dict[str, Any]:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(_extract_json_object(resp.choices[0].message.content or ""))


def judge_relevance(
    client: OpenAI,
    model: str,
    query: str,
    contexts: List[Dict[str, Any]],
    cache: Dict[Tuple[str, str], bool],
) -> Dict[str, bool]:
    """Label each retrieved chunk relevant / not relevant to the query.

    Labels are cached per (query, chunk_id) so a chunk retrieved by both
    the baseline and the reranker is judged once and scored identically.
    """
    pending = [c for c in contexts if c.get("chunk_id") and (query, c["chunk_id"]) not in cache]
    system = (
        "You are evaluating retrieval for an energy-sector cybersecurity RAG system. "
        "For each passage, decide whether it contains information that directly helps answer the question. "
        "Passages that are only loosely on-topic, generic, acronym lists, tables of contents, or references are NOT relevant. "
        'Return JSON only: {"labels": [{"chunk_id": "...", "relevant": true|false}]} covering every passage.'
    )
    for i in range(0, len(pending), JUDGE_BATCH_SIZE):
        batch = pending[i:i + JUDGE_BATCH_SIZE]
        passages = "\n\n".join(
            f"[chunk_id] {c['chunk_id']}\n[title] {c.get('document_title')}\n{(c.get('text') or '')[:JUDGE_CHUNK_CHARS]}"
            for c in batch
        )
        data = _judge_json(client, model, system, f"QUESTION:\n{query}\n\nPASSAGES:\n{passages}")
        labels = {str(l.get("chunk_id")): bool(l.get("relevant")) for l in data.get("labels", []) if isinstance(l, dict)}
        for c in batch:
            cache[(query, c["chunk_id"])] = labels.get(c["chunk_id"], False)

    return {c["chunk_id"]: cache[(query, c["chunk_id"])] for c in contexts if c.get("chunk_id")}


def judge_usefulness(client: OpenAI, model: str, query: str, contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
    system = (
        "You are evaluating the context given to an LLM for an energy-sector cybersecurity question. "
        "Judge whether the passages, taken together, provide sufficient directly relevant evidence to answer the question well. "
        "Score 1-5: 5 = complete, specific evidence; 3 = partial or generic evidence; 1 = little or no useful evidence. "
        'Return JSON only: {"score": 1-5, "sufficient": true|false, "missing": "<one sentence on what is missing, or empty>"}'
    )
    passages = "\n\n".join(
        f"[{c.get('chunk_id')}] {(c.get('text') or '')[:USEFULNESS_CHUNK_CHARS]}" for c in contexts
    )
    data = _judge_json(client, model, system, f"QUESTION:\n{query}\n\nCONTEXT:\n{passages}")
    return {
        "score": float(data.get("score") or 0),
        "sufficient": bool(data.get("sufficient")),
        "missing": data.get("missing") or "",
    }


def judge_grounding(
    client: OpenAI,
    model: str,
    query: str,
    out: Dict[str, Any],
    cited_contexts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    system = (
        "You are checking whether a RAG answer is grounded in the evidence it cites. "
        "Score 1-5: 5 = every claim is supported by the cited passages; 3 = some claims unsupported; "
        "1 = mostly unsupported or contradicts the passages. "
        'Return JSON only: {"score": 1-5, "unsupported_claims": ["<short claim>", ...]}'
    )
    answer = {k: v for k, v in out.items() if k not in ("debug", "retrieval_sources")}
    answer_text = json.dumps(answer, ensure_ascii=False)[:GROUNDING_ANSWER_CHARS]
    passages = "\n\n".join(
        f"[{c.get('chunk_id')}] {(c.get('text') or '')[:JUDGE_CHUNK_CHARS]}" for c in cited_contexts
    ) or "(no cited passages)"
    data = _judge_json(
        client, model, system,
        f"QUESTION:\n{query}\n\nANSWER:\n{answer_text}\n\nCITED PASSAGES:\n{passages}",
    )
    return {
        "score": float(data.get("score") or 0),
        "unsupported_claims": data.get("unsupported_claims") or [],
    }


def compute_metrics(
    query: str,
    out: Dict[str, Any],
    wall_ms: float,
    judge: Optional[OpenAI],
    judge_model: str,
    relevance_cache: Dict[Tuple[str, str], bool],
) -> Dict[str, Any]:
    debug = out.get("debug", {}) or {}
    contexts = debug.get("retrieved_contexts", []) or []
    latency = debug.get("latency_ms", {}) or {}
    retrieved_ids = {c.get("chunk_id") for c in contexts if c.get("chunk_id")}
    cited = cited_chunk_ids(out)
    cited_valid = [cid for cid in cited if cid in retrieved_ids]

    metrics: Dict[str, Any] = {
        "num_retrieved": len(contexts),
        "num_cited": len(cited),
        "citation_valid_rate": round(len(cited_valid) / len(cited), 3) if cited else None,
        "latency_ms": {
            "retrieval": latency.get("retrieval"),
            "rerank": latency.get("rerank"),
            "generation": latency.get("generation"),
            "total": round(wall_ms, 1),
        },
    }

    if judge is None or not contexts:
        return metrics

    labels = judge_relevance(judge, judge_model, query, contexts, relevance_cache)
    relevant_ids = [cid for cid, ok in labels.items() if ok]
    ordered = [c.get("chunk_id") for c in contexts if c.get("chunk_id")]
    top5 = ordered[:5]
    cited_judged = [cid for cid in cited_valid if cid in labels]

    metrics["retrieval_relevance"] = {
        "relevant": len(relevant_ids),
        "precision_at_k": round(len(relevant_ids) / len(ordered), 3) if ordered else 0.0,
        "precision_at_5": round(sum(labels.get(cid, False) for cid in top5) / len(top5), 3) if top5 else 0.0,
        "labels": labels,
    }
    metrics["context_usefulness"] = judge_usefulness(judge, judge_model, query, contexts)

    by_id = {c.get("chunk_id"): c for c in contexts}
    grounding = judge_grounding(judge, judge_model, query, out, [by_id[cid] for cid in cited_valid])
    grounding["citation_relevance"] = (
        round(sum(labels[cid] for cid in cited_judged) / len(cited_judged), 3) if cited_judged else 0.0
    )
    metrics["grounding"] = grounding
    return metrics


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    def avg(values: List[Optional[float]]) -> Optional[float]:
        vals = [v for v in values if isinstance(v, (int, float))]
        return round(mean(vals), 3) if vals else None

    metrics = [r["metrics"] for r in results]
    return {
        "queries": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "precision_at_k": avg([m.get("retrieval_relevance", {}).get("precision_at_k") for m in metrics]),
        "precision_at_5": avg([m.get("retrieval_relevance", {}).get("precision_at_5") for m in metrics]),
        "relevant_chunks": avg([m.get("retrieval_relevance", {}).get("relevant") for m in metrics]),
        "usefulness_score": avg([m.get("context_usefulness", {}).get("score") for m in metrics]),
        "sufficient_rate": avg([float(m["context_usefulness"]["sufficient"]) for m in metrics if "context_usefulness" in m]),
        "grounding_score": avg([m.get("grounding", {}).get("score") for m in metrics]),
        "citation_relevance": avg([m.get("grounding", {}).get("citation_relevance") for m in metrics]),
        "citation_valid_rate": avg([m.get("citation_valid_rate") for m in metrics]),
        "retrieval_ms": avg([m["latency_ms"].get("retrieval") for m in metrics]),
        "rerank_ms": avg([m["latency_ms"].get("rerank") for m in metrics]),
        "generation_ms": avg([m["latency_ms"].get("generation") for m in metrics]),
        "total_ms": avg([m["latency_ms"].get("total") for m in metrics]),
    }


def print_comparison(summaries: Dict[str, Dict[str, Any]]) -> None:
    methods = list(summaries)
    rows = [
        ("passed / queries", lambda s: f"{s['passed']}/{s['queries']}"),
        ("retrieval precision@k", lambda s: s["precision_at_k"]),
        ("retrieval precision@5", lambda s: s["precision_at_5"]),
        ("relevant chunks (avg)", lambda s: s["relevant_chunks"]),
        ("context usefulness (1-5)", lambda s: s["usefulness_score"]),
        ("context sufficient rate", lambda s: s["sufficient_rate"]),
        ("grounding score (1-5)", lambda s: s["grounding_score"]),
        ("citation relevance", lambda s: s["citation_relevance"]),
        ("citation valid rate", lambda s: s["citation_valid_rate"]),
        ("retrieval ms", lambda s: s["retrieval_ms"]),
        ("rerank ms", lambda s: s["rerank_ms"]),
        ("generation ms", lambda s: s["generation_ms"]),
        ("total ms", lambda s: s["total_ms"]),
    ]
    width = max(14, *(len(m) + 2 for m in methods))
    print("\n" + "=" * 80)
    print(f"{'metric':<28}" + "".join(f"{m:>{width}}" for m in methods))
    print("-" * (28 + width * len(methods)))
    for label, fn in rows:
        cells = "".join(f"{str(fn(summaries[m]) if fn(summaries[m]) is not None else '-'):>{width}}" for m in methods)
        print(f"{label:<28}{cells}")
    print("=" * 80)


# =========================================================
# RUN
# =========================================================
def run_one(q: str, top_k: int, min_recurring_reviews: int, rerank: str) -> Tuple[Dict[str, Any], List[str], float]:
    start = time.perf_counter()
    out = generate_grounded_response(
        query=q,
        top_k=top_k,
        min_recurring_reviews=min_recurring_reviews,
        include_debug=True,
        rerank=rerank,
    )
    wall_ms = (time.perf_counter() - start) * 1000

    errs: List[str] = []
    errs += assert_schema_and_shape(out)
    if "error" not in out:
        errs += assert_grounding_ids(out)
    return out, errs, wall_ms


def main(
    top_k: int,
    min_recurring_reviews: int,
    out_path: str,
    methods: List[str],
    use_judge: bool,
    judge_model: str,
) -> None:
    all_fails = 0
    stamp = datetime.now().isoformat(timespec="seconds")
    output_file = Path(out_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    judge = None
    if use_judge:
        try:
            judge = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        except KeyError:
            print("OPENAI_API_KEY not set; skipping LLM-judged metrics (relevance, usefulness, grounding).")

    relevance_cache: Dict[Tuple[str, str], bool] = {}
    results = []
    by_method: Dict[str, List[Dict[str, Any]]] = {m: [] for m in methods}

    for method in methods:
        print(f"\n--- rerank={method} ---")
        for q in SAMPLE_QUERIES:
            out, errs, wall_ms = run_one(q, top_k, min_recurring_reviews, method)
            metrics = compute_metrics(q, out, wall_ms, judge, judge_model, relevance_cache)

            rerank_error = (out.get("debug", {}) or {}).get("retrieval", {}).get("error")
            if rerank_error:
                print(f"[WARN] reranker fell back to lexical: {rerank_error}")

            record = {
                "timestamp": stamp,
                "rerank": method,
                "top_k": top_k,
                "query": q,
                "passed": not bool(errs),
                "errors": errs,
                "metrics": metrics,
                "output": out,
            }
            results.append(record)
            by_method[method].append(record)

            if errs:
                all_fails += 1
                print("\n" + "=" * 80)
                print("QUERY:", q)
                print("FAILED CHECKS:")
                for e in errs:
                    print("-", e)
            else:
                rel = metrics.get("retrieval_relevance", {})
                print(
                    f"[PASS] {q}  "
                    f"(p@k={rel.get('precision_at_k', '-')}, total={metrics['latency_ms']['total']}ms)"
                )

    with output_file.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summaries = {m: summarize(rs) for m, rs in by_method.items()}
    summary_file = output_file.with_name(output_file.stem + "_summary.json")
    summary_file.write_text(
        json.dumps({"timestamp": stamp, "top_k": top_k, "judge_model": judge_model if judge else None, "methods": summaries}, indent=2),
        encoding="utf-8",
    )

    print_comparison(summaries)
    print(f"\nWrote eval results -> {output_file}")
    print(f"Wrote eval summary -> {summary_file}")

    if all_fails:
        raise SystemExit(f"\nEvaluation finished with {all_fails} failing queries.")
    print("\nAll checks passed.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--top_k", type=int, default=25)
    ap.add_argument("--min_recurring_reviews", type=int, default=2)
    ap.add_argument("--out", default="data/eval_results.jsonl")
    ap.add_argument(
        "--rerank",
        default="none,pinecone",
        help=f"Comma-separated reranking methods to compare. Choices: {', '.join(RERANK_METHODS)}. "
             "'none' is the baseline (current retrieval).",
    )
    ap.add_argument("--no_judge", action="store_true", help="Skip LLM-judged metrics (only schema checks and latency).")
    ap.add_argument("--judge_model", default=os.getenv("EVAL_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")))
    args = ap.parse_args()

    methods = [m.strip().lower() for m in args.rerank.split(",") if m.strip()]
    unknown = [m for m in methods if m not in RERANK_METHODS]
    if unknown:
        ap.error(f"Unknown rerank method(s): {', '.join(unknown)}. Choices: {', '.join(RERANK_METHODS)}")

    main(args.top_k, args.min_recurring_reviews, args.out, methods, not args.no_judge, args.judge_model)
