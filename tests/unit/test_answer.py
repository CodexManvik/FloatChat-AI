import pandas as pd

from floatchat.answer import describe_filters, format_position, format_results_for_display


def test_format_position():
    assert format_position(-12.5, 65.25) == "12.50°S, 65.25°E"


def test_describe_filters():
    assert describe_filters({"region": "Arabian Sea", "month_num": 3, "year": 2024, "has_oxygen": True}) == \
        "in the Arabian Sea in March 2024 from floats measuring oxygen"
    assert describe_filters({}) == ""


def test_format_avg_by_depth_truncates_with_a_note():
    df = pd.DataFrame({"depth": range(20), "avg_temperature": [20.0] * 20, "avg_salinity": [35.0] * 20,
                       "measurement_count": [5] * 20})
    text = format_results_for_display(df, "avg_by_depth")
    assert text.startswith("- **0 m**: 20.00 °C, 35.00 PSU (5 readings)")
    assert "8 more rows" in text
