import pytest

from eval.__main__ import HERE
from eval.runner import load_cases, run_eval, summarize
from tests.integration.test_api import make_client

pytestmark = pytest.mark.integration


def test_the_benchmark_runs_against_a_local_api(reader_engine):
    # No LLM here, so this scores the keyword router: the template questions and follow-ups must still be understood
    client = make_client(reader_engine, query_limits=(1000, 1000))

    def send(payload):
        response = client.post("/query", json=payload, headers={"X-Forwarded-For": "9.9.9.9"})
        return response.status_code, response.json()

    results = run_eval(load_cases(HERE / "questions.json"), send, delay=0, sleep=lambda s: None, log=lambda *_: None)
    by_id = {r["id"]: r for r in results}
    summary = summarize(results)
    assert summary["failed_requests"] == 0 and summary["cases"] == len(results)
    for case in ("depth-avg", "depth-avg-arabian", "regions", "layers", "monthly", "follow-region", "follow-month",
                 "follow-oxygen", "find-bengal", "find-low-oxygen"):
        assert by_id[case]["routing"] and by_id[case]["filters"], (case, by_id[case]["note"])
    assert by_id["depth-avg"]["answer"] and by_id["depth-avg-arabian"]["answer"]
    assert all(r["router"] == "keywords" and not r["llm_wrote_answer"] for r in results)
