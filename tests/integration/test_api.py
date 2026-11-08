import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.main import create_app
from tests.fakes import FakeEmbedder

pytestmark = pytest.mark.integration


def make_client(engine, **kwargs):
    kwargs.setdefault("get_embedder_fn", FakeEmbedder)
    kwargs.setdefault("chat_fn", lambda *a, **k: None)
    kwargs.setdefault("llm_enabled", lambda: False)
    kwargs.setdefault("stream_chat_fn", lambda *a, **k: iter(()))
    return TestClient(create_app(engine=engine, **kwargs))


def stream(client, question, history=None, ip="1.1.1.1"):
    """POST /query/stream and parse the Server-Sent Events into (event, data) pairs."""
    resp = client.post("/query/stream", json={"query_text": question, "history": history or []},
                       headers={"X-Forwarded-For": ip})
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in resp.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def ask(client, question, ip="1.1.1.1"):
    return client.post("/query", json={"query_text": question}, headers={"X-Forwarded-For": ip})


def test_ping_and_health(reader_engine):
    client = make_client(reader_engine)
    assert client.get("/ping").json() == {"ok": True}
    health = client.get("/health").json()
    assert health["status"] == "healthy" and health["database"] == "connected"
    assert health["vector_index"] == "ready" and health["indexed_profiles"] > 0
    assert health["llm"]["budget_exhausted"] is False and health["version"] == "3.0.0"


def test_stats_floats_and_profiles(reader_engine):
    client = make_client(reader_engine)
    assert client.get("/stats").json()["profiles"] > 0
    floats = client.get("/floats").json()
    track = client.get(f"/profiles/float/{floats[0]['float_id']}").json()
    assert track and track[0]["float_id"] == floats[0]["float_id"]
    assert client.get(f"/float/{floats[0]['float_id']}").json()["float_info"]["float_id"] == floats[0]["float_id"]
    assert client.get("/float/nope").json() == {"error": "Float not found"}
    profiles = client.post("/get_profiles", json={"profile_ids": [track[0]["profile_id"]]}).json()
    assert profiles and "chlorophyll" in profiles[0]


def test_query_analytical_and_semantic(reader_engine):
    client = make_client(reader_engine)
    analytical = ask(client, "What is the average temperature at different depths?").json()
    assert analytical["query_type"] == "analytical" and analytical["sql_results"]
    assert set(analytical) == {"answer", "query_type", "context_documents", "retrieved_metadata", "sql_results",
                               "intent", "filters", "steps"}
    assert analytical["intent"] == "avg_by_depth" and [s["step"] for s in analytical["steps"]][0] == "understood"
    semantic = ask(client, "Show me profiles in the Arabian Sea").json()
    assert semantic["query_type"] == "semantic"
    assert all(m["region"] == "Arabian Sea" for m in semantic["retrieved_metadata"])


def test_follow_up_question_with_history(reader_engine):
    client = make_client(reader_engine)
    first = ask(client, "What is the average temperature at different depths?").json()
    history = [{"question": "What is the average temperature at different depths?",
                "query_type": first["query_type"], "intent": first["intent"], "filters": first["filters"]}]
    resp = client.post("/query", json={"query_text": "now only the Arabian Sea", "history": history},
                       headers={"X-Forwarded-For": "1.1.1.1"}).json()
    assert resp["intent"] == "avg_by_depth" and resp["filters"] == {"region": "Arabian Sea"}
    too_long = client.post("/query", json={"query_text": "x", "history": history * 4})
    assert too_long.status_code == 422


def test_stream_sends_steps_tokens_then_the_result(reader_engine):
    client = make_client(reader_engine, chat_fn=lambda *a, **k: None,
                         stream_chat_fn=lambda *a, **k: iter(["Streamed ", "answer."]), llm_enabled=lambda: True)
    events = stream(client, "Show me profiles in the Arabian Sea")
    kinds = [kind for kind, _ in events]
    assert kinds[0] == "step" and kinds[-1] == "result" and "token" in kinds
    assert kinds.index("token") > kinds.index("step")
    result = events[-1][1]
    assert result["answer"] == "".join(data["text"] for kind, data in events if kind == "token")
    assert result["answer"] == "Streamed answer." and result["query_type"] == "semantic"
    assert [data["step"] for kind, data in events if kind == "step"] == [s["step"] for s in result["steps"]]


def test_cached_stream_replays_steps(reader_engine):
    client = make_client(reader_engine)
    first = stream(client, "What is the average temperature at different depths?")
    second = stream(client, "What is the average temperature at different depths?")
    assert [k for k, _ in second] == [k for k, _ in first if k == "step"] + ["token", "result"]
    assert second[-1][1]["answer"] == first[-1][1]["answer"]


def test_stream_is_rate_limited_with_query(reader_engine):
    client = make_client(reader_engine, query_limits=(1, 100))
    stream(client, "Show me profiles in the Arabian Sea")
    limited = client.post("/query", json={"query_text": "again"}, headers={"X-Forwarded-For": "1.1.1.1"})
    assert limited.status_code == 429


def test_query_validation(reader_engine):
    client = make_client(reader_engine)
    assert ask(client, "   ").status_code == 422
    assert ask(client, "x" * 301).status_code == 422


def test_rate_limit_per_ip(reader_engine):
    client = make_client(reader_engine, query_limits=(2, 100))
    assert ask(client, "Show me profiles in the Arabian Sea").status_code == 200
    assert ask(client, "Show me profiles in the Bay of Bengal").status_code == 200
    limited = ask(client, "Show me profiles near the equator")
    assert limited.status_code == 429 and limited.json()["error"] == "rate_limited"
    assert ask(client, "Show me profiles near the equator", ip="2.2.2.2").status_code == 200


def test_cache_and_query_log(reader_engine, loaded_db):
    client = make_client(reader_engine)
    first = ask(client, "Show me profiles in the Arabian Sea").json()
    second = ask(client, "show me profiles in the arabian sea?").json()
    assert first == second
    with loaded_db.connect() as conn:
        rows = conn.execute(text("SELECT cached, success FROM query_log ORDER BY id")).all()
    assert [tuple(r) for r in rows] == [(False, True), (True, True)]


def test_answers_are_not_cached_when_the_llm_failed(reader_engine, loaded_db):
    # A transient LLM failure must not pin the data-only answer in the cache for 24 hours
    calls = []

    def flaky_llm(*a, **k):
        if k.get("json_mode"):
            return None  # router call: fall back to keywords
        calls.append(1)
        return None if len(calls) == 1 else "MOCK ANSWER"

    client = make_client(reader_engine, chat_fn=flaky_llm, llm_enabled=lambda: True)
    assert ask(client, "Show me profiles in the Arabian Sea").json()["answer"].startswith("Here are the")
    assert ask(client, "Show me profiles in the Arabian Sea").json()["answer"] == "MOCK ANSWER"
    assert ask(client, "Show me profiles in the Arabian Sea").json()["answer"] == "MOCK ANSWER"
    with loaded_db.connect() as conn:
        cached = conn.execute(text("SELECT cached FROM query_log ORDER BY id")).scalars().all()
    assert cached == [False, False, True]


def test_llm_budget_falls_back_to_data_only(reader_engine):
    calls = []

    def chat(*a, **k):
        calls.append(1)
        return "MOCK ANSWER"

    client = make_client(reader_engine, chat_fn=chat, llm_budget=1)
    assert ask(client, "Show me profiles in the Arabian Sea").json()["answer"] == "MOCK ANSWER"
    fallback = ask(client, "Show me profiles in the Bay of Bengal").json()["answer"]
    assert fallback.startswith("Here are the") and len(calls) == 1
    assert client.get("/health").json()["llm"]["budget_exhausted"] is True


def test_exports(reader_engine):
    client = make_client(reader_engine)
    csv = client.post("/export", json={"format": "csv", "profile_ids": [1]})
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    assert client.post("/export", json={"format": "csv", "profile_ids": list(range(51))}).status_code == 422
    assert client.post("/export", json={"format": "xlsx", "profile_ids": [1]}).status_code == 422
    assert client.post("/export", json={"format": "csv"}).status_code == 400


def test_cors_only_for_allowed_origins(reader_engine):
    client = make_client(reader_engine)
    ok = client.options("/stats", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.options("/stats", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_unexpected_error_returns_friendly_answer(reader_engine, monkeypatch):
    import api.main

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(api.main, "answer_question", boom)
    result = ask(make_client(reader_engine), "Show me profiles in the Arabian Sea").json()
    assert result["query_type"] == "error" and "kaboom" not in result["answer"]
