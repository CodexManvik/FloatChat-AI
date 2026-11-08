import json

import pytest

from eval.runner import RATE_LIMIT_WAIT, check_case, load_cases, run_eval, summarize, to_markdown

DEPTH = {"id": "depth", "question": "average temperature by depth in the Arabian Sea",
         "expect": {"path": "analytical", "intent": "avg_by_depth", "filters": {"region": "Arabian Sea"}}}
FIND = {"id": "find", "question": "oxygen profiles in the Bay of Bengal",
        "expect": {"path": "semantic", "filters": {"region": "Bay of Bengal"}, "optional_filters": ["has_oxygen"]}}


def analytical(intent="avg_by_depth", filters=None, sql="SELECT ... WHERE p.region = :region", rows=1, llm=False):
    filters = {"region": "Arabian Sea"} if filters is None else filters
    return {"query_type": "analytical", "intent": intent, "filters": filters,
            "sql_results": [{"depth": 0}] * rows, "retrieved_metadata": [{"sql_query": sql}],
            "steps": [{"step": "understood", "router": "llm"}, {"step": "answer", "llm_used": llm}]}


def semantic(profiles, filters=None, fallback=False):
    filters = {"region": "Bay of Bengal", "has_oxygen": True} if filters is None else filters
    return {"query_type": "semantic", "intent": None, "filters": filters, "retrieved_metadata": profiles,
            "steps": [{"step": "understood", "router": "keywords"},
                      {"step": "search", "fallback_without_filters": fallback}, {"step": "answer", "llm_used": True}]}


def bengal(**extra):
    return {"region": "Bay of Bengal", "has_oxygen": True, "month_num": 3, "year": 2026, **extra}


def test_a_correct_analytical_answer_passes_every_check():
    r = check_case(DEPTH, 200, analytical(llm=True), 120)
    assert (r["routing"], r["filters"], r["answer"]) == (True, True, True)
    assert r["note"] is None and r["router"] == "llm" and r["llm_wrote_answer"] is True


@pytest.mark.parametrize("response, failed, note", [
    (analytical(intent="custom"), "routing", "routed to analytical/custom"),
    (semantic([bengal()], filters={"region": "Arabian Sea"}), "routing", "routed to semantic"),
    (analytical(filters={}), "filters", "filters {}"),
    (analytical(rows=0), "answer", "SQL returned no rows"),
    (analytical(sql="SELECT avg(temperature) FROM measurements"), "answer", "SQL does not apply region"),
])
def test_each_check_fails_on_its_own(response, failed, note):
    r = check_case(DEPTH, 200, response, 10)
    assert r[failed] is False and note in r["note"]


def test_routing_is_judged_on_the_router_decision_and_a_search_fallback_fails_the_answer():
    fell_back = semantic([bengal(region="Arabian Sea")], filters={"region": "Arabian Sea"})
    fell_back["steps"][0].update(path="analytical", intent="avg_by_depth", filters={"region": "Arabian Sea"})
    r = check_case(DEPTH, 200, fell_back, 10)
    assert r["routing"] and r["filters"] and not r["answer"] and "fell back" in r["note"]
    assert r["got"]["answered_by"] == "semantic"


def test_llm_sql_with_inlined_filter_values_counts_as_applied():
    sql = "SELECT max(temperature) FROM measurements m JOIN profiles p USING (profile_id) " \
          "WHERE p.region = 'Arabian Sea' AND EXTRACT(YEAR FROM p.profile_date) = 2026"
    r = check_case(DEPTH, 200, analytical(filters={"region": "Arabian Sea", "year": 2026}, sql=sql), 10)
    assert r["answer"] is True and r["filters"] is False  # year wasn't expected


def test_a_list_of_intents_accepts_any_of_them():
    case = {**DEPTH, "expect": {**DEPTH["expect"], "intent": ["custom", "avg_by_depth"]}}
    assert check_case(case, 200, analytical(intent="custom"), 10)["routing"] is True


def test_semantic_answers_must_only_return_matching_profiles():
    assert check_case(FIND, 200, semantic([bengal(), bengal()]), 10)["answer"] is True
    wrong = check_case(FIND, 200, semantic([bengal(), bengal(region="Arabian Sea")]), 10)
    assert wrong["answer"] is False and "1 of 2 profiles" in wrong["note"]
    widened = check_case(FIND, 200, semantic([bengal()], fallback=True), 10)
    assert widened["answer"] is False and "widened" in widened["note"]
    assert check_case(FIND, 200, semantic([]), 10)["answer"] is False


def test_optional_filters_are_ignored_when_comparing():
    assert check_case(FIND, 200, semantic([bengal()]), 10)["filters"] is True
    assert check_case(FIND, 200, semantic([bengal()], filters={"region": "Bay of Bengal"}), 10)["filters"] is True


def test_failed_requests_and_error_answers_fail_everything():
    for status, body, note in ((429, {}, "HTTP 429"), (0, {}, "request failed"),
                               (200, {"query_type": "error"}, "error answer")):
        r = check_case(DEPTH, status, body, 10)
        assert not (r["routing"] or r["filters"] or r["answer"]) and note in r["note"]


def test_follow_ups_get_their_parents_answer_as_history_and_requests_are_paced():
    follow = {"id": "follow", "follow_up_of": "depth", "question": "now only in March",
              "expect": {"path": "analytical", "intent": "avg_by_depth",
                         "filters": {"region": "Arabian Sea", "month_num": 3}}}
    sent, sleeps = [], []

    def send(payload):
        sent.append(payload)
        return 200, analytical(filters={"region": "Arabian Sea", "month_num": 3} if payload["history"] else None,
                               sql="... :region ... :month_num")

    results = run_eval([DEPTH, follow], send, delay=6.5, sleep=sleeps.append, log=lambda *_: None)
    assert sent[0]["history"] == []
    assert sent[1]["history"] == [{"question": DEPTH["question"], "query_type": "analytical",
                                   "intent": "avg_by_depth", "filters": {"region": "Arabian Sea"}}]
    assert sleeps == [6.5] and all(r["routing"] and r["filters"] and r["answer"] for r in results)


def test_a_rate_limited_question_is_retried_once_after_waiting():
    replies = iter([(429, {}), (200, analytical())])
    sleeps = []
    results = run_eval([DEPTH], lambda payload: next(replies), sleep=sleeps.append, log=lambda *_: None)
    assert sleeps == [RATE_LIMIT_WAIT] and results[0]["answer"] is True


def test_summary_and_markdown():
    results = [check_case(DEPTH, 200, analytical(llm=True), 100), check_case(DEPTH, 200, analytical(rows=0), 300),
               check_case(DEPTH, 429, {}, 5)]
    summary = summarize(results)
    assert summary == {"cases": 3, "passed": 1, "routing_accuracy": 0.667, "filter_accuracy": 0.667,
                       "answer_pass_rate": 0.333, "median_latency_ms": 200, "llm_routed": 2, "llm_wrote_answer": 1,
                       "failed_requests": 1}
    markdown = to_markdown(summary, results, "http://api", "2026-11-08 10:00 UTC")
    assert markdown.startswith("## FloatChat evaluation — 1/3 questions fully correct")
    assert "| Routing accuracy (SQL vs search, and which analysis) | 67% |" in markdown
    assert markdown.count("| `depth` |") == 3


def test_load_cases_validates_ids_and_follow_up_order(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([{**DEPTH, "follow_up_of": "later"}]))
    with pytest.raises(ValueError, match="must come earlier"):
        load_cases(path)
    path.write_text(json.dumps([DEPTH, DEPTH]))
    with pytest.raises(ValueError, match="Duplicate"):
        load_cases(path)


def test_the_shipped_benchmark_is_valid():
    from eval.__main__ import HERE

    cases = load_cases(HERE / "questions.json")
    assert len(cases) >= 30
    assert {c["expect"]["path"] for c in cases} == {"analytical", "semantic"}
    assert sum(bool(c.get("follow_up_of")) for c in cases) >= 3
