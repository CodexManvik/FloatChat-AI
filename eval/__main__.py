"""
Run the benchmark against a FloatChat API and write the scores.

    python -m eval --api https://floatchat-ai-svjw.onrender.com
    python -m eval --api http://localhost:8000 --delay 0 --only depth-avg,regions
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from eval.runner import load_cases, run_eval, summarize, to_markdown

HERE = Path(__file__).parent


def http_sender(api: str, timeout: float = 90):
    session = requests.Session()
    session.headers["User-Agent"] = "FloatChat-eval"

    def send(payload: dict) -> tuple[int, dict]:
        try:
            response = session.post(f"{api}/query", json=payload, timeout=timeout)
        except requests.RequestException as e:
            print(f"  request failed: {e.__class__.__name__}")
            return 0, {}
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, {}

    return send


def wake(api: str) -> None:
    """Free hosting sleeps when idle; wait for it so the first question's latency isn't a cold start."""
    try:
        health = requests.get(f"{api}/health", timeout=180, headers={"User-Agent": "FloatChat-eval"}).json()
        print(f"API {health.get('status')}: {health.get('indexed_profiles')} profiles, LLM {health.get('llm')}")
    except (requests.RequestException, ValueError) as e:
        print(f"Health check failed ({e.__class__.__name__}); trying the questions anyway")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default=os.getenv("FLOATCHAT_API", "http://localhost:8000"))
    parser.add_argument("--cases", default=str(HERE / "questions.json"))
    parser.add_argument("--delay", type=float, default=6.5,
                        help="seconds between questions (the public API allows 10 per minute)")
    parser.add_argument("--only", help="comma-separated case ids (their follow-up parents are added)")
    parser.add_argument("--out", default=str(HERE / "latest.json"))
    parser.add_argument("--markdown", default=str(HERE / "latest.md"))
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    api = args.api.rstrip("/")
    cases = load_cases(args.cases)
    if args.only:
        wanted = set(args.only.split(","))
        wanted |= {c["follow_up_of"] for c in cases if c["id"] in wanted and c.get("follow_up_of")}
        cases = [c for c in cases if c["id"] in wanted]

    wake(api)
    results = run_eval(cases, http_sender(api), delay=args.delay)
    summary = summarize(results)
    ran_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    markdown = to_markdown(summary, results, api, ran_at)

    Path(args.out).write_text(json.dumps({"api": api, "ran_at": ran_at, "summary": summary, "results": results},
                                         indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(args.markdown).write_text(markdown, encoding="utf-8")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(markdown)
    print("\n" + markdown)
    return 1 if summary["failed_requests"] == summary["cases"] else 0


if __name__ == "__main__":
    sys.exit(main())
