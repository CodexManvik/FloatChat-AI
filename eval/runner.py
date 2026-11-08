"""
Score FloatChat answers against benchmark questions.

Each case says how the question should be understood (SQL or profile search, which analysis, which filters).
A case is scored on three checks:

- routing: the API took the expected path (and, for SQL, ran the expected analysis)
- filters: it understood exactly the expected region / month / year / sensor filters
- answer:  the answer holds up — SQL returned rows and actually applies the filters it reports; every profile a search
           returned matches the filters it reports
"""

import json
import re
import statistics
import time
from collections.abc import Callable
from pathlib import Path

RATE_LIMIT_WAIT = 65  # seconds to wait after a 429 before the single retry
Send = Callable[[dict], tuple[int, dict]]  # POST /query payload -> (status code, JSON body)


def load_cases(path: str | Path) -> list[dict]:
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    seen = set()
    for case in cases:
        if case["id"] in seen:
            raise ValueError(f"Duplicate case id {case['id']!r}")
        if case.get("follow_up_of") and case["follow_up_of"] not in seen:
            raise ValueError(f"{case['id']!r} follows up on {case['follow_up_of']!r}, which must come earlier")
        if case["expect"]["path"] not in ("analytical", "semantic"):
            raise ValueError(f"{case['id']!r} has an unknown path")
        seen.add(case["id"])
    return cases


def _without(filters: dict | None, keys) -> dict:
    return {k: v for k, v in (filters or {}).items() if k not in keys}


def _sql_applies(sql: str, key: str, value) -> bool:
    """Does the SQL filter on this key? Templates bind parameters (:region); LLM-written SQL may inline values."""
    lowered = sql.lower()
    if f":{key}" in lowered or (key.startswith("has_") and key in lowered):
        return True
    if isinstance(value, str):
        return f"'{value.lower()}'" in lowered
    if isinstance(value, int) and re.search(rf"\b{value}\b", lowered):
        return ("month" if key == "month_num" else "year") in lowered
    return False


def _profile_matches(profile: dict, filters: dict) -> bool:
    return all(profile.get(key) == value for key, value in filters.items())


def _check_analytical(response: dict) -> str | None:
    if not response.get("sql_results"):
        return "SQL returned no rows"
    meta = (response.get("retrieved_metadata") or [{}])[0]
    sql = meta.get("sql_query") or ""
    missing = [key for key, value in (response.get("filters") or {}).items() if not _sql_applies(sql, key, value)]
    return f"SQL does not apply {', '.join(missing)}" if missing else None


def _check_semantic(response: dict) -> str | None:
    profiles = response.get("retrieved_metadata") or []
    if not profiles:
        return "no profiles returned"
    if any(s.get("step") == "search" and s.get("fallback_without_filters") for s in response.get("steps") or []):
        return "no profile matched the filters (search was widened)"
    filters = response.get("filters") or {}
    wrong = sum(not _profile_matches(p, filters) for p in profiles)
    return f"{wrong} of {len(profiles)} profiles do not match the filters" if wrong else None


def check_case(case: dict, status: int, response: dict, latency_ms: int) -> dict:
    expect = case["expect"]
    intents = expect.get("intent")
    intents = [intents] if isinstance(intents, str) else intents
    optional = expect.get("optional_filters", [])
    steps = (response.get("steps") or []) if status == 200 else []
    understood = next((s for s in steps if s.get("step") == "understood"), {})
    # Routing and filters are judged on what the router decided; the answer check covers what happened next
    decided = {"path": understood.get("path", response.get("query_type")),
               "intent": understood.get("intent", response.get("intent")),
               "filters": understood.get("filters", response.get("filters")) or {}}
    result = {
        "id": case["id"],
        "question": case["question"],
        "follow_up_of": case.get("follow_up_of"),
        "expected": {"path": expect["path"], "intent": intents, "filters": expect["filters"]},
        "got": {**decided, "answered_by": response.get("query_type")} if status == 200 else None,
        "status": status,
        "latency_ms": latency_ms,
        "router": understood.get("router"),
        "llm_wrote_answer": any(s.get("step") == "answer" and s.get("llm_used") for s in steps),
        "routing": False,
        "filters": False,
        "answer": False,
        "note": None,
    }
    if status != 200:
        result["note"] = f"HTTP {status}" if status else "request failed"
        return result
    if response.get("query_type") == "error":
        result["note"] = "the API returned an error answer"
        return result

    path_ok = decided["path"] == expect["path"]
    result["routing"] = path_ok and (expect["path"] != "analytical" or not intents or decided["intent"] in intents)
    result["filters"] = _without(decided["filters"], optional) == _without(expect["filters"], optional)
    if response.get("query_type") != decided["path"]:
        problem = "SQL failed or found nothing, so it fell back to profile search"
    elif response.get("query_type") == "analytical":
        problem = _check_analytical(response)
    else:
        problem = _check_semantic(response)
    result["answer"] = problem is None
    notes = []
    if not result["routing"]:
        notes.append(f"routed to {decided['path']}/{decided['intent']}")
    if not result["filters"]:
        notes.append(f"filters {json.dumps(decided['filters'])}")
    if problem:
        notes.append(problem)
    result["note"] = "; ".join(notes) or None
    return result


def run_eval(cases: list[dict], send: Send, delay: float = 6.5, sleep=time.sleep, clock=time.perf_counter,
             log=print) -> list[dict]:
    """Ask every question in order (follow-ups get their parent's answer as history), pacing for rate limits."""
    questions = {case["id"]: case["question"] for case in cases}
    answers: dict[str, dict] = {}
    results = []
    for i, case in enumerate(cases):
        if i:
            sleep(delay)
        history = []
        parent = case.get("follow_up_of")
        if parent and parent in answers:
            prev = answers[parent]
            history = [{"question": questions[parent], "query_type": prev.get("query_type"),
                        "intent": prev.get("intent"), "filters": prev.get("filters") or {}}]
        payload = {"query_text": case["question"], "history": history}
        started = clock()
        status, body = send(payload)
        if status == 429:
            log(f"  rate limited, waiting {RATE_LIMIT_WAIT} s")
            sleep(RATE_LIMIT_WAIT)
            started = clock()
            status, body = send(payload)
        latency_ms = int((clock() - started) * 1000)
        answers[case["id"]] = body if status == 200 else {}
        result = check_case(case, status, body if status == 200 else {}, latency_ms)
        results.append(result)
        mark = "PASS" if result["routing"] and result["filters"] and result["answer"] else "FAIL"
        log(f"[{i + 1}/{len(cases)}] {mark} {case['id']} ({latency_ms} ms){' - ' + result['note'] if result['note'] else ''}")
    return results


def summarize(results: list[dict]) -> dict:
    n = len(results)

    def share(key):
        return round(sum(r[key] for r in results) / n, 3) if n else 0.0

    latencies = [r["latency_ms"] for r in results if r["status"] == 200]
    return {
        "cases": n,
        "passed": sum(r["routing"] and r["filters"] and r["answer"] for r in results),
        "routing_accuracy": share("routing"),
        "filter_accuracy": share("filters"),
        "answer_pass_rate": share("answer"),
        "median_latency_ms": int(statistics.median(latencies)) if latencies else None,
        "llm_routed": sum(r["router"] == "llm" for r in results),
        "llm_wrote_answer": sum(r["llm_wrote_answer"] for r in results),
        "failed_requests": sum(r["status"] != 200 for r in results),
    }


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def to_markdown(summary: dict, results: list[dict], api: str, ran_at: str) -> str:
    tick = {True: "✅", False: "❌"}
    lines = [
        f"## FloatChat evaluation — {summary['passed']}/{summary['cases']} questions fully correct",
        "",
        f"Run against `{api}` on {ran_at}.",
        "",
        "| Metric | Score |",
        "|---|---|",
        f"| Routing accuracy (SQL vs search, and which analysis) | {_pct(summary['routing_accuracy'])} |",
        f"| Filter accuracy (region, month, year, sensor) | {_pct(summary['filter_accuracy'])} |",
        f"| Answer checks passed | {_pct(summary['answer_pass_rate'])} |",
        f"| Median latency | {summary['median_latency_ms']} ms |" if summary["median_latency_ms"] is not None
        else "| Median latency | n/a |",
        f"| Understood by the LLM router | {summary['llm_routed']}/{summary['cases']} |",
        f"| Answers written by the LLM | {summary['llm_wrote_answer']}/{summary['cases']} |",
        "",
        "| Case | Question | Routing | Filters | Answer | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        question = r["question"].replace("|", "\\|")
        follow = f" *(follow-up to {r['follow_up_of']})*" if r["follow_up_of"] else ""
        note = (r["note"] or "").replace("|", "\\|")
        lines.append(f"| `{r['id']}` | {question}{follow} | {tick[r['routing']]} | {tick[r['filters']]} | "
                     f"{tick[r['answer']]} | {note} |")
    return "\n".join(lines) + "\n"
