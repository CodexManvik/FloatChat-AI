import json

from floatchat.router import keyword_route, llm_route, route

PREVIOUS_SQL = {"question": "What is the average temperature at different depths?", "query_type": "analytical",
                "intent": "avg_by_depth", "filters": {"month_num": 3}}
PREVIOUS_SEARCH = {"question": "Show me salinity profiles near the equator", "query_type": "semantic",
                   "intent": None, "filters": {"region": "Equatorial Indian Ocean"}}


def test_keyword_route_matches_phase1_routing():
    r = keyword_route("What is the average temperature at different depths in the Arabian Sea?")
    assert (r.path, r.intent, r.filters, r.source) == ("analytical", "avg_by_depth", {"region": "Arabian Sea"}, "keywords")
    r = keyword_route("Show me salinity profiles near the equator in March 2024")
    assert (r.path, r.intent) == ("semantic", None)
    assert r.filters == {"region": "Equatorial Indian Ocean", "month_num": 3, "year": 2024}


def test_keyword_follow_up_reuses_the_previous_statistical_question():
    r = keyword_route("now only the Arabian Sea", [PREVIOUS_SQL])
    assert (r.path, r.intent) == ("analytical", "avg_by_depth")
    assert r.filters == {"month_num": 3, "region": "Arabian Sea"}
    assert r.question.startswith("What is the average temperature at different depths?")


def test_keyword_follow_up_on_a_search():
    r = keyword_route("what about February?", [PREVIOUS_SEARCH])
    assert r.path == "semantic"
    assert r.filters == {"region": "Equatorial Indian Ocean", "month_num": 2}


def test_a_new_question_with_a_region_is_not_a_follow_up():
    r = keyword_route("Show me profiles in the Arabian Sea", [PREVIOUS_SQL])
    assert (r.path, r.filters) == ("semantic", {"region": "Arabian Sea"})


def fake_llm(reply):
    calls = []

    def chat(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return reply if isinstance(reply, str) else json.dumps(reply)

    chat.calls = calls
    return chat


def test_llm_route_is_validated():
    chat = fake_llm({"path": "analytical", "intent": "bgc_analysis",
                     "filters": {"region": "Arabian Sea", "has_oxygen": True, "month_num": 14, "bogus": 1},
                     "question": "Average oxygen by ocean zone in the Arabian Sea"})
    r = llm_route("how's the oxygen doing in the arabian sea, by zone?", [], chat)
    assert (r.path, r.intent, r.source) == ("analytical", "bgc_analysis", "llm")
    assert r.filters == {"region": "Arabian Sea", "has_oxygen": True}
    assert r.question == "Average oxygen by ocean zone in the Arabian Sea"
    assert chat.calls[0][1].get("json_mode") is True


def test_llm_route_unknown_intent_becomes_custom_sql():
    r = llm_route("q", [], fake_llm({"path": "analytical", "intent": "teleport", "filters": {}, "question": "q"}))
    assert (r.path, r.intent) == ("analytical", "custom")


def test_llm_route_gives_up_on_malformed_replies():
    assert llm_route("q", [], fake_llm("not json at all")) is None
    assert llm_route("q", [], fake_llm({"path": "sideways"})) is None
    assert llm_route("q", [], lambda *a, **k: None) is None


def test_route_falls_back_to_keywords():
    r = route("What is the average temperature at different depths?", [], fake_llm("garbage"), use_llm=True)
    assert (r.source, r.intent) == ("keywords", "avg_by_depth")
    chat = fake_llm({"path": "semantic", "filters": {}, "question": "x"})
    assert route("anything", [], chat, use_llm=False).source == "keywords" and not chat.calls


def test_llm_prompt_includes_history():
    chat = fake_llm({"path": "analytical", "intent": "avg_by_depth", "filters": {}, "question": "q"})
    llm_route("now only the Arabian Sea", [PREVIOUS_SQL], chat)
    assert "What is the average temperature at different depths?" in chat.calls[0][0]
