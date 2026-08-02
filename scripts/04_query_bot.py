# scripts/04_query_bot.py
import json
from app.rag import generate_grounded_response


def main(q: str, top_k: int, min_recurring_reviews: int, include_debug: bool) -> None:
    out = generate_grounded_response(
        q,
        top_k=top_k,
        min_recurring_reviews=min_recurring_reviews,
        include_debug=include_debug,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--q", required=True)
    ap.add_argument("--top_k", type=int, default=8)
    ap.add_argument("--min_recurring_reviews", type=int, default=2)
    ap.add_argument("--debug", action="store_true", help="Include debug block in output")
    args = ap.parse_args()

    main(args.q, args.top_k, args.min_recurring_reviews, args.debug)