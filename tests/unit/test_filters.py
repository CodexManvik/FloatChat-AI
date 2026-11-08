from floatchat.filters import clean_filters, sql_conditions


def test_clean_filters_keeps_only_valid_values():
    raw = {"region": "Arabian Sea", "month_num": 3, "year": 2026, "has_oxygen": True,
           "evil": "1; DROP", "has_ph": False}
    assert clean_filters(raw) == {"region": "Arabian Sea", "month_num": 3, "year": 2026, "has_oxygen": True}


def test_clean_filters_rejects_out_of_range_values():
    assert clean_filters({"region": "Atlantis", "month_num": 13, "year": 1890}) == {}
    assert clean_filters({"month_num": "4", "year": "2025"}) == {"month_num": 4, "year": 2025}
    assert clean_filters(None) == {}


def test_sql_conditions_are_parameterised():
    conditions, params = sql_conditions({"region": "Bay of Bengal", "month_num": 2, "has_nitrate": True}, alias="p")
    assert conditions == ["p.region = :region", "EXTRACT(MONTH FROM p.profile_date) = :month_num", "p.has_nitrate"]
    assert params == {"region": "Bay of Bengal", "month_num": 2}


def test_sql_conditions_empty():
    assert sql_conditions({}, alias="p") == ([], {})
