"""
Ask a deployed FloatChat API five real questions and report answers and timings.

    python scripts/smoke_test.py https://<your-service>.onrender.com
"""

import sys
import time

import requests

QUESTIONS = [
    "What is the average temperature at different depths?",
    "Compare surface temperature across ocean regions",
    "Average dissolved oxygen by ocean zone",
    "Show me salinity profiles near the equator",
    "Which floats measured low oxygen in the Arabian Sea?",
]
SLOW_SECONDS = 20


def main(base_url: str) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # answers contain °, µ, ₂ (Windows consoles)
    base_url = base_url.rstrip("/")
    failures = 0
    ping = requests.get(f"{base_url}/ping", timeout=60)
    print(f"/ping -> {ping.status_code} {ping.json()}")
    health = requests.get(f"{base_url}/health", timeout=60).json()
    print(f"/health -> {health['status']}, {health['indexed_profiles']} profiles, newest {health['newest_data']}, "
          f"LLM configured={health['llm']['configured']} reachable={health['llm']['reachable']}")
    if health["status"] != "healthy":
        failures += 1
    for question in QUESTIONS:
        started = time.perf_counter()
        resp = requests.post(f"{base_url}/query", json={"query_text": question}, timeout=120)
        seconds = time.perf_counter() - started
        ok = resp.status_code == 200 and resp.json().get("query_type") in ("analytical", "semantic")
        failures += (not ok) or seconds > SLOW_SECONDS
        summary = resp.json().get("answer", resp.text)[:110].replace("\n", " ") if resp.ok else resp.text[:110]
        kind = resp.json().get("query_type", "-") if resp.ok else resp.status_code
        print(f"{'OK ' if ok else 'ERR'} {seconds:5.1f}s [{kind}] {question}\n      {summary}")
    print("All checks passed." if not failures else f"{failures} check(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
