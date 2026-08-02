# scripts/05_eval_grounding.py
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.rag import generate_grounded_response

SAMPLE_QUERIES = [
    "What are NERC CIP access control requirements?",
    "How should incident response be handled in OT environments?",
    "Recommend an action plan for improving monitoring and logging.",
    "Draft policy language for patch management in energy delivery systems.",
]


def _chunk_ids_from_items(items: Any) -> List[str]:
    chunk_ids: List[str] = []
    if not isinstance(items, list):
        return chunk_ids

    for item in items:
        if isinstance(item, dict):
            for key in ("source_chunk_ids", "evidence_chunk_ids", "grounding_chunk_ids"):
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


def run_one(q: str, top_k: int, min_recurring_reviews: int) -> Tuple[Dict[str, Any], List[str]]:
    out = generate_grounded_response(
        query=q,
        top_k=top_k,
        min_recurring_reviews=min_recurring_reviews,
        include_debug=True,
    )

    errs: List[str] = []
    errs += assert_schema_and_shape(out)
    if "error" not in out:
        errs += assert_grounding_ids(out)
    return out, errs


def main(top_k: int, min_recurring_reviews: int, out_path: str) -> None:
    all_fails = 0
    stamp = datetime.now().isoformat(timespec="seconds")
    output_file = Path(out_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for q in SAMPLE_QUERIES:
        out, errs = run_one(q, top_k, min_recurring_reviews)

        results.append({
            "timestamp": stamp,
            "query": q,
            "passed": not bool(errs),
            "errors": errs,
            "output": out,
        })

        if errs:
            all_fails += 1
            print("\n" + "=" * 80)
            print("QUERY:", q)
            print("FAILED CHECKS:")
            for e in errs:
                print("-", e)
        else:
            print(f"[PASS] {q}")

    with output_file.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nWrote eval results -> {output_file}")

    if all_fails:
        raise SystemExit(f"\nEvaluation finished with {all_fails} failing queries.")
    print("\nAll checks passed.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--top_k", type=int, default=25)
    ap.add_argument("--min_recurring_reviews", type=int, default=2)
    ap.add_argument("--out", default="data/eval_results.jsonl")
    args = ap.parse_args()
    main(args.top_k, args.min_recurring_reviews, args.out)
